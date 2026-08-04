# Design vs Backend — Alignment Review

**Date:** 2026-07-31
**Question:** are the frontend design and the backend heading in the same direction, and
where they diverge, which one is right?

Not a compliance audit. Field names are not a difference in direction, and an earlier
version of this document scored them as if they were — producing a "0% compliance" figure
that measured spelling rather than substance. What follows is a judgment call on each real
divergence.

---

## 1. Verdict

**They agree on the product. They disagree on details, and the design is right more often
than the backend is.**

Both describe the same thing: travellers pre-order along a highway route, restaurants
confirm and prepare against a stated arrival, food is ready on arrival, pay at the counter,
rate afterwards. Same actors, same lifecycle (`pending → confirmed → ready → handed_over`),
same anxieties (hygiene, timeliness), same market. Nothing in the design suggests a product
the backend was not built for.

The divergences sort into four kinds, and only the first is urgent:

| | Count | Urgency |
|---|---|---|
| **Design is ahead** — real product surface the backend lacks | 5 | **Before Stage 11** |
| **Backend is ahead** — design would introduce a defect | 4 | Amend the design |
| **Both half-right** — the answer is a synthesis | 3 | Decide once, cheaply |
| **Coin flips** — naming, no argument either way | ~12 | Adopt the design's |

---

## 2. Where the design is ahead

These are not naming differences. They are things the product needs that the backend has no
way to express.

### 2.1 `booking_type` — the significant one

The design distinguishes three fulfilment modes:

```
bus_boarding_point | self_drive_dine | self_drive_takeaway
```

The backend has **one**. This concept appears nowhere in the repository's sixteen spec
documents.

It matters because the three are genuinely different products sharing an order flow. A bus
passenger with a twenty-minute halt needs food bagged and waiting at a boarding point — the
handover is the whole transaction, and being two minutes late fails it. A self-drive family
who want to sit down needs a table and no urgency at all; `ready_by = arrival − 5 min` is
actively wrong for them, since food plated five minutes early sits and cools while they
park. Takeaway sits between the two.

Consequences the backend cannot currently express:

- **Prep timing differs per mode.** The single `ready_by` formula suits takeaway, is tight
  for bus, and is wrong for dine-in.
- **The dashboard queue differs.** A kitchen prioritising a bus handover at 07:30 against a
  dine-in at 07:30 is doing two different jobs. One is a hard deadline; the other is a
  seating.
- **Cancellation risk differs.** A bus that leaves without its passenger is a total loss; a
  driver running late just arrives late.

This is the one item that should land **before** bookings are built, because it changes the
`bookings` table and the dashboard grouping. Bookings are the next stage.

### 2.2 No opening-hours model

The design expects a booking to be rejected when a restaurant is closed — by an owner
toggle *or* by time of day. The backend has `is_active` (a soft delete) and nothing else.

For a product whose entire premise is time-aligned pickup, being unable to represent "we are
shut at 3am" is a substantive gap. Today a traveller can book breakfast at a dhaba that
will not open for six hours, and nothing in the system objects.

### 2.3 Menus as data, not code

The design has a real `menu_items` table: stable `menu_item_id`, `description`,
`prep_time_minutes`, `is_available`, `image_url`. The backend hardcodes three items per
restaurant in `app/services/menu.py`.

The design's instinct is right, and the hardcoding has a consequence beyond inconvenience:
because menu items have no IDs, the design's `menu_item_id` on a booking line cannot be
honoured, and per-item availability ("we're out of paneer") cannot be expressed at all.
This was scheduled as a Phase 1 item; it is really a prerequisite for bookings.

### 2.4 Restaurant login as a first-class thing

The design assumes restaurants authenticate properly — `POST /restaurant/auth/login`
returning a JWT scoped to a `restaurant_id`. The backend uses a shared static
`X-Restaurant-Token`, gated to non-production, with real per-restaurant auth deferred to
Stage 18.

The backend was being expedient and the design is simply right. The shared token cannot
distinguish one restaurant from another, which is why it had to be paired with a separate
ownership check on every mutation. A `restaurant_id` claim in a token removes that whole
class of problem. Worth pulling forward.

### 2.5 Lifecycle timestamps

The design records `confirmed_at`, `ready_at`, `handed_over_at`. The backend stores only the
current status and a generic `updated_at`.

Without those columns the project's own north-star metric — "food ready within ±10 minutes
of stated arrival" (`00_PROJECT_CHARTER.md` §9) — is **not computable**. The charter commits
to measuring `ready_at` against arrival, and there is no `ready_at`. Three nullable
timestamp columns close it.

Also worth taking: order history (`GET /bookings`) does not exist in the backend at all, and
the design's `items_summary` as a pre-formatted string is a sensible payload choice for a
list view.

---

## 3. Where the backend is ahead

### 3.1 Client-supplied prices — the design should change

The design's booking request carries `price: 120` per line. The backend refuses this and
resolves every unit price from its own menu.

