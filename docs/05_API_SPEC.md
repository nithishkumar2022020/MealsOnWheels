# API Specification — Highway Food Pre-Booking Platform

**Document version:** 1.0  
**Last updated:** 2026-07-25  
**Base URL:** `https://<host>/api` (production) | `http://localhost:8000/api` (local)

**Parent:** [02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md), [04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md)

---

## 1. Conventions

| Aspect | Standard |
|--------|----------|
| Protocol | HTTPS in production; HTTP local only |
| Format | JSON request/response bodies |
| Auth header | `Authorization: Bearer <jwt>` |
| Content-Type | `application/json` |
| Timestamps | ISO 8601 UTC (`2026-07-25T07:30:00Z`) |
| Phone numbers | E.164 (`+919876543210`) |
| Pagination | `?page=1&limit=20` (Phase 2; MVP returns full lists) |
| Versioning | Unversioned MVP; prefix `/api/v1` in Phase 2 |

---

## 2. Error Model

All errors return:

```json
{
  "detail": "Human-readable message",
  "code": "MACHINE_READABLE_CODE"
}
```

| HTTP Status | Code examples | When |
|-------------|---------------|------|
| 400 | `VALIDATION_ERROR`, `INVALID_STATUS_TRANSITION`, `ARRIVAL_TOO_SOON` | Bad input |
| 401 | `UNAUTHORIZED`, `INVALID_OTP`, `TOKEN_EXPIRED` | Auth failure |
| 403 | `FORBIDDEN`, `INVALID_RESTAURANT_TOKEN` | Insufficient permissions |
| 404 | `NOT_FOUND`, `USER_NOT_FOUND` | Resource missing |
| 409 | `DUPLICATE_RATING`, `PHONE_ALREADY_REGISTERED` | Conflicting state |
| 422 | `UNPROCESSABLE_ENTITY` | Pydantic validation |
| 429 | `RATE_LIMITED` | Throttle exceeded |
| 500 | `INTERNAL_ERROR` | Unhandled server error |
| 503 | `SERVICE_UNAVAILABLE` | Database unreachable, or OTP delivery unavailable in production |

---

## 3. Authentication Endpoints

### 3.1 POST `/auth/register`

Create a new user account.

**Auth required:** No

**Request:**

```json
{
  "phone": "+919876543210",
  "name": "Priya Sharma",
  "email": "priya@example.com"
}
```

**Response `201`:**

```json
{
  "id": 1,
  "phone": "+919876543210",
  "name": "Priya Sharma",
  "email": "priya@example.com",
  "created_at": "2026-07-25T08:00:00Z"
}
```

**Errors:** `409` if phone already registered

---

### 3.2 POST `/auth/login`

Verify OTP and receive JWT.

**Auth required:** No

**Request:**

```json
{
  "phone": "+919876543210",
  "otp": "123456"
}
```

