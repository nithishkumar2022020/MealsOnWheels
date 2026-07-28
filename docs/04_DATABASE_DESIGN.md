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
    decimal hygiene_rating
    int avg_prep_time_minutes
    boolean is_active
    timestamptz created_at
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
  }

  bookings {
    bigint id PK
    bigint user_id FK
    bigint restaurant_id FK
    bigint route_id FK
    timestamptz booking_time
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
| `hygiene_rating` | `DECIMAL(3,2)` | DEFAULT 0 | Aggregated 0–5 |
| `avg_prep_time_minutes` | `INTEGER` | DEFAULT 30 | Used for cutoff calc |
| `is_active` | `BOOLEAN` | DEFAULT true | Soft disable |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT now() | |

**Indexes:**

```sql
CREATE INDEX idx_restaurants_location ON restaurants USING GIST (location);
CREATE INDEX idx_restaurants_active ON restaurants (is_active) WHERE is_active = true;
```

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
| `booking_time` | `TIMESTAMPTZ` | NOT NULL | Expected arrival |
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

### 5.2 Restaurants along route corridor (Phase 1.5)

```sql
SELECT r.id, r.name
FROM restaurants r
JOIN routes rt ON rt.id = :route_id
WHERE ST_DWithin(
  r.location,
  rt.geometry::geography,
  :buffer_meters
);
```

---

## 6. Migration Strategy

| Phase | Tool | Location |
|-------|------|----------|
| MVP sprint | Raw SQL | `backend/migrations/001_create_tables.sql` |
| Post-MVP | Alembic | `backend/alembic/versions/` |

**Migration execution:**

```bash
# Local
docker compose exec postgres psql -U mealsonwheels -d highway_food_booking \
  -f /migrations/001_create_tables.sql

# Production (Render)
npm run migrate:prod  # or python script invoking psql
```

**Rules:**

- Migrations are forward-only in sprint (no down migrations)
- Always enable PostGIS before creating spatial columns:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

---

## 7. Seed Data (MVP)

| Entity | Count | Notes |
|--------|-------|-------|
| Routes | 5 | Delhi-Chandigarh, Mumbai-Pune, Bangalore-Hyderabad, Chennai-Bangalore, Jaipur-Delhi |
| Restaurants | 10 | Along Delhi-Chandigarh corridor |
| Users | 1 | Test user `+919876543210` |

Seed script: `backend/scripts/seed.py` (Stream B deliverable)

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
