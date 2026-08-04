# Screen → API Wiring

**Verified against a running backend** at Stage 10 (2026-08-01) unless marked otherwise.
**Companion to:** [../FRONTEND_CONTRACT.md](../FRONTEND_CONTRACT.md), which holds the full
response shapes. This file is per-screen: what to call, what to render, what can go wrong.

Legend: ✅ built · 🔨 Stage 11–13 · 📋 needs `16` sign-off · ❌ no backend design

---

## 1. Rules that apply to every screen

1. **Errors are `{detail, code}`.** Branch on `code`. Render `detail` only as a fallback
   message.
2. **Money is a string** — `"80.00"`. Parse `Decimal`, display `₹`.
3. **Timestamps are UTC with `Z`.** Convert for display; compute in UTC.
4. **Handle three states everywhere:** loading, error, empty. The mockups have screens for
   all three — wire them as you go, not later.
5. **Unknown query params are silently dropped.** A 200 does not mean the parameter worked.
6. Handle `401 TOKEN_EXPIRED` globally in the dio interceptor → clear token → login with
   "Session expired". No screen implements this itself.

---

## 2. Login ✅

**Screen:** `login_screen_1`

```
POST /api/auth/login   { "phone": "+919876543210", "otp": "123456" }
→ 200 { access_token, token_type: "bearer", expires_in: 86400,
        user: { id, phone, name } }
```

Store `access_token` in `flutter_secure_storage`. The embedded `user` is trimmed — **no
email, no timestamps**; fetch `/user/profile` if more is needed.

| Code | Status | UI |
|---|---|---|
| `INVALID_OTP` | 401 | Inline: "Incorrect code. Try again." |
| `USER_NOT_FOUND` | 404 | **Not an error — go to registration.** See below |
| `RATE_LIMITED` | 429 | "Too many attempts. Try again in N minutes." Read `Retry-After` |
| `SERVICE_UNAVAILABLE` | 503 | "Phone verification is temporarily unavailable." Not retryable |

**The registration gap.** The mockups have no register screen, but login never creates a
user — so a first-time traveller cannot get in. Treat `404 USER_NOT_FOUND` as a *branch*:
reveal name + optional email, then:

```
POST /api/auth/register  { phone, name?, email? }   → 201
```

…and immediately call login again. `409 PHONE_ALREADY_REGISTERED` on register means the
phone exists — return to the OTP step rather than showing a dead end.

The OTP stub is `123456` outside production. Phone input strips spaces and dashes; it must
match `^\+[1-9]\d{6,14}$` after stripping. The `+91` prefix is a UI affordance — send full
E.164.

---

## 3. Route search ✅

**Screen:** `route_search_vibrant`

```
GET /api/routes
→ 200 { routes: [ { id, name, origin_name, dest_name,
                    origin_lat, origin_lon, dest_lat, dest_lon, distance_km } ],
        total_count: 5 }
```

Five routes. **No polyline is returned** and `routes.geometry` is NULL — do not draw a
corridor. Public: no token needed.

The mockup's separate origin/destination dropdowns imply free combination; the API returns
**fixed pairs**. Render one dropdown of routes, or two that only offer valid pairs.

---

## 4. Restaurant list & map ✅

**Screens:** `find_restaurants_vibrant`, `restaurant_list_map_view_1`

```
GET /api/restaurants/search?latitude=29.02&longitude=77.02&radius_km=15
→ 200 { restaurants: [ { id, name, lat, lon, distance_km,
                         composite_rating, avg_prep_time_minutes,
                         address, source } ],
        total_count, cached }
```

- Ordered by `distance_km` ascending. **No sort parameter exists.**
- `radius_km` default 15, max 50. Out of range → 422.
- `composite_rating` is `null` when unrated → render **"New"**, never 0★. Every seeded
  restaurant is currently unrated.
- `source` is `"local"` or `"osm"`. OSM rows have `phone: ""` (empty string), often
  `address: null`, `avg_prep_time_minutes: 30` (a default), and a generic menu — consider a
  subtle "Community listing" marker.
- `cached: true` means up to 6 h stale.
- Empty → `no_restaurants_found_empty_state_2`.
- Network failure → `network_connection_error`.

**Filters in the mockup that have no backing:** hygiene rating, fast prep, pure veg, cuisine,
open-now. Ship the screen without them, or as client-side filters over the returned list —
but a "Hygiene 4.0+" filter returns nothing while all ratings are `null`. Prefer omitting.

---

## 5. Restaurant menu ✅

**Screen:** `restaurant_menu_1`

```
GET /api/restaurants/{id}
→ 200 { id, name, phone, address, composite_rating, rating_count,
        avg_prep_time_minutes,
        menu: [ { name, price: "80.00", category } ] }
```

4–5 items. Categories: `Main`, `Beverage`, `Dessert`, `Starter`, `Side`, `Snack`.
Unknown **or inactive** id → 404.

**This menu is authoritative** — the same source booking prices against. Menu items have
**no id** today; the cart keys on `name`. (`16` §3.1 proposes `menu_items` with ids; until
signed off, name is the key.)

No images. No veg/non-veg flag. No "bestseller" badge. No per-item prep time — those come
from `16`.

Empty phone (`""`) on OSM rows → hide the call button, do not render an empty row.

---

## 6. Cart & checkout 🔨 *Stage 11 — not built*

