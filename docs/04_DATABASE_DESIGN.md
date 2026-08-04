# Database Design — Highway Food Pre-Booking Platform

**Document version:** 1.0  
**Last updated:** 2026-07-25  
**Parent:** [02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md)

---

## 1. Overview

PostgreSQL 16 with **PostGIS 3.4** is the system of record. All transactional data (users, restaurants, bookings, ratings) lives here. Redis is cache-only and never authoritative.

**Design principles:**

- Normalize core entities; store booking line items as JSONB in MVP for speed
- Use PostGIS `GEOGRAPHY(POINT, 4326)` for restaurant locations
- Use explicit status history table in Phase 2; MVP stores current status on booking row
- All timestamps in UTC (`TIMESTAMPTZ`)

---

## 2. Entity-Relationship Diagram

```mermaid
erDiagram
  users ||--o{ bookings : places
  restaurants ||--o{ bookings : receives
  routes ||--o{ bookings : "associated_with"
  bookings ||--o| ratings : "has_one"
  restaurants ||--o{ ratings : "aggregated_in"

  users {
    bigint id PK
    varchar phone UK
    varchar email
    varchar name
    timestamptz created_at
    timestamptz updated_at
  }

  restaurants {
    bigint id PK
    varchar name
    varchar phone
    varchar email
    text address
    geography location
    decimal composite_rating
    int rating_count
    int avg_prep_time_minutes
    boolean is_active
    bigint osm_id UK
    timestamptz created_at
    timestamptz updated_at
  }

  routes {
    bigint id PK
    varchar name
    varchar origin_name
    varchar dest_name
    geography origin_point
    geography dest_point
    geometry geometry
    int distance_km
    timestamptz created_at
    timestamptz updated_at
  }

  bookings {
    bigint id PK
    bigint user_id FK
    bigint restaurant_id FK
    bigint route_id FK
    timestamptz arrival_time
    timestamptz cutoff_time
    varchar status
    jsonb items
    decimal total_price
    text notes
    varchar payment_status
    timestamptz created_at
    timestamptz updated_at
  }

  ratings {
    bigint id PK
    bigint booking_id FK UK
    bigint user_id FK
    bigint restaurant_id FK
    smallint hygiene_score
    smallint food_quality_score
    smallint timeliness_score
    text comment
    timestamptz created_at
  }

  bus_gps_events {
    bigint id PK
    bigint route_id FK
    varchar vehicle_id
    geography location
    timestamptz recorded_at
  }
```

---

## 3. Table Definitions

### 3.1 `users`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGSERIAL` | PK | Internal user ID |
| `phone` | `VARCHAR(20)` | UNIQUE NOT NULL | E.164 format, e.g. `+919876543210` |
| `email` | `VARCHAR(255)` | NULL | Optional; used for notifications |
| `name` | `VARCHAR(100)` | NULL | Display name |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT now() | |

**Indexes:** `UNIQUE (phone)`

### 3.2 `restaurants`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGSERIAL` | PK | |
| `name` | `VARCHAR(200)` | NOT NULL | |
| `phone` | `VARCHAR(20)` | NOT NULL | Contact number |
| `email` | `VARCHAR(255)` | NULL | Notification target |
| `address` | `TEXT` | NULL | Human-readable address |
| `location` | `GEOGRAPHY(POINT, 4326)` | NOT NULL | WGS84 lat/lon |
| `composite_rating` | `DECIMAL(3,2)` | NOT NULL DEFAULT 0 | Mean of all three rating dimensions, 0–5. `0` means unrated |
| `rating_count` | `INTEGER` | NOT NULL DEFAULT 0 | Ratings behind `composite_rating`; lets the mean update incrementally |
| `avg_prep_time_minutes` | `INTEGER` | NOT NULL DEFAULT 30 | Cutoff calc **and** the minimum booking lead time |
| `is_active` | `BOOLEAN` | NOT NULL DEFAULT true | Soft disable; inactive restaurants are unsearchable and unbookable |
| `osm_id` | `BIGINT` | UNIQUE NULL | Set when the row was promoted from an OSM POI; `NULL` for manually onboarded restaurants |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT now() | |

