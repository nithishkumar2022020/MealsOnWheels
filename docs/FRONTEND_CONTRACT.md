# Frontend ↔ Backend Contract — Design Review Brief

**Snapshot date:** 2026-07-31
**Backend state:** Stages 7–10 complete (auth, routes, restaurants). Stages 11–14 not built.
**Purpose:** Everything a designer or reviewer needs to check whether a mockup matches what
the server actually does.

> This is a **snapshot**, not a spec. [05_API_SPEC.md](./05_API_SPEC.md) is the contract;
> this file records which parts of it exist today and where the design docs have drifted
> from them. Re-verify against the build plan before trusting it after Stage 11 lands.

---

## 1. How to use this for a mockup review

Check a mockup against three things, in this order:

1. **§4 — Blocking mismatches.** These are places where the design and the server disagree
   about something load-bearing. A mockup that matches the design docs here is still wrong.
2. **§5 — Data the design assumes but the API does not return.** Anything drawn from data
   that does not exist needs either a backend change or a design change.
3. **§3 — Exact response shapes.** Field names, types, and null cases.

§6 lists screens whose backend is not built yet — a mockup for those is designing against
`05_API_SPEC.md` alone, which is fine, but nothing is verified.

---

## 2. What exists today

| Endpoint | Auth | Status |
|----------|------|--------|
| `GET /api/health` | No | Built |
| `POST /api/auth/register` | No | Built |
| `POST /api/auth/login` | No | Built |
| `GET /api/user/profile` | JWT | Built |
| `GET /api/routes` | No | Built |
| `GET /api/restaurants/search` | No | Built |
| `GET /api/restaurants/{id}` | No | Built |
| `POST /api/restaurants/register` | JWT | Built |
| `POST /api/bookings/create` | JWT | **Stage 11 — not built** |
| `GET /api/bookings`, `/{id}`, `PUT /{id}/cancel` | JWT | **Stage 11 — not built** |
| `GET/PUT /api/dashboard/*` | `X-Restaurant-Token` | **Stage 12 — not built** |
| `POST /api/ratings/create` | JWT | **Stage 13 — not built** |

There is **no** endpoint for: editing a profile, logging out, uploading an image, changing a
menu, searching by cuisine, or listing a restaurant's own bookings by phone.

---

## 3. Exact response shapes

### Conventions

- Base URL `/api`. JSON only.
- **All timestamps are ISO 8601 UTC with a `Z` suffix** (`2026-07-31T07:30:00Z`). The client
  converts to IST for display, and countdown maths must be done in UTC.
- Phones are E.164 (`+919876543210`). Input accepts spaces, dashes, and parens and strips
  them; anything not matching `^\+[1-9]\d{6,14}$` after stripping is a 422.
- **Money is a JSON *string***, not a number: `"price": "80.00"`. It is a server-side
  `Decimal` and is serialised as a string on purpose, so it must be parsed as decimal — not
  as a float — and rendered as ₹ (INR).
- No pagination. MVP returns full lists.

### Every error, without exception

```json
{ "detail": "Human-readable message", "code": "MACHINE_READABLE_CODE" }
```

**Branch UI on `code`, never on `detail`** — the messages are not stable copy. Codes in use
today: `UNAUTHORIZED`, `TOKEN_EXPIRED`, `INVALID_OTP`, `USER_NOT_FOUND`, `NOT_FOUND`,
`PHONE_ALREADY_REGISTERED`, `VALIDATION_ERROR`, `UNPROCESSABLE_ENTITY`, `RATE_LIMITED`,
`SERVICE_UNAVAILABLE`, `INTERNAL_ERROR`.

### `POST /api/auth/register` → 201

```json
{ "id": 1, "phone": "+919876543210", "name": "Priya Sharma",
  "email": "priya@example.com", "created_at": "2026-07-31T08:00:00Z" }
```

`name` and `email` are optional and may be `null`. Duplicate phone → `409
PHONE_ALREADY_REGISTERED`.

### `POST /api/auth/login` → 200

```json
{ "access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400,
  "user": { "id": 1, "phone": "+919876543210", "name": "Priya Sharma" } }
```

The embedded `user` is trimmed — **no email, no timestamps**. Errors: `401 INVALID_OTP`,
`404 USER_NOT_FOUND`, `429 RATE_LIMITED`, `503 SERVICE_UNAVAILABLE`.

### `GET /api/routes` → 200

