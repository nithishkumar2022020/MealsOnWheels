# Build Plan & Handoff Log

**Document version:** 1.0
**Last updated:** 2026-08-04 (Stage 10.5c complete — owner-managed product data)
**Purpose:** Single source of truth for build progress. Any agent or contributor picking
this project up mid-stream starts here.

---

## 1. How to use this document

Each stage below is a **self-contained unit of work that ends in a working state**. The
rule is deliberate: if work stops after any stage, the repository is coherent and the next
person continues from a clean boundary rather than reassembling half-finished changes
scattered across modules.

**Before starting work:** read §3 to find the first stage not marked `DONE`.

**Before stopping work:** update that stage's row in §3, add anything you learned to §5,
and make sure §4 (Next Action) names the exact next step. Assume you will not be available
to explain your reasoning.

**Stage status values:** `TODO` · `IN PROGRESS` · `DONE` · `BLOCKED`

---

## 2. Context: what changed on 2026-07-29

The original plan was a **24-hour sprint with parallel agent streams**. That constraint no
longer applies — there is no deadline, and the priority is now correctness and
resumability over speed.

Consequences, applied throughout the doc set:

- Automated tests are **in scope from the start**, not deferred. The CI test gate is on.
- Shortcuts that were justified only by the deadline are being fixed now rather than
  booked as Phase 1 debt — notably the client-supplied price trust boundary and the
  unauthenticated restaurant dashboard.
- Stream labels (A–E) are retired. Work is sequenced by the stages in §3 instead, because
  sequential stages are resumable and parallel streams are not.
- "No refactoring during sprint" is withdrawn.

Shortcuts **still deliberately accepted** (all documented, all gated):

| Shortcut | Why kept | Gate |
|----------|----------|------|
| OTP stub `123456` | No SMS provider yet; blocks nothing else | `ENVIRONMENT != production` |
| Point-radius search | Route polylines not seeded yet | Corridor query is Stage 16 |
| JSONB booking items | Normalising costs a join for no gain while a booking is always read whole | Line items freeze name and price at order time |
| Polling, not WebSocket | Adequate at current scale | — |
| No operator UI for approving a restaurant | Approval is a database update by an operator | Self-registrations land `is_active = false` and are never searchable |

**Retired since**, because the reason for keeping them stopped applying:

| Was | Now | Why it could not wait |
|-----|-----|-----------------------|
| Shared restaurant dashboard token | Per-restaurant JWTs (`typ` + `rid`), Stage 10.5b | A shared secret cannot distinguish one restaurant from another, so authorization rested on the client volunteering an honest `restaurant_id` |
| Hardcoded menus | `menu_items`, owner-managed, Stage 10.5c | Menus had to be real before bookings priced against them; a fabricated menu quotes a price no restaurant agreed to |

---

## 3. Stages

### Phase A — Specification correction

The spec is being built against, so defects in it become defects in code. Fixed first.

| # | Stage | Status | Ends when |
|---|-------|--------|-----------|
| 0 | Continuity scaffolding — root `README.md`, `CLAUDE.md`, this document | DONE | A new agent can orient itself from the repo alone |
| 1 | Fix demo-breaking and factual doc errors | DONE | Documented example inputs actually work against documented seed data |
| 2 | Retire 24-hour sprint framing across docs | DONE | No doc justifies a shortcut with a deadline that has passed |
| 3 | Apply correctness fixes to product/DB/API specs | DONE | `arrival_time` rename landed; price trust boundary closed in spec; rating model coherent |
| 4 | Close security gaps in the spec | DONE | Every write endpoint has a documented auth requirement; no "obscure URL" mitigations |
| 5 | Resolve the OSM-result-not-bookable defect | DONE | Every search result carries a real integer `id` that satisfies the booking FK |
| 6 | Operational and doc-hygiene cleanup | DONE | Retention, cache TTL, Alembic baseline, observability, Node residue all resolved |

### Phase B — Backend implementation

Each stage is independently runnable and independently testable.

