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
| 400 | `VALIDATION_ERROR`, `INVALID_STATUS_TRANSITION` | Bad input |
| 401 | `UNAUTHORIZED`, `INVALID_OTP`, `TOKEN_EXPIRED` | Auth failure |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource missing |
| 409 | `DUPLICATE_RATING` | Rating already exists |
| 422 | `UNPROCESSABLE_ENTITY` | Pydantic validation |
| 429 | `RATE_LIMITED` | Throttle exceeded |
| 500 | `INTERNAL_ERROR` | Unhandled server error |
| 503 | `SERVICE_UNAVAILABLE` | Database unreachable |

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

**MVP behavior:** OTP must be exactly `123456`. Any other value returns `401 INVALID_OTP`.

**Side effect:** If user does not exist, auto-register on first successful login (sprint convenience).

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

**Auth required:** No (MVP)

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

---

## 6. Restaurant Endpoints

### 6.1 GET `/restaurants/search`

Search restaurants near a point on a route.

**Auth required:** No (MVP)

**Query parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `route_id` | int | Yes | — | Route identifier |
| `latitude` | float | Yes | — | Search center lat |
| `longitude` | float | Yes | — | Search center lon |
| `radius_km` | float | No | 15 | Search radius |

**Example:**

```
GET /api/restaurants/search?route_id=1&latitude=30.9&longitude=77.7&radius_km=15
```

**Response `200`:**

```json
{
  "restaurants": [
    {
      "id": 1,
      "name": "Murthal Dhaba",
      "lat": 29.0,
      "lon": 77.0,
      "distance_km": 3.2,
      "hygiene_rating": 4.5,
      "avg_prep_time_minutes": 25,
      "address": "NH-44, Murthal, Haryana",
      "source": "local"
    },
    {
      "id": null,
      "name": "Highway Kitchen",
      "lat": 29.05,
      "lon": 77.05,
      "distance_km": 5.1,
      "hygiene_rating": null,
      "avg_prep_time_minutes": 30,
      "address": null,
      "source": "osm"
    }
  ],
  "total_count": 2,
  "cached": false
}
```

**Caching:** Second identical request returns `"cached": true` when Redis available.

---

### 6.2 GET `/restaurants/{id}`

Restaurant detail with dummy menu (MVP).

**Response `200`:**

```json
{
  "id": 1,
  "name": "Murthal Dhaba",
  "phone": "+919999999999",
  "address": "NH-44, Murthal",
  "hygiene_rating": 4.5,
  "avg_prep_time_minutes": 25,
  "menu": [
    {"name": "Paneer Paratha", "price": 80.00, "category": "Main"},
    {"name": "Dal Makhani", "price": 120.00, "category": "Main"},
    {"name": "Lassi", "price": 40.00, "category": "Beverage"}
  ]
}
```

---

### 6.3 POST `/restaurants/register`

Manual restaurant onboarding (dashboard form).

**Auth required:** No (MVP; protect in Phase 2)

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
  "booking_time": "2026-07-26T07:30:00Z",
  "items": [
    {"name": "Paneer Paratha", "qty": 2, "price": 80.00},
    {"name": "Lassi", "qty": 1, "price": 40.00}
  ],
  "notes": "Less spicy please"
}
```

**Response `201`:**

```json
{
  "booking_id": 42,
  "status": "pending",
  "cutoff_time": "2026-07-26T07:00:00Z",
  "total_price": 200.00,
  "booking_time": "2026-07-26T07:30:00Z"
}
```

**Server-side logic:**

- Validates `booking_time` is in the future
- Computes `cutoff_time = booking_time - restaurant.avg_prep_time_minutes`
- Computes `total_price` from items
- Triggers notification stub

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
  "booking_time": "2026-07-26T07:30:00Z",
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

### 8.1 GET `/dashboard/orders`

**Query:** `restaurant_id=1&status=pending`

**Response `200`:**

```json
{
  "orders": [
    {
      "booking_id": 42,
      "user_phone": "+919****3210",
      "items": [{"name": "Paneer Paratha", "qty": 2, "price": 80.00}],
      "cutoff_time": "2026-07-26T07:00:00Z",
      "time_until_cutoff_minutes": 45,
      "status": "pending",
      "notes": "Less spicy"
    }
  ]
}
```

Sorted by `cutoff_time` ascending.

---

### 8.2 PUT `/dashboard/orders/{id}/confirm`

**Response `200`:** `{ "id": 42, "status": "confirmed" }`

### 8.3 PUT `/dashboard/orders/{id}/ready`

**Response `200`:** `{ "id": 42, "status": "ready" }`

### 8.4 PUT `/dashboard/orders/{id}/handed_over`

**Response `200`:** `{ "id": 42, "status": "handed_over" }`

Each transition validates state machine rules ([01_PRODUCT_SPEC.md](./01_PRODUCT_SPEC.md)).

---

### 8.5 GET `/dashboard/stats`

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

Outliers (> 2 SD) excluded from averages per [02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md).

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
POST /gps/events          — Ingest bus GPS (MVP: endpoint stub, writes bus_gps_events)
```

### 11.3 WebSocket status

```
WS /bookings/{id}/stream  — Phase 2 (replaces polling)
```

---

## 12. Rate Limiting

| Endpoint group | Limit | Window |
|----------------|-------|--------|
| `/auth/login` | 10 | per phone per hour |
| `/restaurants/search` | 60 | per IP per minute |
| External geo calls | 1/sec | global client throttle |

Implemented via Redis counters in Phase 2; in-process throttle in MVP.

---

## 13. OpenAPI

FastAPI auto-generates OpenAPI 3.1 at `/docs` (Swagger UI) and `/redoc`. This document is the human-readable contract; generated schema is authoritative for field types.

---

## 14. Related Documents

- [04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md)
- [10_SECURITY.md](./10_SECURITY.md)
- [03_SYSTEM_ARCHITECTURE.md](./03_SYSTEM_ARCHITECTURE.md)