**On `composite_rating` naming:** this column previously held the composite score under the
name `hygiene_rating`, which read as a hygiene-only figure and collided with the genuinely
hygiene-only `average_hygiene` in [05_API_SPEC.md](./05_API_SPEC.md) §9.2. Two different
quantities, near-identical names.

**On `osm_id`:** required so an Overpass search result can be promoted into a real
restaurant row when a traveller books it. Without it the same OSM POI inserts repeatedly.
See §3.2.1.

**Indexes:**

```sql
CREATE INDEX idx_restaurants_location ON restaurants USING GIST (location);
CREATE INDEX idx_restaurants_active ON restaurants (is_active) WHERE is_active = true;
CREATE UNIQUE INDEX idx_restaurants_osm_id ON restaurants (osm_id) WHERE osm_id IS NOT NULL;
```

#### 3.2.1 Promoting OSM results into `restaurants`

A search may return POIs that came from Overpass and have no row in this table. Those
results must still be bookable, and `bookings.restaurant_id` is a `NOT NULL` foreign key —
so an OSM result cannot be returned with a null id and booked later.

**Resolution:** every Overpass POI that survives filtering is upserted into `restaurants`
at search time, keyed on `osm_id`:

```sql
INSERT INTO restaurants (name, phone, address, location, osm_id, avg_prep_time_minutes)
VALUES (:name, '', :address, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
        :osm_id, 30)
ON CONFLICT (osm_id) WHERE osm_id IS NOT NULL DO UPDATE
  SET name       = EXCLUDED.name,
      address    = COALESCE(EXCLUDED.address, restaurants.address),
      updated_at = now()
RETURNING id;
```

**The `WHERE osm_id IS NOT NULL` in the conflict target is required, not decoration.**
`idx_restaurants_osm_id` is a *partial* unique index (§3.2), and PostgreSQL will not infer a
partial index as an arbiter unless the conflict target repeats its predicate. Without it the
statement fails outright with `no unique or exclusion constraint matching the ON CONFLICT
specification` — the upsert cannot run at all. An earlier draft of this section omitted the
predicate and so could never have executed against the index §3.2 defines.

Every search result therefore carries a real integer `id`. Consequences:

- `phone` is empty for OSM-derived rows — they were never onboarded, so there is nobody to
  notify. The booking still succeeds; the notification stub logs that it had no contact.
- `composite_rating` is `0` and `rating_count` is `0` until someone rates them. The API
  reports `composite_rating: null` rather than `0` for unrated restaurants so clients do not
  render a zero-star rating.
- `avg_prep_time_minutes` defaults to 30, which also sets their minimum booking lead time.
- The `source` field in search responses (`"local"` / `"osm"`) is derived from whether
  `osm_id IS NULL`, not stored separately.

The alternative — returning `id: null` and blocking booking on OSM results — was rejected
because Overpass supplementation exists precisely to cover corridors where seeded data is
thin, so it would disable booking exactly where it is most needed.

### 3.3 `routes`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGSERIAL` | PK | |
| `name` | `VARCHAR(100)` | NOT NULL | e.g. `Delhi-Chandigarh` |
| `origin_name` | `VARCHAR(100)` | NOT NULL | |
| `dest_name` | `VARCHAR(100)` | NOT NULL | |
| `origin_point` | `GEOGRAPHY(POINT, 4326)` | NOT NULL | |
| `dest_point` | `GEOGRAPHY(POINT, 4326)` | NOT NULL | |
| `geometry` | `GEOMETRY(LINESTRING, 4326)` | NULL | Route polyline from OSRM |
| `distance_km` | `INTEGER` | NULL | Approximate |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT now() | |

**Indexes:**

```sql
CREATE INDEX idx_routes_geometry ON routes USING GIST (geometry);
```