| # | Stage | Status | Ends when |
|---|-------|--------|-----------|
| 7 | Backend skeleton, config, DB schema, health check | DONE | `docker compose up` → `GET /api/health` returns 200 with db + redis status |
| 8 | Auth module — register, login, JWT, profile | DONE | `pytest tests/test_auth.py` green; login returns a usable token |
| 9 | Routes module + seed script | DONE | Seeded DB; `GET /api/routes` returns 5 routes |
| 10 | Restaurant search, detail, register | DONE | `tests/test_restaurants.py` green including Overpass-down fallback |
| 10.5a | Migration 002 — owner-managed product data schema | DONE | Six new/changed tables; migration idempotent; approval backfill guarded |
| 10.5b | Per-restaurant auth (JWT with `typ` + `rid`) | DONE | `tests/test_restaurant_auth.py` green including the actor-collision test |
| 10.5c | Menu + hours CRUD, bookability from the database | DONE | `tests/test_restaurant_admin.py` green; menus served from `menu_items` |
| 11 | Booking module + state machine | TODO | `tests/test_bookings.py` green including every invalid transition |
| 12 | Dashboard module + restaurant token auth | TODO | `tests/test_dashboard.py` green including cross-restaurant denial |
| 13 | Ratings module + aggregate recompute | TODO | `tests/test_ratings.py` green; restaurant aggregate updates on rating |
| 14 | CI workflow, migrate script, gitignore | TODO | CI config passes against the real backend |

### Phase C — Client and hardening (not yet started)

Deliberately unplanned in detail. Scope these when Phase B is done, not before.

| # | Stage | Status |
|---|-------|--------|
| 15 | Flutter client — login, search, book, status, rating | TODO |
| 16 | PostGIS corridor search replacing point-radius | TODO |
| 17 | Restaurant dashboard web console | TODO |
| 18 | Real SMS OTP (unblocks public launch) | TODO |
| 19 | Self-hosted Nominatim / Overpass (usage policy compliance) | TODO |

---

## 4. Next Action

**Stage 11 — booking module and state machine.**

Phase A and Stages 7–10 are complete and verified. Do not re-open the Phase A decisions;
they are recorded in §5 with reasons.

### What already exists (build on it, do not rewrite)

| File | What it gives you |
|------|-------------------|
| `app/config.py` | `get_settings()`; `.otp_stub_allowed`, `.is_production` |
| `app/db.py` | `Base`, `SessionLocal`, `get_db`. `NullPool` under `ENVIRONMENT=test` — see §5 |
| `app/cache.py` | `get_json()` / `set_json()` / `incr_with_expiry()`. All fail open |
| `app/errors.py` | `unauthorized()`, `forbidden()`, `not_found()`, `conflict()`, `validation_error()` |
| `app/models.py` | `Booking`, `ALLOWED_TRANSITIONS`, and `Booking.can_transition_to()` |
| `app/schemas.py` | `RequestModel` (`extra="forbid"`) / `ResponseModel` bases |
| `app/deps.py` | `CurrentUser`, `DbSession`, `ClientIp` |
| **`app/services/menus.py`** | **`price_lookup(db, restaurant_id)` → `{name: Decimal}`, the authoritative price source. Excludes unavailable items, so a missing name means "cannot be ordered right now"** |
| **`app/services/bookability.py`** | **`unbookable_reason(restaurant, hours, moment, booking_type)` → reason string or `None`. Already handles timezone and overnight windows** |
| `app/services/hours.py` | `list_hours(db, restaurant_id)` |
| `app/models.py` | also `BOOKING_TYPES`, `READY_BEFORE_ARRIVAL_MINUTES`, `Booking.ready_by` |
| `app/services/restaurants.py` | `get_detail()`; the geography/`ST_DWithin` pattern |
| `app/services/rate_limit.py` | `enforce(key, limit, window)`; add a `(limit, window)` constant per §9 of `10_SECURITY.md` |
| `tests/conftest.py` | `client`, `seeded`, `db_exec`, `db_scalar`, `db_count` fixtures; Overpass blocked by default |

`app/services/menu.py` **no longer exists** — it moved to `scripts/seed_menus.py` and is seed
data only. Do not import it from the request path; `price_lookup` above is the replacement.

### Build

1. `app/services/bookings.py` — creation, listing, cancellation, and the state machine.
2. `app/routers/bookings.py` — `POST /api/bookings/create`, `GET /api/bookings`,
   `GET /api/bookings/{id}`, `PUT /api/bookings/{id}/cancel`
   ([05_API_SPEC.md](./05_API_SPEC.md) §7).
