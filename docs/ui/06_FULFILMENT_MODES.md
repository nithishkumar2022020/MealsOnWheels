# Fulfilment Modes — including rider delivery

**Date:** 2026-08-01
**Status:** delivery is **in the product plan**, owner decision. Not in the MVP build.
**Extends:** [../16_FUNCTIONAL_PRODUCT_DATA.md](../16_FUNCTIONAL_PRODUCT_DATA.md) §3.4, which
defines three modes and predates this decision.

---

## 1. The question this settles

The Stitch mockups show a delivery product: a rider on a moped, live on a map, bringing food
to **seat 12A** of a moving bus. The backend, the charter, and `docs/README.md` say the
opposite — *"This is not a food delivery app. Food is ready when the traveller arrives."*

That is not a naming difference. Pickup needs a restaurant and a clock; delivery needs a
fleet, live positions, and money moving before handover.

The owner's answer: **both are part of the plan.** So this document treats delivery as a
real future mode and says precisely what it costs, rather than pretending the mockups fit
what exists or discarding them.

---

## 2. The four modes

| Mode | Ready by | Handover | Status |
|---|---|---|---|
| `bus_boarding_point` | `arrival − 5 min` | Traveller collects at the stop | 📋 `16` §3.4 |
| `self_drive_takeaway` | `arrival − 5 min` | Traveller collects at the counter | 📋 `16` §3.4 |
| `self_drive_dine` | `arrival` | Traveller eats in | 📋 `16` §3.4 |
| **`rider_delivery`** | **`rider_pickup_time`** | **Rider hands to seat** | **❌ this document** |

The first three share a shape: the restaurant is the last actor, and the traveller comes to
the food. `rider_delivery` inverts it — a third party collects and carries, and the deadline
is set by the rider's arrival at the restaurant, not the traveller's arrival anywhere.

**That inversion is why it cannot be a fourth enum value on the existing tables.**

---

## 3. What delivery needs that no side has

Neither the backend nor the design has modelled these. The mockups *depict* them, which is
not the same as specifying them.

### 3.1 Riders as an actor

There is no rider table, no rider auth, no rider app. The mockups show registration, document
upload (licence, RC, Aadhaar), a verification workflow, and a rider dashboard. That is a
third user type alongside travellers and restaurant staff — and restaurant staff auth is
*itself* still unbuilt (`16` §3.3).

Minimum: `riders`, `rider_documents`, verification states, rider JWT, plus an ops surface to
approve them. Aadhaar and licence images are regulated personal data — see §5.

### 3.2 Assignment

Something must decide which rider takes which order, and when. The mockups show a rider
already assigned; they do not show how. Assignment is the hard part of every delivery
product: batching, rejection, reassignment on no-show, surge.

### 3.3 Live location

"Rider is 2 mins away", a moving map pin, "0.8 km". Needs position ingestion at intervals,
storage, ETA computation, and a push channel to the client. `bus_gps_events` exists but is
explicitly unwritten and unread in MVP (ADR-0010), and it models *bus* positions, not riders.

The architecture also commits to **polling, not WebSocket** — adequate for order status
every 10 s, visibly wrong for a moving dot.

### 3.4 Payment before handover

Pickup is pay-at-counter, which is why the backend has no payment integration. Delivery
cannot be: a rider will not front the bill. The mockups show a wallet with a balance, UPI,
cards, promo codes, delivery fees, taxes, and refunds — a payments subsystem, PCI scope, a
refund path, and reconciliation.

`bookings.payment_status` is `pending|paid` and nothing in the codebase ever sets `paid`.

### 3.5 Seat and vehicle capture

Delivery is to `Bus RJ-14-PB-1234, Seat 12A at Ambala Cantt Stop`. Nothing in `bookings`
records a vehicle, a seat, or a stop. Bus identity is also not something the traveller
reliably knows in advance — it changes with operator substitutions.

### 3.6 A bus that moves

The deepest problem. Pickup has a fixed rendezvous: a restaurant with a known location and a
traveller who arrives. Delivery has **two moving parties** and a window measured in the
seconds a bus is stationary at a stop. A late rider misses the bus entirely, and the food
cannot be re-delivered.

That is not an engineering detail — it is the core operational risk, and no mockup addresses
what happens when it fails.

---

## 4. Phasing

Delivery is roughly a product of its own. The recommendation is to ship pickup first and
build delivery behind it, because pickup is nearly done and delivery has not started.

| Phase | Scope | State |
|---|---|---|
| **A — Pickup MVP** | Three non-delivery modes end to end | Backend Stages 7–10 done, 11–14 next |
| **B — Owner-managed data** | Menus, hours, staff accounts | `16`, needs sign-off |
| **C — Payments** | Prerequisite for delivery, useful alone | Not designed |
| **D — Delivery** | Riders, assignment, live tracking, seat capture | Not designed |

Phase C before D is deliberate: payments is independently valuable — prepaid pickup reduces
no-shows — and it is the largest single dependency delivery has.

---

## 5. Two things to decide before building D

**Regulated data.** Licence, RC, and Aadhaar images are personal data under India's DPDP Act.
Aadhaar in particular has specific handling rules and should not be collected without a clear
lawful basis. `10_SECURITY.md` currently has no provision for document storage, retention, or
deletion. Decide whether Aadhaar is genuinely needed — many delivery platforms verify on
licence alone.

**The missed-bus case.** If the rider does not make it, who bears the cost — traveller,
restaurant, rider, or platform? This drives refund logic, rider payment, and the cancellation
UI, and it should be answered before code, not after the first complaint.

---

## 6. What this means for the UI now

The delivery screens are **not blocked** as design work — they are the reference for Phase D.
For the Flutter app being built now:

- Build the three pickup modes. `select_booking_type_vibrant` ships with three options.
- Structure routing and state so a fourth mode slots in without rework — see
  [04_FLUTTER_ARCHITECTURE.md](./04_FLUTTER_ARCHITECTURE.md).
- Do **not** build the tracking screens against invented data. A live map with fabricated
  positions is worse than an honest status stepper: it teaches travellers to trust a number
  that is not real.
- Keep the delivery mockups in `mockups/`. They are the spec for Phase D.

---

## 7. Related

- [../16_FUNCTIONAL_PRODUCT_DATA.md](../16_FUNCTIONAL_PRODUCT_DATA.md) — three modes, prep formula
- [../15_DESIGN_BACKEND_ALIGNMENT.md](../15_DESIGN_BACKEND_ALIGNMENT.md) §2.1 — why `booking_type` matters
- [02_SCREEN_INVENTORY.md](./02_SCREEN_INVENTORY.md) §6 — the delivery screens
- [../00_PROJECT_CHARTER.md](../00_PROJECT_CHARTER.md) — the "not a delivery app" scope line
