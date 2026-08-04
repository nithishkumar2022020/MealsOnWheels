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
| Hosting (MVP) | Render | Free tier PostgreSQL + Redis + web service |

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
│   ├── scripts/
│   │   ├── migrate.py       # Applies migrations against DATABASE_URL
│   │   └── seed.py          # Routes, restaurants, test user
│   ├── tests/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── mobile/                  # Flutter app
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

- `GET /api/restaurants/search?latitude&longitude&radius_km[&route_id]`
- Pipeline:
  1. Check Redis cache key `restaurants:{lat}:{lon}:{radius}`. Hit → return with
     `cached: true`
  2. Query local `restaurants` by PostGIS radius
     ([04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md) §5.1)
  3. Query Overpass for OSM `amenity=restaurant` nodes near the coordinates
  4. **Upsert each Overpass POI into `restaurants` keyed on `osm_id`**
     ([04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md) §3.2.1) so every result carries a
     real integer `id` and is bookable
  5. Merge and dedupe local + promoted rows, order by distance
  6. Cache the result with a 6-hour TTL (§5.5)
- **Degradation:** if Overpass times out or errors, return step 2's results alone. Search
  never fails because an external service did — it returns less.
- The upsert in step 4 is the only write on this read path. It is idempotent, so a repeated
  search does not duplicate rows.

### 4.4 Booking module (`models/booking.py`, `routers/bookings.py`)

- Create booking with items JSON, compute `cutoff_time`
- State machine enforcement (see [01_PRODUCT_SPEC.md](./01_PRODUCT_SPEC.md))
- Notification hook on create (console stub → SMTP email)

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

For routes with stored polyline geometry, restaurants are selected by distance from the
route line rather than from a single point.

**Canonical query:** [04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md) §5.2. It is defined
there once so the two documents cannot drift; do not duplicate the SQL here.

**Buffer:** Default 15 km (`radius_km=15`).

**Index note:** `restaurants.location` is already `GEOGRAPHY`, so it must not be re-cast.
`routes.geometry` is `GEOMETRY(LINESTRING, 4326)` and casting it to `geography` inline
discards the `idx_routes_geometry` GiST index — see §5.2 of the database design for the
form that keeps the index usable.

**Current implementation:** Point-radius search around the traveller's coordinates plus an
Overpass supplement ([04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md) §5.1). The corridor
query lands once route polylines are seeded — Stage 16 in
[14_BUILD_PLAN.md](./14_BUILD_PLAN.md).

### 5.2 Cutoff, lead time, and ready-by calculation

```python
prep = restaurant.avg_prep_time_minutes or 30

# Reject before computing anything: the restaurant cannot physically make the window.
if arrival_time < now + timedelta(minutes=prep):
    raise ArrivalTooSoon

cutoff_time = arrival_time - timedelta(minutes=prep)
ready_by = arrival_time - timedelta(minutes=5)
```

The lead-time floor is `avg_prep_time_minutes`, not a flat 30. Without it a booking placed
minutes ahead yields a `cutoff_time` already in the past — a booking nobody can fulfil.

A `pending` booking whose `cutoff_time` passes without confirmation **stays `pending`** and
is flagged overdue on the dashboard. Nothing auto-rejects it in MVP; a human decides.

### 5.3 Order pricing

```python
menu = get_menu(restaurant_id)          # server-owned, see 05_API_SPEC §6.2
prices = {item["name"]: item["price"] for item in menu}

for line in request.items:              # request carries name + qty only
    if line.name not in prices:
        raise ValidationError(f"'{line.name}' is not on this restaurant's menu")

resolved = [{"name": l.name, "qty": l.qty, "price": prices[l.name]} for l in request.items]
total_price = sum(l["price"] * l["qty"] for l in resolved)
```

`resolved` is what gets persisted to `bookings.items`, freezing the unit prices at order
time. The client never supplies a price; a `price` key in the request is rejected outright
by `extra="forbid"`.

### 5.4 Rating aggregation

```python
composite = (hygiene_score + food_quality_score + timeliness_score) / 3
```

`restaurants.composite_rating` is the **plain mean** of every rating's composite, with
`rating_count` tracking how many. Both update incrementally when a rating is created — no
full-table scan.

Outlier exclusion is deliberately **not** done. The original design discarded ratings more
than 2σ from the mean, which is unsound at these sample sizes: σ is degenerate at n ≤ 2, and
at n = 5 a single honest 1-star review gets thrown away. Genuine outlier handling belongs
with rating moderation and fraud detection in Phase 2
([13_ROADMAP.md](./13_ROADMAP.md) §4).

### 5.5 Cache key design