### 3.4 `bookings`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGSERIAL` | PK | |
| `user_id` | `BIGINT` | FK → users(id) NOT NULL | |
| `restaurant_id` | `BIGINT` | FK → restaurants(id) NOT NULL | |
| `route_id` | `BIGINT` | FK → routes(id) NULL | |
| `arrival_time` | `TIMESTAMPTZ` | NOT NULL | Expected arrival |
| `cutoff_time` | `TIMESTAMPTZ` | NOT NULL | Last moment to confirm |
| `status` | `VARCHAR(20)` | NOT NULL DEFAULT 'pending' | State machine value |
| `items` | `JSONB` | NOT NULL | `[{name, qty, price}]` |
| `total_price` | `DECIMAL(10,2)` | NOT NULL | |
| `notes` | `TEXT` | NULL | Special instructions |
| `payment_status` | `VARCHAR(20)` | DEFAULT 'pending' | MVP: always pending |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT now() | |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT now() | |

**Status enum values:** `pending`, `confirmed`, `ready`, `handed_over`, `cancelled`

**Indexes:**

```sql
CREATE INDEX idx_bookings_restaurant_status ON bookings (restaurant_id, status);
CREATE INDEX idx_bookings_user ON bookings (user_id);
CREATE INDEX idx_bookings_cutoff ON bookings (cutoff_time) WHERE status IN ('pending', 'confirmed');
```

**Items JSONB example:**

```json
[
  {"name": "Paneer Paratha", "qty": 2, "price": 80.00},
  {"name": "Lassi", "qty": 1, "price": 40.00}
]
```

### 3.5 `ratings`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGSERIAL` | PK | |
| `booking_id` | `BIGINT` | FK → bookings(id) UNIQUE NOT NULL | One rating per booking |
| `user_id` | `BIGINT` | FK → users(id) NOT NULL | |
| `restaurant_id` | `BIGINT` | FK → restaurants(id) NOT NULL | |
| `hygiene_score` | `SMALLINT` | CHECK 1–5 | |
| `food_quality_score` | `SMALLINT` | CHECK 1–5 | |
| `timeliness_score` | `SMALLINT` | CHECK 1–5 | |
| `comment` | `TEXT` | NULL | |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT now() | |