**Screen:** `checkout_payment_1`

```
POST /api/bookings/create
  { restaurant_id, route_id?, arrival_time, booking_type,
    items: [ { name, qty } ],        ← NO price field
    notes? }
```

**Send name + qty only.** A `price` field is rejected with 422. The server resolves prices
from its own menu and computes the total — client totals are a preview.

| Code | Meaning |
|---|---|
| `ARRIVAL_TOO_SOON` | Earlier than `now + avg_prep_time_minutes`. Offer the earliest valid time |
| `ITEM_NOT_ON_MENU` | Name did not resolve — refresh the menu |
| `ITEM_UNAVAILABLE` 📋 | Went out of stock mid-flow → `order_update_required_vibrant` |
| `RESTAURANT_CLOSED` 📋 | Closed at `arrival_time` in its own timezone |

**Minimum lead time is per-restaurant** (20–45 min in seed data), not a flat 30. Compute the
floor only after a restaurant is chosen — a time picked on the search screen can become
invalid.

**Payment is entirely unbacked.** Wallet, UPI, cards, promo code, delivery fee, taxes — none
exist. `payment_status` is `pending|paid` and nothing sets `paid`; the charter says pay at
the counter. Ship checkout with an informational "Pay at the restaurant on pickup" banner and
omit the payment section until a payments phase exists.

---

## 7. Booking status & history 🔨 *Stage 11*

**Screens:** `order_status_tracking_enhanced`, `booking_confirmed_modal_1`, `order_history`

```
GET /api/bookings          → own bookings
GET /api/bookings/{id}     → one
PUT /api/bookings/{id}/cancel
```

Statuses: `pending` → `confirmed` → `ready` → `handed_over`, with `cancelled` reachable from
the first three. `handed_over` and `cancelled` are **terminal**.

Poll `GET /bookings/{id}` every 10 s; **stop on terminal states.** Pause when backgrounded.

The mockup's stepper says "Picked up" for `handed_over` — fine as display copy, keep the
mapping explicit. `ready` → show `order_ready_modal`.

Ownership is enforced: another user's booking id returns **404, not 403**, so ids are not
enumerable. Do not build UI that distinguishes them.

Cancellation shows a refund amount that cannot be computed — no payments. Show "No payment
was taken" instead.

---

## 8. Rating 🔨 *Stage 13*

**Screen:** `post_trip_rating_screen`

```
POST /api/ratings/create
  { booking_id, hygiene_score, food_quality_score, timeliness_score, comment? }
```

All three required, 1–5. Only for `handed_over` bookings. One per booking — a second is
`409 DUPLICATE_RATING`, enforced by a unique index.

The three scores are collected separately but **only ever returned as `composite_rating`**,
their mean. There is no endpoint returning a per-dimension breakdown, so do not design a
detail screen that shows one.

---

## 9. Profile ⚠️ partial

**Screen:** `user_profile_settings`

```
GET /api/user/profile → { id, phone, name, email, created_at }
```

Read-only — **there is no PUT**. "Edit Profile" has no endpoint.

Also unbacked on this screen: **wallet and balance** (no payments), **saved locations**,
**veg preferences**, **notification settings**. Logout is client-side only — discard the
token; it stays valid server-side up to 24 h (no blocklist until Phase 2).

---

## 10. Restaurant owner 📋 *needs `16` sign-off*

**Screens:** `restaurant_login`, `restaurant_dashboard_vibrant`, `restaurant_menu_management`,
`operating_hours_vibrant`, `restaurant_settings`

Dashboard order list/transitions are Stage 12 🔨. Menu CRUD, hours, and accepting-orders are
proposed in `16` §3.5 📋.

**The shared `X-Restaurant-Token` cannot ship in production** — the server refuses to start
with it set when `ENVIRONMENT=production`. Per-restaurant accounts (`16` §3.3) are the
prerequisite. Build owner screens against the proposed JWT login, not the shared token.

`restaurant_analytics_dashboard` has **no endpoint at all** ❌ — orders, revenue, hourly
breakdown, top items. Do not build it against invented numbers.

---

## 11. Screens with no backend ❌

Do not wire these. Listed so nobody starts.

| Screen | Missing |
|---|---|
| `notifications_center`, `no_notifications` | No notification system |
| `restaurant_analytics_dashboard` | No analytics endpoints |
| `restaurant_busy_warning` | No queue-depth field |
| `live_order_tracking_*` (5) | No riders, no live GPS |
| `delivery_partner_*`, `partner_registration`, `document_upload`, `how_it_works_rider` | No rider subsystem |
| `gps_unavailable_tracking` | Delivery only |
| Wallet / payment sections | No payments |

See [06_FULFILMENT_MODES.md](./06_FULFILMENT_MODES.md).

---

## 12. Local development

```bash
docker compose up -d                 # postgres, redis, backend
docker compose exec backend python scripts/seed.py
curl -s localhost:8000/api/health
```

Flutter: `--dart-define=API_BASE_URL=http://10.0.2.2:8000/api` (Android emulator) or
`http://localhost:8000/api` (iOS simulator).

**Seed data:** demo point `29.02, 77.02`; 10 restaurants within 15 km, nearest Gulshan Dhaba
1.1 km; prep 20–45 min; all ratings `null`; test user `+919876543210` / OTP `123456`.