**Response `200`:**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": 1,
    "phone": "+919876543210",
    "name": "Priya Sharma"
  }
}
```

**OTP verification is environment-gated.**

| `ENVIRONMENT` | Behaviour |
|---------------|-----------|
| `development` / `test` | The stub OTP `123456` is accepted. Anything else → `401 INVALID_OTP` |
| `production` | The stub is **rejected unconditionally**. With no SMS provider configured the endpoint returns `503 SERVICE_UNAVAILABLE` |

The stub must never be reachable in production, even by misconfiguration. The check is on
`ENVIRONMENT`, not on whether a provider happens to be configured — a missing provider is a
`503`, not a fallback to a constant password.

**Login does not create users.** An unrecognised phone returns `404 NOT_FOUND` with
`code: "USER_NOT_FOUND"`, directing the caller to `POST /auth/register` first.

An earlier draft auto-registered any unknown phone on first successful login. Combined with a
constant OTP, that let anyone mint an account and a 24-hour token for **any** phone number,
including one belonging to a real person — account creation under someone else's identity,
not merely a weak password. It also made `POST /auth/register`'s `409` branch unreachable.

**Errors:** `401 INVALID_OTP`, `404 NOT_FOUND` (`USER_NOT_FOUND`), `429 RATE_LIMITED`,
`503 SERVICE_UNAVAILABLE` (production, no SMS provider)

---

## 4. User Endpoints

### 4.1 GET `/user/profile`

**Auth required:** Yes

**Response `200`:**

```json
{
  "id": 1,
  "phone": "+919876543210",
  "name": "Priya Sharma",
  "email": "priya@example.com",
  "created_at": "2026-07-25T08:00:00Z"
}
```

---

## 5. Route Endpoints

### 5.1 GET `/routes`

List available travel routes.

**Auth required:** No — public read

**Response `200`:**

```json
{
  "routes": [
    {
      "id": 1,
      "name": "Delhi-Chandigarh",
      "origin_name": "Delhi",
      "dest_name": "Chandigarh",
      "origin_lat": 28.6139,
      "origin_lon": 77.2090,
      "dest_lat": 30.7333,
      "dest_lon": 76.7794,
      "distance_km": 245
    }
  ],
  "total_count": 5
}
```

**Geography flattening.** The database stores `origin_point` and `dest_point` as
`GEOGRAPHY(POINT, 4326)` ([04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md) §3.3). The API
flattens each into a scalar lat/lon pair so clients never parse WKB:

| DB column | API fields | Extraction |
|-----------|-----------|------------|
| `origin_point` | `origin_lat`, `origin_lon` | `ST_Y(origin_point::geometry)`, `ST_X(origin_point::geometry)` |
| `dest_point` | `dest_lat`, `dest_lon` | `ST_Y(dest_point::geometry)`, `ST_X(dest_point::geometry)` |
| `geometry` | *not exposed* | Route polyline is internal; corridor search uses it server-side |

`ST_X` is longitude and `ST_Y` is latitude — the opposite order to how coordinates are
written in `lat, lon` form. Getting this backwards puts Delhi in the Indian Ocean, so it is
covered by a seed assertion in the test fixtures
([11_TESTING.md](./11_TESTING.md) §6).

---

## 6. Restaurant Endpoints

### 6.1 GET `/restaurants/search`

Search restaurants near a point on a route.

**Auth required:** No — public read

**Query parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `latitude` | float | Yes | — | Search centre lat (−90 to 90) |
| `longitude` | float | Yes | — | Search centre lon (−180 to 180) |
| `radius_km` | float | No | 15 | Search radius, max 50 |
| `route_id` | int | No | — | Route context; recorded on the resulting booking, not used to filter |

`route_id` is **optional**. The current search is point-radius and does not read it — it was
previously marked required, which implied a corridor filter the MVP does not perform. It
becomes meaningful when corridor search lands (Stage 16 in
[14_BUILD_PLAN.md](./14_BUILD_PLAN.md)).

**Example:**

```
GET /api/restaurants/search?latitude=29.02&longitude=77.02&radius_km=15
```

**Canonical demo coordinate:** `29.02, 77.02` — on the NH-44 Delhi–Chandigarh corridor just
south of Murthal. This is the same point used by
[07_UI_UX_GUIDELINES.md](./07_UI_UX_GUIDELINES.md) §3.2 and the geospatial fixtures in
[11_TESTING.md](./11_TESTING.md) §6, and it is within radius of the seeded restaurants.
Use it in every example so documented requests actually return rows.

**Response `200`:**

```json
{
  "restaurants": [
    {
      "id": 1,
      "name": "Murthal Dhaba",
      "lat": 29.0012,
      "lon": 77.0123,
      "distance_km": 2.2,
      "composite_rating": 4.5,
      "avg_prep_time_minutes": 25,
      "address": "NH-44, Murthal, Haryana",
      "source": "local"
    },
    {
      "id": 47,
      "name": "Highway Kitchen",
      "lat": 29.05,
      "lon": 77.05,
      "distance_km": 4.4,
      "composite_rating": null,
      "avg_prep_time_minutes": 30,
      "address": null,
      "source": "osm"
    }
  ],
  "total_count": 2,
  "cached": false
}
```

Results are ordered by `distance_km` ascending.

**Every result has a real integer `id` and is bookable**, including those sourced from
OpenStreetMap. OSM POIs are upserted into the `restaurants` table at search time
([04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md) §3.2.1), so `id` is never null. An earlier
draft returned `id: null` for `source: "osm"`, which made those results unbookable against
the `NOT NULL` foreign key on `bookings.restaurant_id`.

`source` is `"local"` for onboarded restaurants and `"osm"` for promoted POIs.
`composite_rating` is `null` — not `0` — when a restaurant has no ratings yet, so clients do
not render a zero-star rating for a new restaurant.

**Caching:** Second identical request returns `"cached": true` when Redis available.

---

### 6.2 GET `/restaurants/{id}`

Restaurant detail with menu.

**Auth required:** No

**Response `200`:**

```json
{
  "id": 1,
  "name": "Murthal Dhaba",
  "phone": "+919999999999",
  "address": "NH-44, Murthal",
  "composite_rating": 4.5,
  "rating_count": 28,
  "avg_prep_time_minutes": 25,
  "menu": [
    {"name": "Paneer Paratha", "price": 80.00, "category": "Main"},
    {"name": "Dal Makhani", "price": 120.00, "category": "Main"},
    {"name": "Lassi", "price": 40.00, "category": "Beverage"}
  ]
}
```

**This menu is authoritative.** It is the same source `POST /bookings/create` uses to resolve
unit prices, so what a client displays here is exactly what it will be charged. Menus are
hardcoded per restaurant in MVP; `menu_items` CRUD is Phase 1
([04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md) §4).

`composite_rating` is `null` when `rating_count` is `0` — an unrated restaurant, not a
zero-star one.

---

### 6.3 POST `/restaurants/register`

Restaurant self-registration.

**Auth required:** Yes (traveller JWT)

Registrations are created with `is_active = false` and **do not appear in search results
until an operator activates them**. This is a public-facing write that inserts geospatial
rows, so leaving it open would make it a search-poisoning vector — a spammed row would then
persist in the search cache. Requiring a token gives every submission an accountable origin;
holding it inactive means an unreviewed row is never served.

Manual operator onboarding remains the primary path
([00_PROJECT_CHARTER.md](./00_PROJECT_CHARTER.md) §6.3). The approval UI is Phase 1
([13_ROADMAP.md](./13_ROADMAP.md) §3); until it exists an operator activates rows directly in
the database.

**Rate limit:** 5 per hour per user.

**Request:**

```json
{
  "name": "New Dhaba",
  "phone": "+919888888888",
  "email": "owner@dhaba.com",
  "address": "NH-44 km 45",
  "latitude": 29.1,
  "longitude": 77.1,
  "avg_prep_time_minutes": 30
}
```

**Response `201`:** Created restaurant object

---

## 7. Booking Endpoints

### 7.1 POST `/bookings/create`

**Auth required:** Yes

**Request:**

```json
{
  "restaurant_id": 1,
  "route_id": 1,
  "arrival_time": "2026-07-26T07:30:00Z",
  "items": [
    {"name": "Paneer Paratha", "qty": 2},
    {"name": "Lassi", "qty": 1}
  ],
  "notes": "Less spicy please"
}
```

**Prices are never accepted from the client.** Each item carries `name` and `qty` only. The
server looks the unit price up from the restaurant's own menu (§6.2) and computes the total
itself. A `price` field in the request is rejected as an unknown field
(`extra="forbid"`), not silently ignored.

**Response `201`:**

```json
{
  "booking_id": 42,
  "status": "pending",
  "cutoff_time": "2026-07-26T07:00:00Z",
  "total_price": 200.00,
  "arrival_time": "2026-07-26T07:30:00Z",
  "items": [
    {"name": "Paneer Paratha", "qty": 2, "price": 80.00},
    {"name": "Lassi", "qty": 1, "price": 40.00}
  ]
}
```

The response echoes the resolved unit prices so the client can display the priced order
without holding an authoritative copy of the menu.

**Server-side logic, in order:**

1. Resolve the restaurant; `404 NOT_FOUND` if missing or `is_active = false`.
2. Resolve every item name against that restaurant's menu. Any name not on the menu →
   `400 VALIDATION_ERROR` naming the offending item. An empty `items` array is also a
   `400`.
3. Validate `arrival_time` is far enough ahead:
   `arrival_time >= now + restaurant.avg_prep_time_minutes`. Too soon →
   `400 ARRIVAL_TOO_SOON`. Beyond `now + 48 hours` → `400 VALIDATION_ERROR`.
4. Compute `cutoff_time = arrival_time - restaurant.avg_prep_time_minutes`.
5. Compute `total_price = Σ (menu_price(item.name) × item.qty)`.
6. Persist with `status = 'pending'`, `payment_status = 'pending'`, and the resolved unit
   prices frozen into `items` JSONB — so a later menu price change does not retroactively
   alter a placed order.
7. Trigger the notification stub. A notification failure is logged and does **not** fail
   the booking.

**Errors:** `400 VALIDATION_ERROR`, `400 ARRIVAL_TOO_SOON`, `401 UNAUTHORIZED`,
`404 NOT_FOUND`

---

### 7.2 GET `/bookings/{id}`

**Auth required:** Yes (owner or restaurant — MVP: owner only)

**Response `200`:**

```json
{
  "id": 42,
  "restaurant_id": 1,
  "restaurant_name": "Murthal Dhaba",
  "route_id": 1,
  "status": "confirmed",
  "arrival_time": "2026-07-26T07:30:00Z",
  "cutoff_time": "2026-07-26T07:00:00Z",
  "items": [{"name": "Paneer Paratha", "qty": 2, "price": 80.00}],
  "total_price": 200.00,
  "notes": "Less spicy please",
  "payment_status": "pending",
  "created_at": "2026-07-25T10:00:00Z"
}
```

---

### 7.3 PUT `/bookings/{id}/cancel`

**Auth required:** Yes

**Response `200`:**

```json
{
  "id": 42,
  "status": "cancelled"
}
```

**Errors:** `400 INVALID_STATUS_TRANSITION` if status is `handed_over`

---

## 8. Dashboard Endpoints (Restaurant)

Base path: `/api/dashboard`

### 8.0 Dashboard authentication

**Every endpoint in this section requires the header:**

```
X-Restaurant-Token: <token>
```

checked against the `RESTAURANT_DASHBOARD_TOKEN` env var. A missing or wrong token returns
`403 INVALID_RESTAURANT_TOKEN`.

**The token alone is not sufficient.** Every mutation additionally verifies that the target
booking's `restaurant_id` matches the `restaurant_id` supplied in the request; a mismatch is
`403 FORBIDDEN`. Without that check a single shared token would still let one restaurant
confirm, ready, or hand over another restaurant's orders — including marking `handed_over`,
which permanently blocks cancellation and unlocks rating.

**This is a transitional control, gated to `ENVIRONMENT != production`.** A shared token
cannot distinguish one restaurant from another, so it is adequate for a controlled demo and
not for public use. Per-restaurant JWTs carrying a `restaurant_id` claim are the launch
requirement — [10_SECURITY.md](./10_SECURITY.md) §10 and §3.4.

An earlier draft left these endpoints entirely unauthenticated, mitigated by "obscure URL".
Obscurity is not a control: `restaurant_id` was a plain query parameter, so any caller could
enumerate another restaurant's live order queue — including partially masked customer phone
numbers — and drive arbitrary state transitions.

---

### 8.1 GET `/dashboard/orders`

**Auth required:** `X-Restaurant-Token`

**Query:** `restaurant_id=1&status=pending`

`status` is optional; omit it for all non-terminal orders.

**Response `200`:**

```json
{
  "orders": [
    {
      "booking_id": 42,
      "user_phone": "+919****3210",
      "items": [{"name": "Paneer Paratha", "qty": 2, "price": 80.00}],
      "arrival_time": "2026-07-26T07:30:00Z",
      "cutoff_time": "2026-07-26T07:00:00Z",
      "time_until_cutoff_minutes": 45,
      "is_overdue": false,
      "status": "pending",
      "notes": "Less spicy"
    }
  ]
}
```

Sorted by `cutoff_time` ascending — the most urgent order first.

`time_until_cutoff_minutes` goes negative once the cutoff has passed, and `is_overdue` is
`true` for a `pending` order past its cutoff. Overdue orders are **not** auto-rejected; they
stay `pending` for a human to decide ([02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md) §5.2).

---

### 8.2 PUT `/dashboard/orders/{id}/confirm`

**Auth required:** `X-Restaurant-Token` + ownership check

**Query:** `restaurant_id=1`

**Response `200`:** `{ "id": 42, "status": "confirmed" }`

### 8.3 PUT `/dashboard/orders/{id}/ready`

**Auth required:** `X-Restaurant-Token` + ownership check

**Response `200`:** `{ "id": 42, "status": "ready" }`

### 8.4 PUT `/dashboard/orders/{id}/handed_over`

**Auth required:** `X-Restaurant-Token` + ownership check

**Response `200`:** `{ "id": 42, "status": "handed_over" }`

Each transition validates the state machine
([01_PRODUCT_SPEC.md](./01_PRODUCT_SPEC.md)) and returns
`400 INVALID_STATUS_TRANSITION` if the move is not legal from the current status.

**Errors (8.2–8.4):** `400 INVALID_STATUS_TRANSITION`, `403 INVALID_RESTAURANT_TOKEN`,
`403 FORBIDDEN` (booking belongs to another restaurant), `404 NOT_FOUND`

---

### 8.5 GET `/dashboard/stats`

**Auth required:** `X-Restaurant-Token`

**Query:** `restaurant_id=1`

**Response `200`:**

```json
{
  "daily_order_count": 12,
  "confirmation_rate": 0.92,
  "average_rating": 4.3
}
```

---

## 9. Rating Endpoints

### 9.1 POST `/ratings/create`

**Auth required:** Yes

**Request:**

```json
{
  "booking_id": 42,
  "hygiene_score": 5,
  "food_quality_score": 4,
  "timeliness_score": 5,
  "comment": "Food was hot and ready on time"
}
```

**Response `201`:**

```json
{
  "id": 1,
  "booking_id": 42,
  "restaurant_id": 1,
  "composite_score": 4.67
}
```

**Preconditions:** Booking status must be `handed_over`; one rating per booking.

---

### 9.2 GET `/ratings/{restaurant_id}`

**Response `200`:**

```json
{
  "restaurant_id": 1,
  "average_hygiene": 4.5,
  "average_food_quality": 4.2,
  "average_timeliness": 4.6,
  "composite_average": 4.43,
  "total_ratings": 28
}
```

All four averages are **plain means** over every rating — nothing is excluded. See
[02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md) §5.4 for why the original 2σ outlier
exclusion was dropped.

`composite_average` and `total_ratings` are read from `restaurants.composite_rating` and
`restaurants.rating_count`, which are maintained incrementally. The three per-dimension
averages are computed from `ratings` on request.

Note the naming: `average_hygiene` is hygiene **only**, while `composite_average` covers all
three dimensions. The restaurant column backing the latter is named `composite_rating` for
exactly this reason — it previously sat under the name `hygiene_rating` while holding the
composite.

---

## 10. Health Check

### GET `/health`

**Auth required:** No

**Response `200`:**

```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected"
}
```

---

## 11. Extension Points (Not Implemented in MVP)

### 11.1 Payment provider interface

```
POST /payments/intent     — Phase 2
POST /payments/capture    — Phase 2
GET  /payments/{id}       — Phase 2
```

### 11.2 GPS ingest

```
POST /gps/events          — Phase 3, NOT implemented
```

**Not built in MVP.** The `bus_gps_events` table exists and stays
([04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md) §3.6) — creating it now costs nothing and
avoids a migration later — but no endpoint writes to it.

An earlier draft described this as a live MVP stub that writes to the database, with no auth
requirement stated. That would have been an unauthenticated, unbounded, append-only write
path serving no reader: nothing in MVP consumes the table (ADR-0010), so it carried risk for
no benefit. It arrives with the ETA model in Phase 3, authenticated as a fleet-operator
integration rather than a public endpoint.

### 11.3 WebSocket status

```
WS /bookings/{id}/stream  — Phase 2 (replaces polling)
```

---

## 12. Rate Limiting

| Endpoint | Limit | Scope |
|----------|-------|-------|
| `POST /auth/login` | 10 per hour | per phone |
| `POST /auth/register` | 5 per hour | per IP |
| `GET /restaurants/search` | 60 per minute | per IP |
| `POST /bookings/create` | 30 per hour | per user |
| `POST /restaurants/register` | 5 per hour | per user |
| `POST /ratings/create` | 20 per hour | per user |
| Nominatim / Overpass clients | 1 per second | global outbound throttle |

Exceeding a limit returns `429 RATE_LIMITED` with a `Retry-After` header.

**Implementation:** Redis counters when Redis is available. When it is not, limits are
**best-effort per-process** and reset on restart — which on the Render free tier means they
reset on every cold start. That is an accepted gap for a gated demo, and it is one of the
reasons the OTP stub must not be reachable in production: a constant OTP behind an
unreliable rate limit is not a login.

Booking and registration limits exist to bound abuse of authenticated write paths; neither
had a documented limit previously.

---

## 13. OpenAPI

FastAPI auto-generates OpenAPI 3.1. This document is the human-readable contract; the
generated schema is authoritative for field types.

**Interactive docs are environment-gated:**

| `ENVIRONMENT` | `/docs`, `/redoc`, `/openapi.json` |
|---------------|-----------------------------------|
| `development` / `test` | Served |
| `production` | **Disabled** (`docs_url=None, redoc_url=None, openapi_url=None`) |

A public Swagger UI hands an attacker a complete, executable map of every endpoint,
including the ones this document gates behind environment checks. There is no reason to
serve it from production while the OTP stub and shared dashboard token exist.

**Drift detection:** `openapi.json` is generated and committed, and CI fails if the
committed copy differs from what the running app produces
([12_DEPLOYMENT.md](./12_DEPLOYMENT.md) §6.1). Without that check, "the generated schema is
authoritative" is unenforceable — this prose and the code can disagree silently.

---

## 14. Related Documents

- [04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md)
- [10_SECURITY.md](./10_SECURITY.md)
- [03_SYSTEM_ARCHITECTURE.md](./03_SYSTEM_ARCHITECTURE.md)