| Key pattern | TTL | Content |
|-------------|-----|---------|
| `nominatim:{lat}:{lon}` | 30 days | Reverse geocode JSON |
| `restaurants:{lat}:{lon}:{radius}` | 6 hours | Search result array |
| `otp:{phone}` | 5 min | OTP session (Phase 2) |

**Why 6 hours, not 7 days:** a restaurant that registers itself must become discoverable
within a usable timeframe. At a 7-day TTL a new dhaba stays invisible for a week, and the
only documented invalidation was a manual flush. Six hours bounds the staleness without
losing the Overpass-load reduction the cache exists for.

`route_id` is not part of the search cache key — the MVP search is point-radius and does not
read it (see §5.1). Adding it to the key would fragment the cache across routes that return
identical results.

---

## 6. Integration Specifications

### 6.1 Nominatim

- Endpoint: configurable `NOMINATIM_BASE_URL` (default public with User-Agent)
- Rate limit: **1 request/second** client-side throttle
- Required header: `User-Agent: MealsOnWheels/1.0 (+https://github.com/nithishkumar2022020/MealsOnWheels)`
  — set from the `NOMINATIM_USER_AGENT` env var. Nominatim's usage policy requires a
  genuine identifying agent and blocks generic or placeholder values, so this must not be
  left as an example string.

**Usage policy, not just rate limits:** the public Nominatim and Overpass instances
prohibit sustained application traffic regardless of throttling. The 1 req/sec throttle
keeps development compliant; a public launch requires self-hosting both (or a paid
provider). Tracked as Stage 19 in [14_BUILD_PLAN.md](./14_BUILD_PLAN.md).

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
| Latency | Restaurant search (cache hit) | P95 < 800 ms; typically < 100 ms |
| Latency | Restaurant search (cache miss) | P95 < 5 s |
| Latency | Restaurant search (Redis unavailable) | P95 < 5 s — every request behaves as a cache miss |
| Latency | Booking create | P95 < 500 ms |
| Concurrency | MVP | 50 concurrent users |
| Data retention | Bookings, ratings | 2 years (policy target — see note) |
| Backup | PostgreSQL | Daily automated, 7-day retention (Render free tier) |
| i18n | MVP | English only; Hindi Phase 2 |
| Accessibility | Mobile + dashboard | WCAG 2.1 AA ([07_UI_UX_GUIDELINES.md](./07_UI_UX_GUIDELINES.md)) |

**Latency:** P95 < 800 ms on a cache hit is the requirement. Cache hits normally land well
under 100 ms; that is an expectation, not a separate target. These figures assume Redis is
available — the degraded row above applies when it is not.

**Retention:** 2 years is the *policy*, and the current infrastructure does not meet it. The
Render free tier keeps 7 days of backups, so a data loss older than a week is unrecoverable.
Honouring the policy requires a paid tier or external backup export; until then, do not
represent the platform as a 2-year system of record.

**Measurability:** every P95 target here requires request timing to exist. MVP logs
`duration_ms`, `route`, `status_code`, and `cache_hit` per request as structured JSON
([12_DEPLOYMENT.md](./12_DEPLOYMENT.md) §8.2), which is enough to compute these percentiles
from logs. Prometheus/Grafana remains Phase 2, but the targets are not unmeasurable in the
meantime.

---

## 8. Environment Variables

Documented in `backend/.env.example` and [12_DEPLOYMENT.md](./12_DEPLOYMENT.md):

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (asyncpg driver) |
| `JWT_SECRET` | Yes | HS256 signing secret (≥ 32 bytes) |
| `ENVIRONMENT` | Yes | `development` \| `test` \| `production`. Gates the OTP stub, the dashboard token, and the API docs — so it has no default |
| `REDIS_URL` | No | Redis URL; omit to run without cache |
| `JWT_EXPIRE_HOURS` | No | Default 24 |
| `NOMINATIM_BASE_URL` | No | Default public Nominatim |
| `NOMINATIM_USER_AGENT` | No | Identifying agent required by Nominatim's usage policy (§6.1) |
| `OVERPASS_URL` | No | Default public Overpass |
| `CORS_ORIGINS` | No | Comma-separated allowed origins; never `*` in production |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `EMAIL_FROM` | No | Notification email; unset logs notifications instead of sending |

`ENVIRONMENT` deliberately has **no default**. Three security controls key off it, and a
value that defaults to `development` would mean a deploy that forgot to set it silently
enables the OTP stub in production. Startup fails if it is unset or unrecognised.

Startup also fails if `ENVIRONMENT=production` and `JWT_SECRET` is shorter than 32 bytes or
matches a known development placeholder. Fail at boot, not at first login.

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
