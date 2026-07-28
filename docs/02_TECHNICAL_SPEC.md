# Technical Specification — Highway Food Pre-Booking Platform

**Document version:** 1.0  
**Last updated:** 2026-07-25  
**Parent:** [00_PROJECT_CHARTER.md](./00_PROJECT_CHARTER.md)  
**Companion:** [03_SYSTEM_ARCHITECTURE.md](./03_SYSTEM_ARCHITECTURE.md), [05_API_SPEC.md](./05_API_SPEC.md)

---

## 1. Purpose

This document specifies **how** the system is built: technology choices, module boundaries, core algorithms, and non-functional requirements. Product behavior is defined in [01_PRODUCT_SPEC.md](./01_PRODUCT_SPEC.md).

---

## 2. Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Mobile client | Flutter (Dart) | Single codebase for Android/iOS/Web; strong map plugin ecosystem |
| Backend API | FastAPI (Python 3.11+) | Async I/O for geo/cache workloads; native Python ML path for Phase 2 ETA models |
| Database | PostgreSQL 16 + PostGIS 3.4 | Relational integrity + geospatial queries in one store |
| Cache | Redis 7 | Search result cache, OTP session, rate limiting, refresh token store |
| Object storage | Cloudflare R2 | S3-compatible; zero egress fees for menu images (Phase 2) |
| Maps (client) | MapLibre GL | OSS; no Google Maps billing |
| Tiles | OpenStreetMap | Free tile sources (with usage policy compliance) |
| Geocoding | Nominatim (self-hosted or public with throttle) | OSS reverse geocoding |
| Routing | OSRM (Docker, India extract) | Route geometry + duration; MapLibre cannot route alone |
| Auth | JWT (python-jose) + phone OTP | Stateless access tokens; Redis-backed refresh (Phase 2) |
| Containerization | Docker + docker-compose | Reproducible local and production environments |
| CI/CD | GitHub Actions | Lint, test, build image, deploy |
| Hosting (MVP sprint) | Render | Free tier PostgreSQL + Redis + web service |

**Why FastAPI over Node.js Express:** Async performance, Pydantic validation, OpenAPI generation, and direct path to Python ML services without a rewrite. See ADR-0001 in [09_ARCHITECTURE_DECISIONS.md](./09_ARCHITECTURE_DECISIONS.md).

---

## 3. Repository Structure

```
MealsOnWheels/
├── docs/                    # This documentation set
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entrypoint
│   │   ├── config.py        # Settings (pydantic-settings)
│   │   ├── db.py            # Async SQLAlchemy engine/session
│   │   ├── cache.py         # Redis client + fallback
│   │   ├── core/
│   │   │   └── security.py  # JWT, password hashing
│   │   ├── deps.py          # Auth dependencies
│   │   ├── models/          # SQLAlchemy ORM models
│   │   ├── schemas/         # Pydantic request/response
│   │   ├── routers/         # Route handlers
│   │   └── services/        # Nominatim, Overpass, notifications
│   ├── migrations/          # SQL migrations
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── mobile/                  # Flutter app (Stream D)
├── dashboard/               # Restaurant web console (Phase 2 or Flutter tab)
├── docker-compose.yml       # postgres, redis, osrm (optional), api
└── .github/workflows/       # CI/CD
```

---

## 4. Module Breakdown

### 4.1 Auth module (`routers/auth.py`)

- `POST /api/auth/register` — create user by phone
- `POST /api/auth/login` — verify OTP, issue JWT
- MVP OTP: hardcoded `123456` (no SMS provider)
- JWT claims: `sub` (user_id), `phone`, `exp`, `iat`

### 4.2 Route module (`models/route.py`, `routers/routes.py`)

- CRUD for predefined routes (Delhi-Chandigarh, Mumbai-Pune, etc.)
- Stores polyline geometry (PostGIS `LINESTRING`) for corridor queries
- Seeded with 5 test routes in MVP

### 4.3 Restaurant search module (`services/overpass.py`, `routers/restaurants.py`)

- `GET /api/restaurants/search?route_id&latitude&longitude&radius_km`
- Pipeline:
  1. Check Redis cache key `restaurants:{route_id}:{lat}:{lon}:{radius}`
  2. Query Overpass API for OSM `amenity=restaurant` nodes near coordinates
  3. Join with local `restaurants` table for `hygiene_rating`, `avg_prep_time_minutes`
  4. Fallback: if Overpass fails, return DB-seeded restaurants only
  5. Cache result TTL 7 days

### 4.4 Booking module (`models/booking.py`, `routers/bookings.py`)

- Create booking with items JSON, compute `cutoff_time`
- State machine enforcement (see [01_PRODUCT_SPEC.md](./01_PRODUCT_SPEC.md))
- Notification hook on create (console stub → email in Stream E)

### 4.5 Dashboard module (`routers/dashboard.py`)

- Restaurant-scoped order listing and status transitions
- Stats aggregation endpoint

### 4.6 Ratings module (`models/rating.py`, `routers/ratings.py`)

- Per-booking rating with outlier exclusion (> 2 SD) on aggregate

### 4.7 Notifications module (`services/notifications.py`)

- Interface: `send_booking_confirmation`, `send_order_status_update`
- MVP: structured console logging
- Deploy: Nodemailer-equivalent via `aiosmtplib` + Mailgun/Gmail SMTP

