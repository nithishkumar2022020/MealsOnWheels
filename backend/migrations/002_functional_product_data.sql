-- MealsOnWheels — owner-managed product data
--
-- Source of truth: docs/16_FUNCTIONAL_PRODUCT_DATA.md.
-- Idempotent: safe to re-run against an existing database.
-- Forward-only: no down migration. Roll back by restoring a backup.
--
-- Menus, hours, and prep times become data an owner edits rather than fixtures
-- in app/services/menu.py. One migration rather than six because the pieces
-- interlock — a half-applied version of this is worse than either end state.
--
-- Written while `bookings` is still empty, which is why booking_type can be
-- added NOT NULL and the id type is still open to change later.

-- --------------------------------------------------- restaurants: split ----

-- `is_active` carried two meanings already ("ops approved this listing" and
-- "include in search") and the design wants a third ("we are open right now").
-- Collapsing them is a live bug: an owner tapping Closed at the end of a shift
-- would flip the flag meaning "unapproved" and need an operator to undo it.
--
-- Three independent facts, three different owners, three different lifetimes.
ALTER TABLE restaurants
    ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- Owner toggle from the kitchen tablet. Several times a day.
    ADD COLUMN IF NOT EXISTS is_accepting_orders BOOLEAN NOT NULL DEFAULT true,
    -- Load-bearing, not cosmetic: cutoff validation asks "is 07:30 UTC inside
    -- Monday 06:00-23:00 LOCAL", which is unanswerable without the zone.
    ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    -- Which fulfilment modes this restaurant will serve. A restaurant
    -- supporting none cannot be approved.
    ADD COLUMN IF NOT EXISTS supported_booking_types TEXT[] NOT NULL
        DEFAULT ARRAY['bus_boarding_point', 'self_drive_dine', 'self_drive_takeaway'];

DO $$
BEGIN
    -- Carry the old flag across before it stops being the source of truth:
    -- everything currently live was approved, everything inactive was awaiting
    -- review. Guarded so a re-run cannot re-approve a row an operator has since
    -- rejected.
    IF NOT EXISTS (
        SELECT 1 FROM restaurants WHERE approval_status <> 'pending'
    ) THEN
        UPDATE restaurants
           SET approval_status = CASE WHEN is_active THEN 'approved' ELSE 'pending' END;
    END IF;
END $$;

ALTER TABLE restaurants
    DROP CONSTRAINT IF EXISTS ck_restaurants_approval_status;
ALTER TABLE restaurants
    ADD CONSTRAINT ck_restaurants_approval_status
        CHECK (approval_status IN ('pending', 'approved', 'rejected'));

ALTER TABLE restaurants
    DROP CONSTRAINT IF EXISTS ck_restaurants_booking_types;
ALTER TABLE restaurants
    ADD CONSTRAINT ck_restaurants_booking_types
        CHECK (supported_booking_types <@ ARRAY[
            'bus_boarding_point', 'self_drive_dine', 'self_drive_takeaway'
        ]::TEXT[]);

-- `is_active` is deliberately LEFT IN PLACE and still maintained by the
-- application as `approval_status = 'approved'`. Dropping a column that the
-- previous release still reads would break a rolling deploy; it is retired in a
-- later migration once nothing references it.
COMMENT ON COLUMN restaurants.is_active IS
    'DEPRECATED: mirrors approval_status = ''approved''. Use the bookability '
    'triple (approval_status, is_accepting_orders, restaurant_hours) instead. '
    'Retained for one release so a rollback does not break search.';

-- Search filters on all three facts, so the partial index has to match.
CREATE INDEX IF NOT EXISTS idx_restaurants_bookable
    ON restaurants (approval_status, is_accepting_orders)
    WHERE approval_status = 'approved' AND is_accepting_orders = true;

-- ------------------------------------------------------ restaurant_users ----