This is not a preference. A request body is attacker-controlled; accepting a price means
accepting two paranthas for ₹0.02. Keep the design's `menu_item_id` — it is an improvement,
and it makes server-side lookup cleaner — and drop `price` from the request. The response
should still echo resolved prices so the client can render the priced order.

### 3.2 Flat 30-minute cutoff — the design is wrong for this product

The design specifies `cutoff_time = booking_time − 30 minutes`, flat. The backend uses
`arrival_time − restaurant.avg_prep_time_minutes`.

Concretely: a dhaba whose biryani takes 45 minutes, given an order at a 30-minute cutoff,
has been handed a deadline it cannot meet. The system will show `confirmed`, the traveller
will arrive expecting food, and it will not be ready. The failure is silent and it lands on
the restaurant.

Since `avg_prep_time_minutes` already exists per restaurant and is already collected at
registration, the flat figure discards information the system has. Keep the per-restaurant
formula; the design can keep showing "about 30 minutes" in copy.

### 3.3 HTTP 500 when Overpass is down

The design's example returns 500 when the POI service fails; its own checklist says the
opposite two lines later ("return fallback or empty array, not crash"). The backend returns
seeded local restaurants and a 200. A partial result is not an outage, and OSM coverage gaps
are exactly why local seeding exists.

### 3.4 `refund_amount` on cancellation

The design returns `refund_amount: 340`. Payment is on arrival — no money has been taken.
Telling a traveller they are being refunded ₹340 they never paid is worse than saying
nothing. Drop the field until online payments exist (Phase 2), then it becomes correct.

---

## 4. Where both are half-right

### 4.1 Rating — display hygiene, but do not discard the rest

The design's headline number is `hygiene_rating` (hygiene scores only). The backend's is
`composite_rating` (mean of all three).

The design's instinct is good and I initially read it as an error. For highway food the
purchase anxiety is specifically *will this make me ill* — not "was it tasty". Surfacing
hygiene as the headline is real product thinking.

But it wastes two-thirds of what is collected. **Both:** store all three separately (both
already agree on this), show hygiene as the primary number because that is the anxiety, and
expose the composite alongside. One extra field, no lost information, and the naming
collision that prompted the original `composite_rating` rename disappears because both names
now mean what they say.

### 4.2 Error envelope

The design specifies `{error, message}`; the backend uses `{detail, code}`. `error` and
`detail` are the same thing.

The real difference is that the design has `message` — user-displayable text — and the
backend has `code` — a machine-readable branch key. **A client needs both**, and they are
not substitutes: you cannot branch on prose, and you cannot show `ARRIVAL_TOO_SOON` to a
traveller. Emit `{error, message, code}`.

(The design also mandates a `{data, message, status}` wrapper in Part 8 that none of its own
sixteen examples use. The examples are right — HTTP already carries the status, and the
wrapper adds a layer of unwrapping on every call for nothing.)

### 4.3 `booking_time` vs `arrival_time`

The backend renamed this deliberately: every formula treats the value as *when the traveller
arrives*, while `booking_time` reads as *when the booking was made*. `cutoff_time =
booking_time − 30 min` is genuinely confusing to a new reader.

But the design is drawn against `booking_time`, and this is internal clarity versus external
churn. **Map at the boundary:** `booking_time` on the wire, `arrival_time` in the database
and application code. One line in the response schema.

---

## 5. Coin flips — take the design's

No argument either way; the design is already drawn, so it wins by default:

`jwt_token` over `access_token` · flat `user_id` over nested `user.id` ·
`latitude`/`longitude` over `lat`/`lon` · `special_notes` over `notes` ·
`time_until_cutoff_seconds` over minutes · `start_city`/`end_city` over
`origin_name`/`dest_name` · `/health` alongside `/api/health`

One of these is worth noting: the backend is currently **inconsistent with itself** —
`POST /restaurants/register` accepts `latitude`/`longitude` while `GET /restaurants/search`
returns `lat`/`lon`. Adopting the design's names fixes an existing bug rather than
introducing churn.

Phone masking differs by one character (`+91****3210` vs `+919****3210`). Take the design's;
it reveals less.

---

## 6. What this means for the build

The order that matters:

1. **`booking_type` and opening hours** — schema, and both change the `bookings` table.
   These must land before bookings are built, which is the next stage. Everything else can
   follow at any time.
2. **`menu_items` table** — prerequisite for `menu_item_id` on booking lines.
3. **Lifecycle timestamps** — three nullable columns, and the charter's headline metric
   starts working.
4. **Error envelope + field renames** — mechanical, touches every endpoint, roughly half a
   day, best done in one pass rather than trickled.
5. **Per-restaurant JWT** — pull forward from Stage 18; removes a whole class of
   authorisation risk.

Items 1–3 are schema changes and should go in one migration while the `bookings` table is
still empty. After that the remaining stages build against a contract both sides agree on.

The design should be amended on four points (§3) before anyone builds to it.