### 3.6 `bus_gps_events` (extension point)

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGSERIAL` | PK | |
| `route_id` | `BIGINT` | FK → routes(id) | |
| `vehicle_id` | `VARCHAR(50)` | NOT NULL | Fleet identifier |
| `location` | `GEOGRAPHY(POINT, 4326)` | NOT NULL | GPS fix |
| `recorded_at` | `TIMESTAMPTZ` | NOT NULL | Event timestamp |

**Purpose:** Ingest-only in MVP for future ETA model. No application logic reads this table in MVP.

**Index:**

```sql
CREATE INDEX idx_gps_route_time ON bus_gps_events (route_id, recorded_at DESC);
```

---

## 4. Phase 2 Tables (Not in MVP Migration)

Documented here for forward compatibility; do not create in `001_create_tables.sql`.

### 4.1 `menu_items`

Normalized menu with R2 image URLs. MVP uses hardcoded/dummy menus in API responses.

### 4.2 `order_status_history`

Audit trail: `(booking_id, from_status, to_status, changed_by, changed_at)`.

---

## 5. Sample Spatial Queries

### 5.1 Restaurants within radius (MVP)

```sql
SELECT id, name,
       ST_Distance(location, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS distance_m
FROM restaurants
WHERE is_active = true
  AND ST_DWithin(
        location,
        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
        :radius_meters
      )
ORDER BY distance_m;
```

### 5.2 Restaurants along route corridor (canonical)

This is the single definition of the corridor query. [02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md)
§5.1 refers here rather than duplicating it.

```sql
SELECT r.id,
       r.name,
       ST_Distance(r.location, rt.geog) AS distance_m
FROM (
       SELECT geometry::geography AS geog
       FROM routes
       WHERE id = :route_id
     ) rt,
     restaurants r
WHERE r.is_active = true
  AND ST_DWithin(r.location, rt.geog, :buffer_meters)
ORDER BY distance_m;
```

**Why this shape:**

- `restaurants.location` is already `GEOGRAPHY(POINT, 4326)`. Casting it again
  (`r.location::geography`) is redundant and can prevent use of `idx_restaurants_location`.
- The route geometry is cast to `geography` **once**, in a subquery, rather than per-row in
  the `WHERE` clause. Casting a column inline makes the expression non-indexable; hoisting
  it lets the planner treat it as a constant and use the GiST index on
  `restaurants.location`.
- `ST_Distance` on two `geography` values returns metres along the spheroid, which is what
  the API reports as `distance_km`. Do not mix in `ST_ClosestPoint` — it is a *geometry*
  function and feeding it geography arguments forces an implicit cast back to planar
  degrees, producing distances that are wrong at Indian latitudes.

Verify with `EXPLAIN ANALYZE` that an index scan on `idx_restaurants_location` appears; a
sequential scan means the cast was reintroduced somewhere.

---

## 6. Migration Strategy

| Phase | Tool | Location |
|-------|------|----------|
| MVP | Raw SQL | `backend/migrations/001_create_tables.sql` |
| Post-MVP | Alembic | `backend/alembic/versions/` |

**Migration execution:**

```bash
# Local
docker compose exec postgres psql -U mealsonwheels -d highway_food_booking \
  -f /migrations/001_create_tables.sql

# Production (Render)
python scripts/migrate.py
```

**Rules:**

- Migrations are forward-only while the schema is pre-release (no down migrations). Roll
  back by restoring a backup, not by reversing a migration
- Always enable PostGIS before creating spatial columns:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

- `001_create_tables.sql` is idempotent (`CREATE TABLE IF NOT EXISTS`,
  `CREATE INDEX IF NOT EXISTS`) so re-running it against an existing database is safe

### 6.1 Adopting Alembic later

The hand-written SQL migration must be **baselined**, not re-derived, when Alembic arrives
in Phase 1. Without this step Alembic's first autogenerate sees an empty version history,
compares an empty model of the database against the live schema, and emits a migration that
tries to create every table that already exists.

Procedure:

1. `alembic init backend/alembic`; point `target_metadata` at the SQLAlchemy `Base`.
2. Hand-write `0001_baseline.py` whose `upgrade()` is **empty** — it represents the schema
   that `001_create_tables.sql` already produced.
3. On every existing database (local, Render): `alembic stamp 0001_baseline`. This records
   the revision without executing anything.
4. Only then run `alembic revision --autogenerate` for the next real change, and read the
   generated diff before applying it. PostGIS columns in particular are frequently
   mis-detected — `geoalchemy2` must be imported in `env.py` or autogenerate will propose
   dropping and recreating every spatial column.
5. Fresh databases from that point run `alembic upgrade head` instead of the raw SQL file.
   Keep `001_create_tables.sql` in the repository as the historical record; do not edit it.

---

## 7. Seed Data (MVP)

| Entity | Count | Notes |
|--------|-------|-------|
| Routes | 5 | Delhi-Chandigarh, Mumbai-Pune, Bangalore-Hyderabad, Chennai-Bangalore, Jaipur-Delhi |
| Restaurants | 10 | Along Delhi-Chandigarh corridor |
| Users | 1 | Test user `+919876543210` |

Seed script: `backend/scripts/seed.py`. Restaurant coordinates must fall within the default
15 km radius of the canonical demo search point `29.02, 77.02`
([05_API_SPEC.md](./05_API_SPEC.md) §6.1) — otherwise every documented search example
returns nothing.

---

## 8. Data Integrity Rules

- FK constraints enforced at DB level
- Booking `status` transitions validated in application layer ([01_PRODUCT_SPEC.md](./01_PRODUCT_SPEC.md))
- Rating requires booking `status = handed_over`
- Phone numbers normalized to E.164 before insert
- `total_price` computed server-side from items; client-supplied total ignored

---

## 9. Backup & Retention

- Render managed PostgreSQL: daily automated backups (free tier: 7-day retention)
- No PII encryption at rest in MVP; Phase 2: column-level encryption for phone if required by compliance
- GDPR-style deletion: soft-delete user, anonymize phone (Phase 2)

---

## 10. Related Documents

- [05_API_SPEC.md](./05_API_SPEC.md) — API field mappings
- [03_SYSTEM_ARCHITECTURE.md](./03_SYSTEM_ARCHITECTURE.md) — Data flow
- [08_DEVELOPMENT_GUIDELINES.md](./08_DEVELOPMENT_GUIDELINES.md) — Local DB setup
- [12_DEPLOYMENT.md](./12_DEPLOYMENT.md) — Production migrations