```json
{ "routes": [ { "id": 1, "name": "Delhi-Chandigarh",
    "origin_name": "Delhi", "dest_name": "Chandigarh",
    "origin_lat": 28.6139, "origin_lon": 77.209,
    "dest_lat": 30.7333, "dest_lon": 76.7794, "distance_km": 245 } ],
  "total_count": 5 }
```

Five routes: Delhi-Chandigarh, Mumbai-Pune, Bangalore-Hyderabad, Chennai-Bangalore,
Jaipur-Delhi. **No route polyline is returned, and none is stored yet** — see §4.4.

### `GET /api/restaurants/search?latitude=&longitude=&radius_km=&route_id=` → 200

```json
{ "restaurants": [ { "id": 3, "name": "Gulshan Dhaba",
    "lat": 29.0154, "lon": 77.0098, "distance_km": 1.1,
    "composite_rating": null, "avg_prep_time_minutes": 20,
    "address": "NH-44, Murthal, Haryana", "source": "local" } ],
  "total_count": 10, "cached": false }
```

- `radius_km` defaults to 15, max 50. Out-of-range coordinates or radius → 422.
- Ordered by `distance_km` ascending. **There is no sort parameter.**
- `composite_rating` is `null` when unrated — see §4.2.
- `source` is `"local"` or `"osm"` — see §5.3.
- `route_id` is accepted and **ignored** — see §4.4.

### `GET /api/restaurants/{id}` → 200

```json
{ "id": 1, "name": "Murthal Dhaba", "phone": "+919811100001",
  "address": "NH-44, Murthal, Haryana",
  "composite_rating": null, "rating_count": 0, "avg_prep_time_minutes": 25,
  "menu": [ { "name": "Paneer Paratha", "price": "80.00", "category": "Main" } ] }
```

Unknown **or inactive** id → `404 NOT_FOUND`. Menu length is **4 or 5 items** depending on the
restaurant. Categories in use: `Main`, `Beverage`, `Dessert`, `Starter`, `Side`, `Snack`.

### `POST /api/restaurants/register` → 201 (JWT required)

Request takes `name`, `phone`, `email?`, `address?`, `latitude`, `longitude`,
`avg_prep_time_minutes?` (default 30). Response echoes those plus `id` and
`is_active: false`. The row is **invisible to search and 404s on detail** until an operator
activates it manually — there is no approval UI.

### Request bodies reject unknown fields

Every request schema is `extra="forbid"`. Sending a field the server does not model is a
**422, not a silent ignore**. So a mockup cannot "send `is_active`" or "send a price" — those
are refused. This is deliberate and is the control behind server-side pricing.

---

## 4. Blocking mismatches — design and server disagree

### 4.1 There is no registration screen, and login will not create an account

**The most important item in this document.**

[07_UI_UX_GUIDELINES.md](./07_UI_UX_GUIDELINES.md) §2 shows the information architecture as
`Login → Search`. There is no register screen anywhere in the IA, and §3.1 describes only
phone + OTP.

But **login never creates a user.** An unrecognised phone returns `404 USER_NOT_FOUND`
directing the caller to register first. This is a security decision, not an oversight: login
that auto-registers, combined with a constant OTP, let anyone mint a 24-hour token for any
phone number including a real person's.

**Consequence:** a first-time user cannot get into the app through the designed flow at all.

The mockups need one of:
- A separate "Create account" screen (`POST /auth/register` takes phone, optional name,
  optional email), with a link from login; **or**
- A combined screen where a `404 USER_NOT_FOUND` on login transparently reveals a
  name/email step and then calls register followed by login.

Either is fine. What cannot happen is login alone.

### 4.2 An unrated restaurant is `null`, not zero stars

`composite_rating` is `null` whenever `rating_count` is `0`. Right now **every seeded
restaurant is unrated**, so a realistic mockup shows mostly unrated cards.

[06_DESIGN_SYSTEM.md](./06_DESIGN_SYSTEM.md) §7.3 draws the Restaurant Card with `4.5★` and
gives no unrated variant. A card that renders `null` as `0★` or `0.0` tells travellers a
brand-new dhaba is terrible.

**Needed:** an explicit "New" / "Not yet rated" treatment on the card, the detail header, and
anywhere a rating appears.

### 4.3 "Hygiene rating" no longer exists

07 §3.4 specifies the detail header as "name, **hygiene rating** stars, distance, prep time".