3. Wire the router into `app/main.py`.

### The behaviours that must be exactly right

- **The server computes `total_price`. Always.** Resolve every line item's name against
  `menus.price_lookup()`, reject any name not in it with a 400, and sum the result. A
  client-sent price is refused by `extra="forbid"` — there is no field for it — and the old
  contract that trusted one let two parathas be booked for ₹0.02.
- **Resolved unit prices are frozen onto `bookings.items` at creation.** A later menu price
  change must not retroactively alter a placed order. Store `menu_item_id` on each line as a
  plain integer, **not** an FK: a soft-deleted dish must not break a historical order.
- **A dish marked unavailable cannot be booked.** `price_lookup` already excludes them, so an
  unavailable name lands in the same 400 path as an unknown one — but the message should say
  which, and the code should be `ITEM_UNAVAILABLE` rather than a generic validation error.
  This is the mid-checkout race from `16_FUNCTIONAL_PRODUCT_DATA.md` §3.6: **reject the whole
  booking** rather than silently dropping the line and recomputing the total. Changing what
  someone agreed to pay is a worse surprise than an error.
- **Check `bookability.unbookable_reason()` before anything else.** Approval, the owner's
  accepting-orders toggle, and opening hours at the *requested arrival time* — not at now.
  A restaurant open when you browse and shut when you arrive cannot take the order.
- **Minimum lead time is the restaurant's `avg_prep_time_minutes`, not a flat 30.**
  Enforced server-side; `arrival_time` earlier than `now + prep` is `400 ARRIVAL_TOO_SOON`.
- **`booking_type` is required and must be supported by the restaurant.** It drives
  `ready_by` (dine-in resolves to arrival itself — food plated early cools while a family
  parks), so it cannot be defaulted silently.
- **Every invalid transition is a 400**, driven by `ALLOWED_TRANSITIONS` — including
  reversals and any move out of a terminal state.
- **Ownership is checked on every read and write.** A traveller may only see and cancel
  their own bookings; another user's id is a 404, not a 403, so booking ids are not
  enumerable.

### Done when

`tests/test_bookings.py` is green including **every** invalid transition, the price-tampering
attempt, the unavailable-item rejection, the closed-at-arrival-time rejection, and the
lead-time boundary. Plus `ruff check`, `black --check`, `pytest tests/ -q`, and a real `curl`
creating a booking against the running container.

Note that seeded hours are 06:00–23:00 IST, so a `curl` with an arrival time outside that
window is *correctly* rejected — check the reason before assuming it is a bug.

### Running the stack

```bash
docker compose up -d postgres redis          # both healthy in ~10s
docker compose up -d backend
docker compose exec backend python scripts/migrate.py
docker compose exec backend python scripts/seed.py   # idempotent, safe to re-run
docker compose exec backend pytest tests/ -q
docker compose exec backend ruff check app/ scripts/ tests/
curl -s localhost:8000/api/health
curl -s localhost:8000/api/routes
```

Local Python is 3.14, which has no wheels for the pinned `pydantic-core` — **run everything
in the container**, not in a host venv. Dev dependencies are not in the image; install them
with `docker compose exec backend pip install -q -r requirements-dev.txt` after a rebuild.

---

## 5. Decisions log

Decisions taken during the build that are not obvious from the code. Append, never edit.