---

## 5. Core Algorithms

### 5.1 Corridor restaurant search (production path)

For routes with stored polyline geometry:

```sql
SELECT r.*
FROM restaurants r
JOIN routes rt ON rt.id = :route_id
WHERE ST_DWithin(
  r.location::geography,
  rt.geometry::geography,
  :radius_meters
)
ORDER BY ST_Distance(r.location, ST_ClosestPoint(rt.geometry, r.location));
```

**Buffer:** Default 15 km (`radius_km=15`). Uses GiST index on `restaurants.location`.

**MVP sprint shortcut:** Point-radius search around traveller coordinates + Overpass supplement. PostGIS corridor query is Phase 1.5 once route polylines are seeded.

### 5.2 Cutoff and ready-by calculation

```python
cutoff_time = booking_time - timedelta(minutes=restaurant.avg_prep_time_minutes or 30)
ready_by = booking_time - timedelta(minutes=5)
```

### 5.3 Rating aggregation (outlier exclusion)

1. Fetch all ratings for restaurant
2. Compute mean μ and std σ for composite score `(hygiene + food_quality + timeliness) / 3`
3. Exclude ratings where `|score - μ| > 2σ`
4. Return mean of remaining scores

### 5.4 Cache key design

| Key pattern | TTL | Content |
|-------------|-----|---------|
| `nominatim:{lat}:{lon}` | 30 days | Reverse geocode JSON |
| `restaurants:{route_id}:{lat}:{lon}:{radius}` | 7 days | Search result array |
| `otp:{phone}` | 5 min | OTP session (Phase 2) |

---

## 6. Integration Specifications

### 6.1 Nominatim

- Endpoint: configurable `NOMINATIM_BASE_URL` (default public with User-Agent)
- Rate limit: **1 request/second** client-side throttle
- Required header: `User-Agent: MealsOnWheels/1.0 (contact@example.com)`

### 6.2 Overpass API

- Query template: nodes with `amenity=restaurant` within radius
- Rate limit: 1 req/sec
- Timeout: 10 s; on failure return `[]` and log warning

### 6.3 OSRM (optional local Docker)

- Profile: `car`
- Used for route polyline generation when seeding routes
- Endpoint: `http://osrm:5000/route/v1/driving/{lon1},{lat1};{lon2},{lat2}`

### 6.4 Cloudflare R2 (Phase 2)

- S3-compatible API via `boto3`
- Bucket: `mealsonwheels-assets`
- Use for menu images only; not required in MVP

---

## 7. Non-Functional Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| Availability | MVP demo uptime | 99% (Render free tier cold starts excluded) |
| Latency | Restaurant search (cache hit) | P95 < 800 ms |
| Latency | Restaurant search (cache miss) | P95 < 5 s |
| Latency | Booking create | P95 < 500 ms |
| Concurrency | MVP | 50 concurrent users |
| Data retention | Bookings, ratings | 2 years |
| Backup | PostgreSQL | Daily automated (Render managed) |
| i18n | MVP | English only; Hindi Phase 2 |
| Accessibility | Mobile + dashboard | WCAG 2.1 AA ([07_UI_UX_GUIDELINES.md](./07_UI_UX_GUIDELINES.md)) |

---

## 8. Environment Variables

Documented in `backend/.env.example` and [12_DEPLOYMENT.md](./12_DEPLOYMENT.md):

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | No | Redis URL; omit for DB-only fallback |
| `JWT_SECRET` | Yes | HS256 signing secret (≥ 32 bytes) |
| `JWT_EXPIRE_HOURS` | No | Default 24 |
| `NOMINATIM_BASE_URL` | No | Default public Nominatim |
| `OVERPASS_URL` | No | Default public Overpass |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |
| `ENVIRONMENT` | No | `development` \| `production` |

---

## 9. Error Handling Conventions

- All API errors return JSON: `{ "detail": "...", "code": "ERROR_CODE" }`
- HTTP status mapping per [05_API_SPEC.md](./05_API_SPEC.md)
- Unhandled exceptions logged with request ID; 500 returned without stack trace in production
- External service failures (Overpass, Nominatim) degrade gracefully — never fail entire search

---

## 10. Extension Points (Future AI / Payments)

| Extension | Interface location | Phase |
|-----------|-------------------|-------|
| ETA prediction model | `services/eta.py` — `predict_arrival(route_id, gps_points)` | Phase 3 |
| Demand forecasting | `services/demand.py` — batch job reading `bookings` | Phase 3 |
| Payment provider | `services/payments.py` — `create_intent()`, `capture()` | Phase 2 |
| SMS OTP | `services/otp.py` — `send_otp(phone)` | Phase 2 |

**Rule:** MVP code may stub these modules but must not embed ML or payment logic inline in routers.

---

## 11. Related Documents

- [03_SYSTEM_ARCHITECTURE.md](./03_SYSTEM_ARCHITECTURE.md) — Diagrams and data flow
- [04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md) — Schema details
- [08_DEVELOPMENT_GUIDELINES.md](./08_DEVELOPMENT_GUIDELINES.md) — Local dev setup
- [09_ARCHITECTURE_DECISIONS.md](./09_ARCHITECTURE_DECISIONS.md) — ADRs
- [10_SECURITY.md](./10_SECURITY.md) — Security controls