There is no hygiene-only number in any response. The column was renamed `composite_rating`
and holds the **mean of three dimensions** — hygiene, food quality, timeliness — with
`rating_count` alongside. Ratings are collected per-dimension (Stage 13) but only ever
returned as the composite.

**Needed:** label it as an overall rating, and if the design wants a per-dimension breakdown
on the detail screen, that is a new endpoint nobody has specified.

### 4.4 The map has no route line to draw, and search is not corridor-based

Two related gaps:

- **`routes.geometry` is NULL for all five routes.** Polylines are generated offline by OSRM
  and have not been generated yet. 06 §9 specifies "Route polyline: `--color-accent`, 4 px"
  and a corridor buffer fill — **there is no polyline data for either.**
- **Search is point-radius, not corridor.** `route_id` is accepted and ignored. It exists to
  be recorded on a booking, not to filter.

So 07 §3.3's empty state — "No restaurants found **along this route**. Try expanding search
radius." — describes discovery the MVP does not perform. The map can show restaurant pins and
a user dot; it cannot show the highway corridor.

**Needed:** either copy and map visuals that describe a radius around a point ("within 15 km
of you"), or accept that the route line is a Stage 16 addition and mark it clearly as not-MVP
in the mockups.

### 4.5 The minimum arrival time is per-restaurant, and the design asks for it too early

07 §3.2 puts the arrival-time picker on the **Route Search** screen, before a restaurant is
chosen, with "Minimum booking time: now + 30 minutes".

The actual rule is that minimum lead time is **that restaurant's `avg_prep_time_minutes`**,
not a flat 30. Seeded values range **20 to 45 minutes**. A flat floor is wrong for a
restaurant with a 45-minute prep time, and the server enforces the real rule — an
`arrival_time` that is too soon will be rejected (`400 ARRIVAL_TOO_SOON`, Stage 11).

**Consequence:** a time that is valid when picked on the search screen can become invalid
after the user selects a restaurant. The design has no state for that.

Options, in rough order of how well they work:
- Move the time picker to the **booking screen**, after restaurant selection, where the real
  floor is known.
- Keep it on search as a rough intent, then re-validate on the booking screen and offer to
  adjust ("Gulshan Dhaba needs 45 minutes — earliest is 8:15 AM").
- Keep a conservative global floor of 45 min on search, which is wrong-but-safe for the
  current seed data and breaks as soon as a slower restaurant is onboarded.

### 4.6 Menus are longer than specified, and have categories

07 §3.4 says "Menu list (MVP: **3 hardcoded items** per restaurant)". Actual is **4 or 5
items**, each with a `category`. A mockup sized for three rows will overflow, and the design
does not say whether to group by category or show a flat list.

---

## 5. Data the design assumes but the API does not return

### 5.1 There are no images. Anywhere.

No restaurant photo, no dish photo, no logo URL, no image field of any kind on any response.
Menu items are exactly `{name, price, category}`.

06 §7.3 is consistent with this — the Restaurant Card shows `[Icon]`, not a photo. But if the
mockups add food photography or hero images, **there is no data behind it** and no plan to
add any in MVP (`menu_items` with R2 image URLs is Phase 2).

### 5.2 No sort, filter, or search-by-name

Results come back distance-ascending. There is no query parameter for sorting by rating
(07 §3.3 asks for one), no cuisine or veg/non-veg filter, no price band, no open-now, no
free-text restaurant search. Sorting client-side is possible; on today's all-`null` ratings it
would do nothing.

### 5.3 `source: "osm"` rows are thin, and the design never mentions them

Restaurants promoted from OpenStreetMap are real, bookable rows, but:

- `phone` is `""` — **empty string, not null**. 07 §3.4's "phone (tap to call)" has nothing to
  call. Needs a hidden/disabled state.
- `address` is often `null`.
- `avg_prep_time_minutes` is always 30 (a default, not a real figure).
- The menu is a **generic fallback**, identical across every OSM row.
- `composite_rating` is always `null`.

A mockup should say whether these are visually distinguished from onboarded restaurants. The
`source` field exists precisely so they can be.

### 5.4 No hours, no "open now", no closure state

`restaurants` has no opening-hours column. Nothing in the API says whether a dhaba is open,
and `is_active` is an operator approval flag — **not** an open/closed signal. Do not design
an "Open until 11 PM" chip.

### 5.5 No profile editing, no logout endpoint, no avatar

`GET /api/user/profile` is read-only; there is no `PUT`. There is no logout endpoint — a
token blocklist is Phase 2, so "log out" means discarding the locally stored token while it
remains valid server-side for up to 24 hours. There is no avatar or profile image field.

---

## 6. Screens whose backend does not exist yet

07 §3.5 (Booking), §3.6 (Booking Status), §3.7 (Rating), and §3.8 (Restaurant Dashboard) have
**no implemented endpoints**. Their contracts are specified in `05_API_SPEC.md` §7–§9 and are
being built in Stages 11–13. Designing against the spec is correct; just know that nothing has
been verified against a running server, and field names may still shift.

Two things about those screens that are already settled and worth designing to now:

**The five booking statuses are fixed:** `pending`, `confirmed`, `ready`, `handed_over`,
`cancelled`. 06 §2.3 lists exactly these with colours and icons — good. Legal transitions are
`pending → confirmed|cancelled`, `confirmed → ready|cancelled`, `ready → handed_over|cancelled`;
`handed_over` and `cancelled` are terminal. There is no "out for delivery" and no delivery at
all — this is pickup at the dhaba. Note 07 §8's stepper labels the last step "Picked up" while
the enum is `handed_over`; that is fine as display copy, just keep the mapping deliberate.

**The field is `arrival_time`** — when the traveller expects to arrive. It was renamed from
`booking_time`, which read as a creation timestamp. `cutoff_time` is derived from it.

**The restaurant dashboard cannot ship in a production build.** It authenticates with a
single shared `X-Restaurant-Token`, which is refused outright when `ENVIRONMENT=production`
(startup fails if the variable is set). So 07 §2's "Restaurant mode tab" is a demo-only
surface until per-restaurant accounts land in Stage 18. A mockup showing a restaurant
*login* screen is designing something that does not exist — there are no restaurant
accounts, just one shared secret. Masked phones on order cards are real:
`mask_phone` produces exactly `+919****3210`.

---

## 7. States the design docs do not cover but the server produces

| State | When | UI needed |
|-------|------|-----------|
| `429 RATE_LIMITED` + `Retry-After` header | Login 10/hr per phone; register 5/hr per IP; restaurant register 5/hr per user | Nothing in 07 covers a throttled state. Needs a "too many attempts, try again in N minutes" treatment |
| `503 SERVICE_UNAVAILABLE` on login | Production, where the OTP stub is refused and no SMS provider exists | "Phone verification is temporarily unavailable" — not a validation error, and not retryable by the user |
| `401 TOKEN_EXPIRED` (distinct from `UNAUTHORIZED`) | JWT past 24h | 07 §7 already says "Session expired" → login. The distinct code is what makes that reliable |
| `cached: true` on search | Second identical search within 6 hours | Optional, but results can be up to 6 hours stale and a newly activated restaurant will not appear until the key expires |
| `409 PHONE_ALREADY_REGISTERED` | Registering an existing phone | Should route the user to login rather than showing a dead-end error |

The OTP stub is `123456` and works only outside production, which matches 07 §3.1's "skip
send, show OTP field immediately". There is no real SMS in MVP (Stage 18).

---

## 8. Quick reference — current seed data

Useful for making mockups show plausible content.

- **Demo search point:** `29.02, 77.02` — NH-44 just south of Murthal. Use this everywhere.
- **10 restaurants**, all within 15 km. Nearest three: Gulshan Dhaba (1.1 km, 20 min),
  Amrik Sukhdev (1.2 km, 30 min), Murthal Dhaba (2.2 km, 25 min).
- Prep times range 20–45 min. All ratings `null`. All `source: "local"`.
- Menu prices range ₹15 (Tandoori Roti) to ₹320 (Laal Maas).
- **1 test user:** `+919876543210`, name "Priya Sharma".

Restaurant names are real Murthal-area dhabas; the phone numbers and exact coordinates are
invented placeholders.

---

## 9. Related documents

- [05_API_SPEC.md](./05_API_SPEC.md) — the authoritative contract, including unbuilt endpoints
- [06_DESIGN_SYSTEM.md](./06_DESIGN_SYSTEM.md) — tokens and components
- [07_UI_UX_GUIDELINES.md](./07_UI_UX_GUIDELINES.md) — screen specs and flows
- [14_BUILD_PLAN.md](./14_BUILD_PLAN.md) — what is built and what is next