| Date | Decision | Reason |
|------|----------|--------|
| 2026-07-29 | Sequential stages replace parallel agent streams | Parallel work is not resumable after an interruption; sequential stages are |
| 2026-07-29 | Doc corrections precede any code | The spec is the build input; a defect in it becomes a defect in code |
| 2026-07-29 | Commits are not created by agents | `git config user.name` / `user.email` are unset in this repo; the owner commits |
| 2026-07-30 | Canonical demo coordinate is `29.02, 77.02` (NH-44 near Murthal) | The old `30.9, 77.7` was near Shimla, ~210 km from the seeded restaurants, so every documented search example returned zero rows |
| 2026-07-30 | Corridor SQL defined once, in `04_DATABASE_DESIGN.md` §5.2 | Two copies had already drifted; the `02` copy was also non-indexable and mixed geography with the geometry function `ST_ClosestPoint` |
| 2026-07-30 | OSRM is local-only; production routes use pre-seeded polylines | The architecture diagram had the Render service calling the local dev container. Generating polylines offline at seed time avoids a production dependency on OSRM entirely |
| 2026-07-30 | ADRs 0001–0010 keep their original text; ADR-0011 supersedes what no longer holds | An ADR log edited retroactively cannot be trusted. The sprint context was historically real; only its consequences changed |
| 2026-07-30 | Riverpod from the start, not `provider` then migrate | Writing the Flutter state layer twice costs more than writing it once. The migration was only ever sprint-setup savings |
| 2026-07-30 | Tests are part of each stage's definition of done | A stage cannot be claimed working without them, and resumability depends on the next person being able to trust what came before |
| 2026-07-30 | `booking_time` renamed `arrival_time` everywhere | Every formula already treated it as the traveller's arrival; the old name read as "when the booking was created". Free now, breaking once clients exist |
| 2026-07-30 | Booking requests carry item name + qty only; server resolves prices from its own menu | The old contract let a client set unit prices, so two parathas could be booked for ₹0.02. `04` §8 and `10` §8 both already *claimed* server-side pricing |
| 2026-07-30 | Resolved unit prices frozen onto `bookings.items` at creation | A later menu price change must not retroactively alter a placed order |
| 2026-07-30 | Minimum lead time is `avg_prep_time_minutes`, not a flat 30 min, enforced server-side | A flat floor is wrong for a restaurant with a 45-minute prep time, and client-only enforcement produced cutoffs already in the past |
| 2026-07-30 | Overdue `pending` bookings stay `pending` and are flagged, not auto-rejected | Auto-rejecting a real order because a restaurant was slow to tap a button is worse than surfacing it to a human |
| 2026-07-30 | `hygiene_rating` renamed `composite_rating`; `rating_count` added | The column held the 3-dimension composite while `05` §9.2 separately returned a hygiene-only `average_hygiene`. `rating_count` also removes a full-table scan |
| 2026-07-30 | 2σ outlier exclusion dropped for a plain mean | σ is degenerate at n ≤ 2 and discards honest ratings at small n. Real outlier handling belongs with Phase 2 moderation |
| 2026-07-30 | OSM POIs upserted into `restaurants` on `osm_id` at search time | `id: null` results could not satisfy the `NOT NULL` FK on `bookings.restaurant_id`, so Overpass supplementation disabled booking exactly where seeded data was thinnest |
| 2026-07-30 | Search cache TTL cut from 7 days to 6 hours; `route_id` dropped from the key | A self-registered restaurant was invisible for a week; and keying on a param the query never reads fragmented the cache |
| 2026-07-30 | Single latency target: P95 < 800 ms cache hit | Three conflicting figures existed (3 s, 800 ms, 100 ms). 100 ms is now stated as a typical expectation, not a requirement |
| 2026-07-30 | 2-year retention labelled a policy target the free tier does not meet | Render free tier keeps 7 days of backups; claiming 2 years unqualified was untrue |
| 2026-07-30 | Login never auto-registers; unknown phone → `404 USER_NOT_FOUND` | Auto-register plus a constant OTP let anyone mint a token for any phone number, including a real person's |
| 2026-07-30 | OTP stub, dashboard token, and API docs all gate on `ENVIRONMENT`, which has no default | A value defaulting to `development` means one forgotten env var silently enables a constant password in production. Startup fails if unset |
| 2026-07-30 | Dashboard uses `X-Restaurant-Token` **plus** a per-request ownership check | The token alone cannot distinguish restaurants, so without the ownership check one restaurant could still drive another's orders |
| 2026-07-30 | `POST /restaurants/register` requires a JWT and lands `is_active = false` | It was a public geospatial write — a search-poisoning vector whose rows would then sit in the cache |
| 2026-07-30 | `POST /gps/events` not implemented; table kept | An unauthenticated append-only write with no reader in MVP. The table costs nothing; the endpoint arrives with the Phase 3 ETA model |
| 2026-07-30 | `flutter_secure_storage` from the start, not `SharedPreferences` | Same reasoning as Riverpod: retrofitting means every token issued before the change was already exposed in plaintext |
| 2026-07-30 | Redis fails open per operation, not via a boot-time flag | The flag only handled "already down at boot"; Redis dying mid-run would have raised on every subsequent request |
| 2026-07-30 | Models live in one `app/models.py`, not an `app/models/` package | Six tables with heavy cross-references. One file reads better than six two-class files; split it when it stops fitting on a screen, not preemptively |
| 2026-07-30 | Migrations applied by `scripts/migrate.py`, not postgres `docker-entrypoint-initdb.d` | The init directory runs only on an empty volume, so it silently skips on every subsequent boot. One code path for local and production means a migration that works on a laptop is the one that runs on Render |
| 2026-07-30 | Health returns 503 only for a database failure | A missing or broken cache is degraded, not down. Returning 503 for it would make Render kill a service that still works |
| 2026-07-30 | Rate limiting fails **open** when Redis is unavailable | Failing closed turns a cache outage into an auth outage. The limit is documented as best-effort for exactly this reason |
| 2026-07-31 | `is_active` split into `approval_status` + `is_accepting_orders` + `restaurant_hours` | One flag meant "ops approved this" and "include in search", and the design wanted it to also mean "open now". An owner tapping Closed would have flipped the flag meaning unapproved and needed an operator to undo it |
| 2026-07-31 | `is_active` kept and still maintained, deprecated by comment | Dropping a column the previous release still reads breaks a rolling deploy. It is retired in a later migration once nothing references it |
| 2026-07-31 | Approval backfill guarded against re-running | An unguarded `UPDATE` would re-approve a row an operator had since rejected, every time the migration ran. Verified by rejecting a row and re-running |
| 2026-07-31 | JWTs carry a `typ` actor claim; `expected_actor` is a required argument | Two actors sign against one secret, so without `typ` a traveller token and a staff token decode identically. `users.id` and `restaurant_users.id` are independent sequences, so low IDs collide routinely — a traveller presenting their own valid token as staff was the common case, not an exotic one |
| 2026-07-31 | Authorization reads `restaurant_id` from the staff row, never the `rid` claim | A claim is client-visible and fixed at issue time; the row is current. Staff moved between outlets or deactivated lose access immediately rather than at token expiry |
| 2026-07-31 | Restaurant login succeeds while approval is pending or rejected | Approval gates taking orders, not signing in. An owner needs to log in precisely to see why they are not live; locking them out makes the onboarding checklist unreachable |
| 2026-07-31 | No restaurant self-registration endpoint | Anyone able to create their own staff row could attach themselves to an existing restaurant and read its order queue |
| 2026-07-31 | `RESTAURANT_DASHBOARD_TOKEN` deleted rather than left unused | A live credential for a scheme nothing implements reads as supported. A test asserts the field is gone, because that is the kind of thing that gets quietly reintroduced |
| 2026-07-31 | Hours are replaced wholesale, not merged per day | Omitting a day is how it is marked closed, so a merge would leave unmentioned days as they were — which is how a restaurant ends up open on a day it thought it had closed |
| 2026-07-31 | Absent hours mean closed; `closes_at < opens_at` is a valid overnight window | A newly approved restaurant with no hours must not accept 3am orders. Highway dhabas routinely run past midnight, so rejecting the wrap would close them during peak hours |
| 2026-07-31 | Availability is its own endpoint, separate from menu update | Most-used control in the product, tapped mid-service one-handed. Routing it through the general update would let an unrelated validation error block a stock change |
| 2026-07-31 | `is_available` separate from `deleted_at` | "Out of paneer today" and "we stopped selling this" differ in reversibility; merging them makes an owner re-create the dish tomorrow |
| 2026-07-31 | A restaurant with no menu is listed but not bookable — DEFAULT_MENU fallback removed | The fallback was fine while every menu was fictional. With real menus it would quote a price no restaurant agreed to, for an OSM row nobody has spoken to, and the failure would land at the roadside instead of in the API |
| 2026-07-31 | Seed fixtures moved from `app/services/menu.py` to `scripts/seed_menus.py` | Leaving it beside the new `app/services/menus.py` put two modules one letter apart with opposite roles, and seed data does not belong in the service layer |
| 2026-07-30 | All development runs in the container, not a host venv | Local Python is 3.14 and `pydantic-core` has no wheels for it; building from source needs a Rust toolchain. The container pins 3.11 |
| 2026-07-30 | Login verifies the OTP **before** looking the phone up | Checking existence first makes the 404/401 split a registered-number oracle for a caller who has no valid OTP at all |
| 2026-07-30 | A valid token for a deleted user is `401 UNAUTHORIZED`, identical to a bad signature | Distinguishing the two tells a token prober which user ids exist. Expiry stays distinguishable because a client needs to know to re-login |
| 2026-07-30 | Phone separators stripped before pattern validation, not rejected | `+91 98765-43210` is what people type. Stripping in a `mode="before"` validator means the E.164 pattern still governs storage, and one number cannot become two rows |
| 2026-07-30 | Tests use a `<dbname>_test` database derived from the ambient `DATABASE_URL`, created and migrated by `conftest.py` | The host differs between a container run and a host run; only the name should change. Deriving it also means the suite can never truncate the development database |
| 2026-07-30 | `app/db.py` uses `NullPool` when `ENVIRONMENT == "test"` | pytest gives each test its own event loop and an asyncpg connection is bound to the loop that opened it, so a pooled connection fails with "Event loop is closed" on reuse. Pooling is unchanged everywhere else |
| 2026-07-30 | `email-validator` added to `requirements.txt` | `pydantic.EmailStr` imports it at model-definition time and pydantic does not vendor it; without the pin the app fails at import, not at first use |
| 2026-07-31 | No `GET /routes/{id}`; only the list endpoint exists | [05_API_SPEC.md](./05_API_SPEC.md) §5 defines one endpoint. The route id is booking context chosen from a dropdown the list already populates, so a detail fetch has no caller. An earlier draft of this section named a detail endpoint the spec never had |
| 2026-07-31 | Seed matches on natural key with SELECT-then-write, not `ON CONFLICT` | Neither `routes.name` nor `restaurants.name` is UNIQUE, and neither should be: two real dhabas can share a name, and OSM rows deduplicate on `osm_id`. Adding a unique index to shorten a seed script would constrain production data for a dev convenience |
| 2026-07-31 | Re-seeding never touches `composite_rating` / `rating_count` | They are derived from the `ratings` table. Resetting them on a re-seed would silently discard real ratings |
| 2026-07-31 | Restaurant seed lookup is scoped to `osm_id IS NULL` | Otherwise a re-seed would overwrite a POI promoted from OpenStreetMap that happens to share a name with a seeded row |
| 2026-07-31 | Route `geometry` seeded as NULL, not a fabricated LINESTRING | Polylines come from OSRM offline at seed time and no OSRM service exists in this compose file yet. Wrong data behind the Stage 16 corridor query is worse than no data; the column is nullable for this reason and the point-radius search does not read it |
| 2026-07-31 | Seed constants live in `scripts/seed_data.py`, imported by both the script and the tests | A test that re-types a coordinate tests its own typo. `ST_X`/`ST_Y` swapped still returns 200 with plausible floats — it just puts Delhi in the Arctic |
| 2026-07-31 | The OSM upsert conflict target carries `WHERE osm_id IS NOT NULL` | `idx_restaurants_osm_id` is a *partial* unique index, and Postgres will not infer a partial index as an arbiter without its predicate. The SQL documented in `04` §3.2.1 omitted it and so could never have run; the doc is now corrected |
| 2026-07-31 | Promoted OSM rows are re-read through the same local query, not merged in Python | One SQL ordering is easier to trust than a hand-rolled merge, and dedupe falls to the `osm_id` unique index rather than application logic |
| 2026-07-31 | Search cache key rounds coordinates to 4 decimals (~11 m) | A GPS fix jitters in the seventh decimal place, so unrounded keys would give nearly every request its own entry and the cache would never be hit |
| 2026-07-31 | Menus live in `app/services/menu.py` with `Decimal` prices, never `float` | It is the authoritative price source Stage 11 reads, so it must be importable rather than inline in a handler. `0.1 + 0.2 != 0.3` in binary floating point and these values are summed into a `NUMERIC(10,2)` column that money is owed against |
| 2026-07-31 | Unknown restaurants fall back to `DEFAULT_MENU` rather than an empty menu | An empty menu makes a restaurant unbookable, and OSM-promoted POIs exist precisely to cover corridors where seeded data is thin |
| 2026-07-31 | Inactive restaurants 404 on detail, not just hidden from search | Otherwise a pending self-registration is readable by guessing the id the register response just returned |
| 2026-07-31 | Restaurant registration is rate limited per user, not per IP | There is an authenticated identity on this endpoint, which is a more meaningful key than a shared or rotating address |
| 2026-07-31 | The real Overpass API is blocked from every test by an autouse fixture | Its usage policy prohibits application traffic, and a suite depending on a volunteer service's uptime cannot be trusted. Tests that need POIs substitute their own |

