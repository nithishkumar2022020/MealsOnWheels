# Frontend Contract Audit

**Date:** 2026-07-31
**Audited against:** the frozen frontend design spec supplied by the owner
**Audited:** live code on `autopilot/backend-build-20260730` (Stages 7–10), read from
`app/schemas.py`, `app/routers/`, and the running server's OpenAPI — not from the spec docs.

---

## 1. Headline

**Wire-format compliance: 0%.** Not one implemented endpoint matches the design spec
field-for-field.

**Structural coverage: 5 of 16 endpoints (31%).** Eleven endpoints do not exist yet.

The frontend cannot build against this backend today. That is expected — the backend is
mid-build at Stage 10 of 19 — but the divergence is **not** simply "unfinished". The parts
that *are* built disagree with the design spec on field names, response envelope, and
status codes. Finishing the remaining stages as currently planned would widen the gap, not
close it.

## 2. The decision that gates everything else

**The design spec and this repository's own 16 spec documents are two different contracts.**
They disagree on fundamentals, and the disagreement cannot be resolved endpoint by endpoint.
Someone has to pick.

The conflicts fall into three groups, and they should be resolved differently:

**Group A — the frontend should win.** Pure naming and shape. No correctness argument on
either side; the frozen client is the constraint. `jwt_token` not `access_token`,
`latitude`/`longitude` not `lat`/`lon`, `{error, message, status}` not `{detail, code}`.
Renaming costs hours. Recommend: **adopt the frontend's names wholesale.**

**Group B — the backend should win, and the spec should change.** Adopting these would
introduce a defect:

- **Client-supplied item prices.** The spec's `POST /bookings/create` sends
  `price: 120` per line. The backend deliberately refuses this and resolves prices from its
  own menu — otherwise a caller books two dishes for ₹0.02. Keep `menu_item_id` from the
  spec (it is an improvement), drop `price`.
- **HTTP 500 when Overpass is down.** The spec's own audit checklist contradicts its
  example here ("return fallback or empty array (not crash)"). Returning 500 for a degraded
  external dependency turns a partial result into an outage. Keep the graceful path.

**Group C — needs your product decision.** No technically correct answer:

| Question | Spec says | Backend says |
|---|---|---|
| Cutoff time | `booking_time − 30 min`, flat | `arrival_time − restaurant.avg_prep_time_minutes` |
| Restaurant rating | `hygiene_rating` = mean of hygiene scores only | `composite_rating` = mean of all three dimensions |
| Cancel refund | returns `refund_amount` | pay-on-arrival, no money was taken (ADR-0007) |
| `confirmed → pending` | allowed ("undo button") | forbidden, no reversals |
| Cancel from `ready` | not allowed | allowed |

A flat 30-minute cutoff is wrong for a dhaba with a 45-minute prep time — it promises food
that cannot be cooked in time. But it is simpler and the frontend may render it. Your call.

`refund_amount` is the one I would push back on hardest: returning `refund_amount: 340`
when no payment was ever taken tells the traveller they are owed money they never paid.

## 3. Internal contradictions in the design spec

These need resolving regardless of which side wins, because the spec cannot be implemented
as written:

1. **Part 8 contradicts every example in Part 2.** Part 8 mandates
   `{"data": {...}, "message": ..., "status": "success"}`. Every concrete example in Part 2
   shows a bare object (`{"jwt_token": ..., "user_id": ...}`) with no wrapper. Implementing
   both is impossible. **Recommend: bare objects** — they match all 16 worked examples, and
   an envelope adds a layer for no benefit when HTTP already carries the status.
2. **Overpass failure**: HTTP 500 (example) vs "return fallback or empty array, not crash"
   (checklist).
3. **Price format**: "stored as integers in paise (12000 = ₹120.00)" *or* "decimal with 2
   places" — then every example shows plain integer rupees (`120`, `total_price: 340`).
   Three formats in one section. **Recommend: `DECIMAL(10,2)`**, already implemented.
4. **`users.password_hash`** (Part 6) contradicts the OTP/JWT design in Part 2. The spec
   flags this itself ("or OTP column, but prefer JWT"). Recommend: no password column.

## 4. Findings — implemented endpoints

### CRITICAL · POST /auth/login · response field names

- **Current:** `{access_token, token_type, expires_in, user: {id, phone, name}}`
- **Expected:** `{jwt_token, user_id, phone, email}` — flat, not nested
- **Fix:** rename `access_token` → `jwt_token`; flatten `user.id` → `user_id` and
  `user.phone` → `phone`; add `email`; drop `name` or keep as an addition. Note the spec
  omits `expires_in`, which the client needs to pre-empt expiry — recommend keeping it.

