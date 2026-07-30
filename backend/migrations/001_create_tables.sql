-- MealsOnWheels — initial schema
--
-- Source of truth: docs/04_DATABASE_DESIGN.md section 3.
-- Idempotent: safe to re-run against an existing database.
-- Forward-only: no down migration. Roll back by restoring a backup.
--
-- When Alembic is adopted (Phase 1), this file is BASELINED, not replaced.
-- See docs/04_DATABASE_DESIGN.md section 6.1 for the stamp procedure.

CREATE EXTENSION IF NOT EXISTS postgis;

-- ---------------------------------------------------------------- users ----

CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    phone       VARCHAR(20)  NOT NULL UNIQUE,   -- E.164, e.g. +919876543210
    email       VARCHAR(255),
    name        VARCHAR(100),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------- restaurants ----

CREATE TABLE IF NOT EXISTS restaurants (
    id                     BIGSERIAL PRIMARY KEY,
    name                   VARCHAR(200) NOT NULL,
    -- Empty string for OSM-derived rows: nobody was onboarded, so there is no
    -- contact to notify. Not NULL, so callers never branch on two empty cases.
    phone                  VARCHAR(20)  NOT NULL DEFAULT '',
    email                  VARCHAR(255),
    address                TEXT,
    location               GEOGRAPHY(POINT, 4326) NOT NULL,
    -- Mean of all three rating dimensions, 0-5. 0 means unrated; the API
    -- surfaces null rather than 0 so clients do not render zero stars.
    composite_rating       DECIMAL(3, 2) NOT NULL DEFAULT 0,
    rating_count           INTEGER      NOT NULL DEFAULT 0,
    -- Drives both the cutoff calculation and the minimum booking lead time.
    avg_prep_time_minutes  INTEGER      NOT NULL DEFAULT 30,
    -- Self-registrations land inactive; inactive rows are never searchable.
    is_active              BOOLEAN      NOT NULL DEFAULT true,
    -- Set when the row was promoted from an OpenStreetMap POI at search time.
    -- NULL for manually onboarded restaurants.
    osm_id                 BIGINT,
    created_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_restaurants_rating_range
        CHECK (composite_rating >= 0 AND composite_rating <= 5),
    CONSTRAINT ck_restaurants_rating_count_nonneg
        CHECK (rating_count >= 0),
    CONSTRAINT ck_restaurants_prep_time_positive
        CHECK (avg_prep_time_minutes > 0)
);

CREATE INDEX IF NOT EXISTS idx_restaurants_location
    ON restaurants USING GIST (location);

CREATE INDEX IF NOT EXISTS idx_restaurants_active
    ON restaurants (is_active) WHERE is_active = true;

-- Partial unique index, not a UNIQUE column: many rows legitimately have a
-- NULL osm_id, and this makes the search-time upsert conflict target work.
CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurants_osm_id
    ON restaurants (osm_id) WHERE osm_id IS NOT NULL;

-- --------------------------------------------------------------- routes ----

CREATE TABLE IF NOT EXISTS routes (
    id            BIGSERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    origin_name   VARCHAR(100) NOT NULL,
    dest_name     VARCHAR(100) NOT NULL,
    origin_point  GEOGRAPHY(POINT, 4326) NOT NULL,
    dest_point    GEOGRAPHY(POINT, 4326) NOT NULL,
    -- Polyline generated offline by OSRM at seed time. Production never calls
    -- OSRM (docs/03_SYSTEM_ARCHITECTURE.md section 3). NULL until seeded.
    geometry      GEOMETRY(LINESTRING, 4326),
    distance_km   INTEGER,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_routes_geometry
    ON routes USING GIST (geometry);

-- ------------------------------------------------------------- bookings ----

CREATE TABLE IF NOT EXISTS bookings (
    id             BIGSERIAL PRIMARY KEY,
    user_id        BIGINT       NOT NULL REFERENCES users (id),
    restaurant_id  BIGINT       NOT NULL REFERENCES restaurants (id),
    route_id       BIGINT       REFERENCES routes (id),
    -- When the traveller expects to ARRIVE. Every time calculation derives
    -- from this. Renamed from booking_time, which read as a creation stamp.
    arrival_time   TIMESTAMPTZ  NOT NULL,
    -- arrival_time - restaurant.avg_prep_time_minutes. Last moment the
    -- restaurant can still confirm and cook in time.
    cutoff_time    TIMESTAMPTZ  NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'pending',
    -- [{"name": ..., "qty": ..., "price": ...}] with prices RESOLVED SERVER-SIDE
    -- and frozen here, so a later menu change cannot alter a placed order.
    items          JSONB        NOT NULL,
    total_price    DECIMAL(10, 2) NOT NULL,
    notes          TEXT,
    payment_status VARCHAR(20)  NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT ck_bookings_status
        CHECK (status IN ('pending', 'confirmed', 'ready', 'handed_over', 'cancelled')),
    CONSTRAINT ck_bookings_payment_status
        CHECK (payment_status IN ('pending', 'paid')),
    CONSTRAINT ck_bookings_total_nonneg
        CHECK (total_price >= 0),
    -- Cheap structural guard; the real validation is in the application layer.
    CONSTRAINT ck_bookings_items_is_array
        CHECK (jsonb_typeof(items) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_bookings_restaurant_status
    ON bookings (restaurant_id, status);

CREATE INDEX IF NOT EXISTS idx_bookings_user
    ON bookings (user_id);

-- Supports the dashboard queue, which sorts open orders by urgency.
CREATE INDEX IF NOT EXISTS idx_bookings_cutoff
    ON bookings (cutoff_time) WHERE status IN ('pending', 'confirmed');

-- -------------------------------------------------------------- ratings ----

CREATE TABLE IF NOT EXISTS ratings (
    id                  BIGSERIAL PRIMARY KEY,
    -- UNIQUE enforces one rating per booking at the database level rather than
    -- relying on the application to check first.
    booking_id          BIGINT   NOT NULL UNIQUE REFERENCES bookings (id),
    user_id             BIGINT   NOT NULL REFERENCES users (id),
    restaurant_id       BIGINT   NOT NULL REFERENCES restaurants (id),
    hygiene_score       SMALLINT NOT NULL,
    food_quality_score  SMALLINT NOT NULL,
    timeliness_score    SMALLINT NOT NULL,
    comment             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT ck_ratings_hygiene      CHECK (hygiene_score      BETWEEN 1 AND 5),
    CONSTRAINT ck_ratings_food_quality CHECK (food_quality_score BETWEEN 1 AND 5),
    CONSTRAINT ck_ratings_timeliness   CHECK (timeliness_score   BETWEEN 1 AND 5)
);

CREATE INDEX IF NOT EXISTS idx_ratings_restaurant
    ON ratings (restaurant_id);

-- ------------------------------------------------------- bus_gps_events ----

-- Reserved for the Phase 3 ETA model. Nothing reads or writes this in MVP —
-- creating it now costs nothing and avoids a migration later (ADR-0010).
CREATE TABLE IF NOT EXISTS bus_gps_events (
    id           BIGSERIAL PRIMARY KEY,
    route_id     BIGINT      REFERENCES routes (id),
    vehicle_id   VARCHAR(50) NOT NULL,
    location     GEOGRAPHY(POINT, 4326) NOT NULL,
    recorded_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gps_route_time
    ON bus_gps_events (route_id, recorded_at DESC);