---

## 6. Deferred / discovered

Things noticed but deliberately not acted on. Keeps them from being silently lost.

- No `LICENSE` file. Repo has no GitHub description or topics either — owner decision.
- `bus_gps_events` is created but nothing reads or writes it in MVP (ADR-0010,
  [05_API_SPEC.md](./05_API_SPEC.md) §11.2). Intentional; the table is free, the endpoint
  was not.
- Restaurant activation after self-registration has no UI — an operator flips `is_active`
  in the database. Approval screen is Phase 1 ([13_ROADMAP.md](./13_ROADMAP.md) §3).
- Menus are hardcoded per restaurant. They are server-authoritative, so this is not a
  trust gap, but it does mean adding a dish requires a code change until `menu_items`
  CRUD lands.
- Phase C (Stages 15–19) is intentionally not broken down. Scope it when Phase B is done
  and the shape of the client is clearer, not before.
- **Discovered in Stage 8:** the Stage 7 suite never reached a live database. Its
  `DATABASE_URL` named a `_test` database that did not exist, and the health test tolerates
  `database: "unreachable"` by design, so it passed on the degraded branch. `conftest.py`
  now creates and migrates that database, and the health check has been exercised against a
  reachable one. Nothing in Stage 7 was wrong; it was less covered than it appeared.
