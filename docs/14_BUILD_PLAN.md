# Build Plan & Handoff Log

**Document version:** 1.0
**Last updated:** 2026-07-30 (Stage 8 complete)
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
| Shared restaurant dashboard token | Per-restaurant accounts need an onboarding flow | `ENVIRONMENT != production` |
| Hardcoded menus | Menu CRUD is a Phase 1 feature | Server owns the menu; client cannot inject prices |
| Point-radius search | Route polylines not seeded yet | Corridor query is Stage 16 |
| JSONB booking items | Normalising needs the menu table first | — |
| Polling, not WebSocket | Adequate at current scale | — |

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
| 9 | Routes module + seed script | TODO | Seeded DB; `GET /api/routes` returns 5 routes |
| 10 | Restaurant search, detail, register | TODO | `tests/test_restaurants.py` green including Overpass-down fallback |
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
| 18 | Real SMS OTP + per-restaurant auth (unblocks public launch) | TODO |
| 19 | Self-hosted Nominatim / Overpass (usage policy compliance) | TODO |

---

## 4. Next Action

**Stage 9 — routes module and seed script.**

Phase A, Stage 7 (skeleton) and Stage 8 (auth) are complete and verified. Do not re-open
the Phase A decisions; they are recorded in §5 with reasons.

### What already exists (build on it, do not rewrite)

| File | What it gives you |
|------|-------------------|
| `app/config.py` | `get_settings()`; `settings.otp_stub_allowed`, `.is_production`, `.JWT_SECRET`, `.JWT_EXPIRE_HOURS` |
| `app/db.py` | `Base`, `SessionLocal`, `get_db`. `NullPool` under `ENVIRONMENT=test` — see §5 |
| `app/cache.py` | `cache.get_json()` / `set_json()` / `incr_with_expiry()`. All fail open |
| `app/errors.py` | `unauthorized()`, `not_found()`, `conflict()`, `service_unavailable()` — all carry a `code` |
| `app/models.py` | `User`, `Restaurant`, `Route`, `Booking`, `Rating`; `ALLOWED_TRANSITIONS` |
| `app/schemas.py` | `RequestModel` (`extra="forbid"`) and `ResponseModel` base classes; `PHONE_PATTERN`, `normalise_phone()` |
| `app/deps.py` | `CurrentUser`, `DbSession`, `ClientIp` annotated dependencies |
| `app/services/rate_limit.py` | `enforce(key, limit, window)`; add a new `(limit, window)` constant per §9 of `10_SECURITY.md` |
| `app/core/security.py` | `create_access_token()`, `decode_token()` |
| `tests/conftest.py` | Creates `<db>_test`, applies migrations, truncates between tests. `client` fixture |

**Subclass `RequestModel` / `ResponseModel` for new schemas.** Declaring a bare `BaseModel`
loses `extra="forbid"`, which is the control behind the Stage 11 price promise.

### Build

1. `scripts/seed.py` — 5 NH-44 routes and the seeded restaurants near the canonical demo
   coordinate `29.02, 77.02` ([04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md) §7).
   Idempotent: re-running must not duplicate rows. Route polylines are generated offline
   and stored, never fetched from OSRM at request time (ADR: OSRM is local-only).
2. `app/services/routes.py` + `app/routers/routes.py` — `GET /api/routes`,
   `GET /api/routes/{id}` ([05_API_SPEC.md](./05_API_SPEC.md) §5).
3. Wire the router into `app/main.py`.

### Done when

`GET /api/routes` returns the 5 seeded routes against a seeded database, and
`tests/test_routes.py` covers the list, a single fetch, and a `404 NOT_FOUND` for an unknown
id. Seeding twice leaves the row counts unchanged.

Plus `ruff check`, `black --check`, `pytest tests/ -q` all green, and a real `curl` against
the running container.

### Running the stack

```bash
docker compose up -d postgres redis          # both healthy in ~10s
docker compose up -d backend
docker compose exec backend pytest tests/ -q
docker compose exec backend ruff check app/ scripts/ tests/
curl -s localhost:8000/api/health
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
| 2026-07-30 | All development runs in the container, not a host venv | Local Python is 3.14 and `pydantic-core` has no wheels for it; building from source needs a Rust toolchain. The container pins 3.11 |
| 2026-07-30 | Login verifies the OTP **before** looking the phone up | Checking existence first makes the 404/401 split a registered-number oracle for a caller who has no valid OTP at all |
| 2026-07-30 | A valid token for a deleted user is `401 UNAUTHORIZED`, identical to a bad signature | Distinguishing the two tells a token prober which user ids exist. Expiry stays distinguishable because a client needs to know to re-login |
| 2026-07-30 | Phone separators stripped before pattern validation, not rejected | `+91 98765-43210` is what people type. Stripping in a `mode="before"` validator means the E.164 pattern still governs storage, and one number cannot become two rows |
| 2026-07-30 | Tests use a `<dbname>_test` database derived from the ambient `DATABASE_URL`, created and migrated by `conftest.py` | The host differs between a container run and a host run; only the name should change. Deriving it also means the suite can never truncate the development database |
| 2026-07-30 | `app/db.py` uses `NullPool` when `ENVIRONMENT == "test"` | pytest gives each test its own event loop and an asyncpg connection is bound to the loop that opened it, so a pooled connection fails with "Event loop is closed" on reuse. Pooling is unchanged everywhere else |
| 2026-07-30 | `email-validator` added to `requirements.txt` | `pydantic.EmailStr` imports it at model-definition time and pydantic does not vendor it; without the pin the app fails at import, not at first use |

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

---

## 7. Related documents

- [README.md](./README.md) — doc index and reading order
- [00_PROJECT_CHARTER.md](./00_PROJECT_CHARTER.md) — scope and non-goals
- [13_ROADMAP.md](./13_ROADMAP.md) — phase planning beyond this build
- [../CLAUDE.md](../CLAUDE.md) — agent working rules