### CRITICAL · POST /auth/register · response shape

- **Current:** `201 {id, phone, name, email, created_at}`
- **Expected:** `201 {user_id, message: "OTP sent to your phone"}`
- **Fix:** rename `id` → `user_id`, add `message`. Caveat: the message would be a lie today
   — no SMS is sent, the OTP is the stub `123456`. Suggest `"Registration complete"` until
  Stage 18 delivers a real provider.

### CRITICAL · POST /auth/register · duplicate-phone status code

- **Current:** `409 PHONE_ALREADY_REGISTERED`
- **Expected:** `400 {error: "Phone already registered", message: ...}`
- **Fix:** 409 is the more correct REST semantic, but the frozen client branches on 400.
  Change to 400, or confirm the client treats 4xx generically.

### CRITICAL · GET /restaurants/search · coordinate field names

- **Current:** `lat`, `lon`
- **Expected:** `latitude`, `longitude`
- **Fix:** rename in `RestaurantSearchResult`. Note `POST /restaurants/register` already
  *accepts* `latitude`/`longitude` — the API is currently inconsistent with itself.

### CRITICAL · GET /restaurants/search · missing fields

- **Current:** `{id, name, lat, lon, distance_km, composite_rating, avg_prep_time_minutes, address, source}`
- **Expected:** adds `image_url`, `cuisines: string[]`, `is_active`; `hygiene_rating` not
  `composite_rating`
- **Fix:** three new columns on `restaurants` (`image_url`, `cuisines`, plus a rating
  decision). Requires a migration.

### CRITICAL · GET /restaurants/{id} · missing fields and menu shape

- **Current:** `{id, name, phone, address, composite_rating, rating_count, avg_prep_time_minutes, menu: [{name, price, category}]}`
- **Expected:** adds `latitude`, `longitude`, `cuisines`, `is_active`, `image_url`,
  `timezone`, `recent_ratings[]` (5 most recent, anonymised); each menu item needs
  `id`, `description`, `prep_time_minutes`, `is_available`, `image_url`
- **Fix:** **this is the largest single gap.** Menu items have no `id` today because menus
  are hardcoded in `app/services/menu.py`. The spec's booking request references
  `menu_item_id`, so a real `menu_items` table becomes a prerequisite for bookings — it
  cannot stay a Phase 1 item.

### CRITICAL · all endpoints · error envelope

- **Current:** `{"detail": "...", "code": "MACHINE_READABLE_CODE"}`
- **Expected:** `{"error": "...", "message": "..."}`
- **Fix:** one change in `app/main.py`'s exception handlers plus `app/errors.py`. Cheap,
  and it touches every endpoint at once. Do this first.

### HIGH · GET /routes · field naming

- **Current:** `origin_name`, `dest_name`, `origin_lat`, `origin_lon`, `dest_lat`, `dest_lon`
- **Expected (Part 6 schema):** `start_city`, `end_city`, `start_lat`, `start_lon`,
  `end_lat`, `end_lon`
- **Fix:** no frontend screen consumes this, so it is lower risk — but pick one vocabulary
  before a client binds to it.

### MEDIUM · POST /auth/login · OTP validation width

- **Current:** `^\d{4,8}$`
- **Expected:** exactly 6 digits
- **Fix:** tighten to `^\d{6}$`. The looser pattern accepts input the frontend can never
  send, so it is not breaking — but it is laxer than the contract.

### MEDIUM · GET /restaurants/search · cache TTL

- **Current:** 6 hours
- **Expected:** 7 days
- **Fix:** the TTL was shortened deliberately so a newly activated restaurant becomes
  visible within hours rather than a week. If the frontend has no stake in this, keep 6
  hours; it is invisible over the wire.

### MEDIUM · GET /health path

- **Current:** `/api/health`
- **Expected (Part 9):** `/health`
- **Fix:** add an unprefixed alias. Render's health check is already configured for
  `/api/health`, so serve both rather than moving it.

### LOW · POST /auth/login · phone pattern breadth

- **Current:** `^\+[1-9]\d{6,14}$` (any country)
- **Expected:** `^\+91\d{10}$` (India only)
- **Fix:** a superset — every value the frontend sends is accepted. No action needed unless
  you want to reject non-Indian numbers explicitly.

## 5. Findings — endpoints not yet built

Eleven of sixteen. Each will be built to the frozen contract **only if** the Group A
decision above is taken; otherwise they will be built to the repo's own spec and diverge
further.

