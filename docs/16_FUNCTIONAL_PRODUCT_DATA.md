# Making Product Data Functional — UI and Backend Changes

**Date:** 2026-08-01
**Supersedes on this topic:** [15_DESIGN_BACKEND_ALIGNMENT.md](./15_DESIGN_BACKEND_ALIGNMENT.md) §2.3
**Status:** proposal — needs sign-off before Stage 11 (bookings)

Menus, hours, and prep times are **owner-managed data**, not fixtures. That changes both
sides more than it first appears, because it introduces an actor neither side has fully
modelled: a restaurant owner who edits things while travellers are mid-booking.

---

## 1. What changes, in one line

Today the catalogue is a constant, so it cannot be wrong, cannot be stale, and cannot
disappear between browsing and paying. Once an owner can edit it, all three become possible,
and **the interesting work is in the races, not the CRUD.**

The CRUD itself is routine: a `menu_items` table, five endpoints, a management screen.
What needs deciding is what happens when an owner marks paneer unavailable while forty bus
passengers have it in their cart.

---

## 2. The three-way overload on `is_active`

This is the highest-value backend fix and it is cheap. `is_active` currently means two
things and the design wants it to mean a third:

| Meaning | Who sets it | Changes how often |
|---|---|---|
| "an operator has approved this listing" | ops, once | ~never |
| "exclude from search results" | derived | ~never |
| "we are open for orders right now" | **owner, from a kitchen tablet** | **several times a day** |

Collapsing these is a live bug waiting to happen: an owner tapping *Closed* at the end of a
shift would flip the same flag that means *unapproved*, and the only documented way back is
an operator. Split into three:

```
approval_status       pending | approved | rejected     ← ops
is_accepting_orders   boolean                           ← owner toggle, resets daily
opening_hours         per-weekday windows               ← owner, set once
```

A restaurant is **bookable** when `approval_status = 'approved'` **and**
`is_accepting_orders` **and** now falls inside `opening_hours`. Three independent facts, and
each has a different owner and a different lifetime. This split also fixes the current gap
where a traveller can book breakfast at a dhaba that will not open for six hours.

---

## 3. Backend changes

### 3.1 `menu_items` — and how it interacts with frozen booking lines

```
menu_items
  id                  BIGSERIAL PK
  restaurant_id       BIGINT NOT NULL → restaurants(id)
  name                VARCHAR(200) NOT NULL
  description         TEXT
  price               DECIMAL(10,2) NOT NULL      -- still the only price source
  category            VARCHAR(50) NOT NULL
  prep_time_minutes   INTEGER                      -- NULL = use restaurant default
  is_available        BOOLEAN NOT NULL DEFAULT true -- today's stock
  image_url           TEXT
  display_order       INTEGER NOT NULL DEFAULT 0   -- owner's ordering, not alphabetical
  deleted_at          TIMESTAMPTZ                  -- soft delete
  created_at, updated_at
```

Three decisions embedded there:

**`is_available` is separate from `deleted_at`.** "Out of paneer today" and "we stopped
selling this" are different actions with different reversibility. Conflating them means an
owner has to re-create a dish tomorrow.

**Soft delete, and `bookings.items` keeps no foreign key.** Booking lines already freeze
`{name, qty, price}` at order time so a later price edit cannot alter a placed order. Add
`menu_item_id` to each line as a **plain integer, not an FK** — useful for analytics,
but a hard constraint would make deleting a discontinued dish either fail or cascade into
historical orders. The frozen snapshot is what the order is; the id is a hint about where it
came from.

**`display_order`, not alphabetical.** The design says "sorted by category (alphabetical or
custom)". Owners will want breakfast before dessert. Alphabetical puts *Beverage* first.

**Price edits do not need versioning.** Freezing onto the booking line already gives point-in-time
correctness, which is the only reason versioning was tempting. A `menu_item_price_history`
table is Phase 2 if anyone ever wants price analytics.

### 3.2 `restaurant_hours`

```
restaurant_hours
  restaurant_id  BIGINT → restaurants(id)
  weekday        SMALLINT   -- 0=Monday
  opens_at       TIME
  closes_at      TIME
  PRIMARY KEY (restaurant_id, weekday)
```

Plus `restaurants.timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata'` — the design is right to
want this, and it is load-bearing rather than cosmetic. Cutoff validation asks "is
07:30 UTC inside Monday 06:00–23:00 **local**", which cannot be answered without the zone.
Highway dhabas often run past midnight, so allow `closes_at < opens_at` to mean an overnight
window rather than rejecting it.

Absent rows should mean **closed**, not open-all-day: a newly approved restaurant that has
not set hours should not silently accept 3am orders.

### 3.3 Restaurant owner accounts — the gap neither side has

Both sides assume a restaurant "logs in", but neither models *who*. `restaurants.phone` is a
contact field, not an identity, and the design's `POST /restaurant/auth/login` returns a
`restaurant_id` without saying what authenticates against it.

Minimum viable:

```
restaurant_users
  id              BIGSERIAL PK
  restaurant_id   BIGINT NOT NULL → restaurants(id)
  phone           VARCHAR(20) NOT NULL UNIQUE
  name            VARCHAR(100)
  created_at, updated_at
```

One row per person, `restaurant_id` on the row. This costs nothing now and means a dhaba
with an owner *and* a manager — or an owner with two outlets — does not need a migration
later. The JWT carries `restaurant_id` as a claim, which retires the shared
`X-Restaurant-Token` and the separate ownership check it required.

### 3.4 Booking modes

`restaurants.supported_booking_types TEXT[]` and `bookings.booking_type`. The prep formula
becomes mode-dependent, which is the substantive part:

| Mode | Ready by | Why |
|---|---|---|
| `bus_boarding_point` | `arrival − 5 min` | Hard deadline; bagged and waiting |
| `self_drive_takeaway` | `arrival − 5 min` | Same, softer failure |
| `self_drive_dine` | `arrival` | Food plated early cools while they park |

A restaurant supporting no modes cannot be approved.

### 3.5 Endpoints

New, owner-authenticated (`restaurant_id` from the JWT — never from a query parameter):

```
GET    /api/restaurant/menu
POST   /api/restaurant/menu
PUT    /api/restaurant/menu/{item_id}
DELETE /api/restaurant/menu/{item_id}          -- soft
PATCH  /api/restaurant/menu/{item_id}/availability
PUT    /api/restaurant/hours
PATCH  /api/restaurant/accepting-orders
PUT    /api/restaurant/settings
POST   /api/restaurant/auth/login
```

Changed:

- `GET /restaurants/{id}` — menu from the table, unavailable items included but flagged so
  the client can grey them rather than silently hiding a dish someone is looking for
- `GET /restaurants/search` — filter on all three bookability facts; accept `booking_type`
  and exclude restaurants that do not support it
- `POST /bookings/create` — validate the item is available *and* the restaurant is open at
  `arrival_time` in its own timezone

### 3.6 The race, and where to resolve it

An owner marks paneer unavailable while a traveller has it in their cart. Two candidate
rules:

- **Reject the whole booking** — safe, and infuriating for an order of six items where one
  is gone.
- **Partial accept** — drop the line, recompute the total, tell the client. Requires the UI
  to handle a total that changed after confirmation, which is a worse surprise than an error.

**Recommend rejecting, with a specific error** naming the item and code
`ITEM_UNAVAILABLE`, so the client can send the traveller back to the menu with that dish
greyed out. One clear failure beats a silent mutation of what someone agreed to pay. Same
rule for a price that changed between browsing and confirming — reject with
`PRICE_CHANGED` rather than charging a total the traveller never saw.

This is the one place where being strict is worth an extra tap.

---

## 4. UI changes

### 4.1 Restaurant side — mostly missing today

The design covers a settings screen and an order dashboard. Functional menus need more, and
the constraint is that every one of these is used **one-handed, on a tablet, in a working
kitchen**.

**Menu management** — list grouped by category, drag to reorder, add/edit/delete. Editing
needs a plain form: name, description, price, category, prep time, image, availability.

**Availability toggle belongs on the dashboard, not in settings.** This is the most
frequently used control in the entire product — running out of a dish happens mid-service —
and it must be one tap from the order queue. Burying it three screens deep in settings
guarantees stale menus, which is the failure that makes travellers stop trusting the
platform.

**"Closed now" toggle**, same reasoning, same placement. Prominent, unambiguous, and it
should say what it does: *"You will not receive new orders until you reopen."*

**Hours editor** — seven rows, copy-to-all-days shortcut. Set-once, so it can live in
settings.

**An onboarding checklist.** Because approval now depends on having a menu, hours, and at
least one booking mode, an owner needs to see why they are not live yet:

```
Not live yet
  ✓ Profile             ✓ Hours
  ✗ Menu — add at least one item
  ✗ Booking types — choose at least one
```

Without this, `approval_status = 'pending'` is silent and the owner assumes the platform is
broken.

### 4.2 Traveller side

**Booking type comes early — before the restaurant list.** It filters which restaurants are
eligible, so asking after selection means showing a dhaba and then withdrawing it. It also
sets expectations: a bus passenger and a family choosing a lunch stop are shopping
differently.

**Search results carry open/closed state.** Closed restaurants should be *visible but
unbookable* with "Opens at 6am", not hidden — a traveller who knows a place and cannot find
it assumes the app is wrong. Hiding also makes an empty result set indistinguishable from a
coverage gap.

**Menus show unavailable items greyed out**, not omitted, for the same reason.

**The arrival-time picker must respect hours and prep time.** It should not offer 3am for a
place that opens at 6, nor a slot inside the prep window. This is where the backend's
per-restaurant prep time becomes visible: the earliest selectable time is
`now + avg_prep_time_minutes`, which differs per restaurant — the UI cannot hardcode 30
minutes.

**A reconciliation state between menu and confirmation.** New screen state, not a new
screen: *"Paneer Paratha is no longer available. Update your order?"* This is where §3.6's
rejection surfaces, and without it the strict rule reads as a random failure.

**Show what the rating means.** If hygiene is the headline number (§4.1 of the alignment
review), label it. An unlabelled 4.2 next to a restaurant implies overall quality, and the
whole point of leading with hygiene is that travellers are asking a specific question.

---

## 5. Sequencing

Stage 11 is bookings, and bookings depend on menu items having IDs and on knowing whether a
restaurant is open. So:

1. **One migration** — `menu_items`, `restaurant_hours`, `restaurant_users`, the
   `is_active` split, `timezone`, `supported_booking_types`, `booking_type`, lifecycle
   timestamps. All of it while `bookings` is still empty. One migration, not six, because
   they interlock and a half-applied schema is worse than either end state.
2. **Restaurant auth** — every new endpoint needs `restaurant_id` from a token, so this
   comes before the CRUD rather than after.
3. **Menu + hours CRUD**, and port the seed script from `menu.py` constants into rows so
   the seeded corridor keeps working.
4. **Then bookings**, with availability and hours validation, against real data.

Steps 1–3 are the new work. They are what "functional" costs, and they are cheaper now than
after bookings exist.

## 6. What this does not change

The price boundary. Prices move from a Python constant to a database row, but they are still
resolved **server-side, from the server's own record**, and still frozen onto the booking
line at order time. A client still cannot propose a price. That was never about hardcoding —
it was about not trusting the request body.
