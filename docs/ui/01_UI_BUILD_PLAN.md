# UI Build Plan & Handoff Log

**Status:** Phase C starts now. No Flutter code has been written.
**Parent:** [../14_BUILD_PLAN.md](../14_BUILD_PLAN.md)

---

## 1. Purpose

The same resumability contract as the backend plan. Every stage ends in a working state.
The next person continues from this document, not from their memory.

---

## 2. What exists

| Artefact | Location |
|----------|----------|
| 63 Stitch mockups (57 distinct) | `mockups/` |
| Resolved design tokens (crimson) | `03_DESIGN_TOKENS.md` |
| Per-screen inventory with backend readiness | `02_SCREEN_INVENTORY.md` |
| Flutter architecture and conventions | `04_FLUTTER_ARCHITECTURE.md` |
| Screen → API wiring, every endpoint and error | `05_SCREEN_API_WIRING.md` |
| Fulfilment-mode analysis (incl. delivery) | `06_FULFILMENT_MODES.md` |
| Validated backend contract | `../FRONTEND_CONTRACT.md` |

A Flutter project has **not been created** — `mobile/` does not exist. Stage 1 creates it.

---

## 3. Stages

### Phase A — Scaffold (no backend needed)

| # | Stage | Status | Deliverable |
|---|-------|--------|------------|
| 1 | `flutter create` + theme + dio + Riverpod | TODO | `mobile/` compiles; `AppTheme` renders the crimson palette; `ApiClient` with error interceptor |
| 2 | Auth screens — welcome, login, register | TODO | Login calls the real backend; `404 USER_NOT_FOUND` branches to registration |
| 3 | Route selection | TODO | Dropdown from `GET /api/routes`; no map, no corridor |
| 4 | Home dashboard | TODO | Composite screen; degrade gracefully on sections whose backend doesn't exist |
| 5 | Restaurant list + map | TODO | `ST_DWithin` search; list and map views; MapLibre pins; rate-limit UX |
| 6 | Restaurant menu + cart | TODO | Menu from detail; in-memory cart; client-side total preview |
| 7 | Empty, error, edge states | TODO | Wire all the negative screens — this is its own stage so they don't get skipped |

### Phase B — Backend-dependent

| # | Stage | Status | Backend stage | Deliverable |
|---|-------|--------|---------------|------------|
| 8 | Checkout + booking creation | TODO | Stage 11 🔨 | `POST /bookings/create` with item name + qty only |
| 9 | Booking status + polling | TODO | Stage 11 🔨 | Status stepper, 10 s poll, stop on terminal |
| 10 | Order history | TODO | Stage 11 🔨 | `GET /bookings`; All/Completed/Cancelled |
| 11 | Rating | TODO | Stage 13 🔨 | Three 1–5 dimensions; requires `handed_over` |
| 12 | Restaurant admin dashboard | TODO | Stage 12 🔨 + 📋 | Order feed with transitions |
| 13 | Menu management | TODO | 📋 | Owner CRUD; soft delete; availability toggle |
| 14 | Operating hours + settings | TODO | 📋 | Per-weekday hours; accepting-orders toggle |

### Phase C — Delivery

**Prerequisite:** a working delivery backend (nothing exists today). Do not start these until
`rider_delivery` has a schema and an assignment model.

| # | Stage | Status |
|---|-------|--------|
| 15 | Rider sign-up, login, documents | TODO |
| 16 | Live order tracking | TODO |

---

## 4. Next Action

**Stage 1 — Flutter scaffold.**

Create the project, apply the crimson theme from `03_DESIGN_TOKENS.md`, set up `dio` with the
error interceptor from `04_FLUTTER_ARCHITECTURE.md`, wire Riverpod, add `go_router` with
placeholder routes, and add `flutter_secure_storage`. No backend integration yet — just a
compilable skeleton that the next person typing `flutter run` sees crimson, a button, and a
logged error.

The big compile-time catches to verify: `Decimal`, `freezed`, `json_serializable`, and
`go_router` imports resolve.

### Verify before claiming any stage done

```bash
cd mobile
dart run build_runner build --delete-conflicting-outputs
flutter analyze                  # must be clean, not "only warnings"
flutter test
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api
```

The last one matters most: a screen that compiles and has never rendered against the real
backend is not done. Backend must be up — `docker compose up -d` then
`docker compose exec backend python scripts/seed.py`.

---

## 5. Decisions

| Date | Decision | Reason |
|------|----------|--------|
| 2026-08-01 | Two palettes resolved to crimson `#b7122a` ✓ | Owner chose the "Vibrant Transit" theme over the teal alternative |
| 2026-08-01 | Montserrat + Inter, not Montserrat-only ✓ | Stitch theme spec defines the dual-font pairing; the 18 Inter screens are right |
| 2026-08-01 | Four fulfilment modes — pickup three + rider delivery ✓ | Owner confirmed both pickup and delivery are in scope |
| 2026-08-01 | Payments is a prerequisite for delivery ✓ | Delivery cannot be pay-at-counter; rider delivery without payment is not a thing |
| 2026-08-01 | `price` field never sent to the server ✓ | Defended by `extra="forbid"` on every request schema. A `price` in a booking body is a 422 |
| 2026-08-01 | Money stored as `Decimal`, API sends string ✓ | `0.1 + 0.2 != 0.3` in binary floating point, and these are summed into a `NUMERIC` column |

---

## 6. Deferred / discovered

- **No Flutter test runner is configured** — `flutter_test` is in scope from Stage 0 per
  project convention. Wire it in Stage 1 alongside the scaffold.
- `flutter analyze` will flag unused imports in a scaffold; ignore until Stage 2 when the
  first real screen lands.
- `mobile/` does not exist yet. `flutter create` in the project root.