| Endpoint | Blocking prerequisite |
|---|---|
| `POST /restaurant/auth/login` | Per-restaurant JWT. Currently a shared `X-Restaurant-Token` gated to non-production, with real per-restaurant auth deferred to Stage 18. **The spec requires it now** — this is a genuine improvement on the current plan and should be pulled forward. |
| `POST /bookings/create` | `menu_items` table; `booking_type` enum; `booking_id` string format |
| `GET /bookings/{booking_id}` | string `booking_id` |
| `PUT /bookings/{booking_id}/cancel` | refund semantics decision (Group C) |
| `GET /bookings` (history) | pagination; `items_summary` as a pre-formatted string |
| `POST /ratings/create` | hygiene-vs-composite decision (Group C) |
| `GET /dashboard/orders` | three grouped arrays + embedded stats in one response |
| `PUT /dashboard/orders/{id}/confirm` | `confirmed_at` column |
| `PUT /dashboard/orders/{id}/ready` | `ready_at` column |
| `PUT /dashboard/orders/{id}/handed_over` | `handed_over_at` column |
| `PUT /restaurants/{id}/settings` | `cuisines`, `timezone`, `is_active` toggle |

## 6. Schema changes required

The current migration cannot support the design spec. A second migration is needed:

**`bookings`**
- `id BIGSERIAL` → a string `booking_id` in `BK######` format. **Breaking**; do it before
  any booking rows exist.
- add `booking_type` — `bus_boarding_point | self_drive_dine | self_drive_takeaway`. This
  concept appears nowhere in the repo's docs; it is new product surface, not a rename.
- add `confirmed_at`, `ready_at`, `handed_over_at`
- `arrival_time` → `booking_time` if Group A is adopted (reverses a deliberate rename —
  see §7)

**`restaurants`**
- add `cuisines` (text[] or JSONB), `image_url`, `timezone`, and an `is_closed`/opening-hours
  concept — the spec requires rejecting bookings when a restaurant is closed by time of day,
  and there is no hours model at all today
- `composite_rating` → `hygiene_rating` if Group C resolves that way

**`menu_items`** — create. Currently hardcoded; the spec needs stable `menu_item_id`s,
`is_available`, per-item prep time, descriptions, and images.

**`ratings`** — enforce `comment` ≤ 500 chars.

## 7. One rename to think about before reversing

The backend renamed `booking_time` → `arrival_time` earlier in this build. The reason: every
formula treats it as *when the traveller arrives*, while the name reads as *when the booking
was created*. The spec uses `booking_time`.

If Group A is adopted wholesale this reverts — which is fine, a frozen client outranks a
naming preference. But it is worth knowing it is a deliberate reversal rather than an
oversight, and that `cutoff_time = booking_time − 30 min` reads as nonsense to anyone who
has not been told that `booking_time` means arrival.

A middle path: keep `booking_time` on the wire (frontend contract) and `arrival_time` in the
database and internal code, mapping at the schema boundary. Costs one line per schema.

## 8. What is already correct

Not everything diverges. These match the spec as built:

- Timestamps are `TIMESTAMPTZ`, always UTC, serialised ISO 8601
- Phones stored E.164 with country code, normalised before the uniqueness check
- Prices are `DECIMAL`, never float
- Search results sorted by distance, nearest first; empty array rather than an error
- Redis caching with graceful degradation; no crash when Redis is down
- Request logging with duration per request; structured JSON to stdout
- `DATABASE_URL`, `JWT_SECRET`, `REDIS_URL` all from environment, never hardcoded
- Connection pooling configured
- Seed data present (5 routes, 10 corridor restaurants, test user)
- Ratings constrained to integers 1–5 at the database level
- One rating per booking enforced by a unique constraint, not an application check
- JWT carries `sub`/`phone`, expires in 24h, validated on protected routes
- Booking ownership checked, not just authentication

## 9. Recommended order of work

1. **Get the Group A / B / C decisions** (§2). Everything below depends on them.
2. **Error envelope** — one file, fixes every endpoint at once.
3. **Rename response fields** on the four built endpoints + add missing columns.
4. **`menu_items` table** — unblocks bookings, which unblocks half the remaining endpoints.
5. **Per-restaurant JWT**, pulled forward from Stage 18.
6. Then bookings → dashboard → ratings → history, to the frozen contract.

Steps 2–3 are roughly half a day and take wire-format compliance from 0% to ~90% on what
exists. Step 4 is the real work.