-- Neither the design nor the backend modelled WHO an owner is: the design's
-- restaurant login returns a restaurant_id without saying what authenticates
-- against it, and restaurants.phone is a contact field, not an identity.
--
-- One row per person. Costs nothing now, and means a dhaba with an owner AND a
-- manager — or an owner with two outlets — needs no migration later.
CREATE TABLE IF NOT EXISTS restaurant_users (
    id             BIGSERIAL PRIMARY KEY,
    restaurant_id  BIGINT       NOT NULL REFERENCES restaurants (id),
    phone          VARCHAR(20)  NOT NULL UNIQUE,  -- E.164
    name           VARCHAR(100),
    is_active      BOOLEAN      NOT NULL DEFAULT true,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- The login lookup: one row by phone.
CREATE INDEX IF NOT EXISTS idx_restaurant_users_restaurant
    ON restaurant_users (restaurant_id);

-- ----------------------------------------------------------- menu_items ----

CREATE TABLE IF NOT EXISTS menu_items (
    id                 BIGSERIAL PRIMARY KEY,
    restaurant_id      BIGINT       NOT NULL REFERENCES restaurants (id),
    name               VARCHAR(200) NOT NULL,
    description        TEXT,
    -- Still the only price source. Moving from a Python constant to a row does
    -- not change the trust boundary: prices are resolved server-side and frozen
    -- onto the booking line at order time.
    price              DECIMAL(10, 2) NOT NULL,
    category           VARCHAR(50)  NOT NULL,
    -- NULL means "use the restaurant's avg_prep_time_minutes".
    prep_time_minutes  INTEGER,
    -- Today's stock. Deliberately separate from deleted_at: "out of paneer" and
    -- "we stopped selling this" are different actions with different
    -- reversibility, and merging them makes an owner re-create the dish
    -- tomorrow.
    is_available       BOOLEAN      NOT NULL DEFAULT true,
    image_url          TEXT,
    -- The owner's ordering. Alphabetical would put Beverage before Main.
    display_order      INTEGER      NOT NULL DEFAULT 0,
    -- Soft delete. bookings.items holds a frozen snapshot and menu_item_id is a
    -- plain integer rather than an FK, so a hard delete of a discontinued dish
    -- would either fail or cascade into historical orders.
    deleted_at         TIMESTAMPTZ,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_menu_items_price_nonneg  CHECK (price >= 0),
    CONSTRAINT ck_menu_items_prep_positive CHECK (prep_time_minutes IS NULL
                                                  OR prep_time_minutes > 0)
);

-- Every menu read is "live items for this restaurant, in the owner's order".
CREATE INDEX IF NOT EXISTS idx_menu_items_restaurant
    ON menu_items (restaurant_id, display_order)
    WHERE deleted_at IS NULL;

-- One live dish per name per restaurant. Partial, so a soft-deleted dish does
-- not block re-adding it, and price resolution by name stays unambiguous.
CREATE UNIQUE INDEX IF NOT EXISTS idx_menu_items_unique_live_name
    ON menu_items (restaurant_id, name)
    WHERE deleted_at IS NULL;

-- ------------------------------------------------------ restaurant_hours ----

-- Absent rows mean CLOSED, not open-all-day: a newly approved restaurant that
-- has not set hours must not silently accept 3am orders.
CREATE TABLE IF NOT EXISTS restaurant_hours (
    restaurant_id  BIGINT   NOT NULL REFERENCES restaurants (id),
    weekday        SMALLINT NOT NULL,  -- 0 = Monday, matching Python's weekday()
    opens_at       TIME     NOT NULL,
    closes_at      TIME     NOT NULL,

    PRIMARY KEY (restaurant_id, weekday),

    CONSTRAINT ck_restaurant_hours_weekday CHECK (weekday BETWEEN 0 AND 6)
    -- No CHECK that closes_at > opens_at: highway dhabas run past midnight, and
    -- closes_at < opens_at is how an overnight window is expressed
    -- (22:00-02:00). The application resolves the wrap.
);

-- --------------------------------------------------- bookings: new columns ----

ALTER TABLE bookings
    -- Three fulfilment modes are three different products sharing an order
    -- flow: a bus handover is a hard deadline, a dine-in is a seating, and
    -- ready_by differs per mode. Safe as NOT NULL while the table is empty.
    ADD COLUMN IF NOT EXISTS booking_type VARCHAR(32) NOT NULL
        DEFAULT 'self_drive_takeaway',
    -- Without these the charter's own north-star metric — "ready within +/-10
    -- minutes of stated arrival" (00_PROJECT_CHARTER.md section 9) — is not
    -- computable. updated_at only records the most recent change.
    ADD COLUMN IF NOT EXISTS confirmed_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS ready_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS handed_over_at TIMESTAMPTZ;

ALTER TABLE bookings
    DROP CONSTRAINT IF EXISTS ck_bookings_booking_type;
ALTER TABLE bookings
    ADD CONSTRAINT ck_bookings_booking_type
        CHECK (booking_type IN (
            'bus_boarding_point', 'self_drive_dine', 'self_drive_takeaway'
        ));

-- ------------------------------------------------------ ratings: comment ----

-- The design caps comments at 500 characters. Enforced here rather than only in
-- Pydantic so a direct writer cannot exceed it.
ALTER TABLE ratings
    DROP CONSTRAINT IF EXISTS ck_ratings_comment_length;
ALTER TABLE ratings
    ADD CONSTRAINT ck_ratings_comment_length
        CHECK (comment IS NULL OR char_length(comment) <= 500);