- Rate limits are unenforced whenever Redis is absent, including in the test suite, which
  runs with `REDIS_URL` unset. `tests/test_auth.py` asserts both branches — fail-open
  without a counter, and 429 with `Retry-After` when one is available.
- **Route polylines are not seeded**, so Stage 16's corridor query has nothing to run
  against yet. It needs an OSRM service in `docker-compose.yml` (absent today) plus a
  one-off generation step whose output is committed or stored, since production never calls
  OSRM. Stage 16 starts with that, not with the SQL.
- The seeded restaurant names are real Murthal-area dhabas but the **phone numbers and
  precise coordinates are invented** — plausible placeholders on the NH-44 corridor, not
  surveyed positions. Fine for a demo; they must not be presented as a real directory.
- **The Overpass throttle is per process, not per deployment.** A module-level lock gives
  1 req/sec per worker, so N uvicorn workers permit N req/sec. Adequate for a single-worker
  free-tier service and wrong the moment it scales; a shared limiter (Redis token bucket) is
  needed before then. Self-hosting (Stage 19) removes the constraint entirely.
- **OSM POIs are promoted on the search path and never cleaned up.** A POI that disappears
  from OpenStreetMap keeps its `restaurants` row, and nothing revisits it. Harmless at demo
  scale, but there is no reconciliation job and no `last_seen_at` column to build one from.
- **Promotion writes on a GET.** Documented and intentional (§3.2.1) and idempotent, but it
  means search is not read-only: a search against a read replica would fail. Worth
  remembering before adding one.
- Menu prices are hardcoded, so **a restaurant cannot change its own prices** without a code
  deploy. This is the cost of keeping the price boundary server-side until `menu_items` CRUD
  lands in Phase 1.

---

## 7. Related documents

- [README.md](./README.md) — doc index and reading order
- [00_PROJECT_CHARTER.md](./00_PROJECT_CHARTER.md) — scope and non-goals
- [13_ROADMAP.md](./13_ROADMAP.md) — phase planning beyond this build
- [../CLAUDE.md](../CLAUDE.md) — agent working rules
