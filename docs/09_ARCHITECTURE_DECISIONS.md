# Architecture Decision Records — Highway Food Pre-Booking Platform

**Document version:** 1.0  
**Last updated:** 2026-07-25

---

## 1. ADR Process

Each significant technical decision is recorded here with:

- **Context** — What problem or constraint drove the decision
- **Decision** — What we chose
- **Rationale** — Why this option over alternatives
- **Consequences** — Trade-offs and follow-up actions
- **Alternatives considered** — Options rejected and why

Status values: `Accepted` | `Superseded` | `Deprecated`

---

## ADR-0001: Backend Framework — FastAPI over Node.js Express

**Status:** Accepted  
**Date:** 2026-07-25

### Context

The 24-hour sprint execution plan specified Node.js + Express. The original product brief and long-term roadmap include ML-based ETA prediction, demand forecasting, and geospatial analytics.

### Decision

Use **FastAPI (Python 3.11+)** with async SQLAlchemy and Uvicorn.

### Rationale

- Native async I/O matches geo API and DB-heavy workloads
- Python ecosystem is the standard for future ML features — no second language or service rewrite
- Pydantic provides runtime validation and auto-generated OpenAPI
- Strong typing with mypy/ruff improves maintainability as team grows

### Consequences

- Sprint agents must translate Node deliverables to Python equivalents
- Flutter client unchanged (REST JSON contract identical)
- Team needs Python proficiency (already assumed for ML path)

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Node.js Express | Faster sprint start but forces Python rewrite for ML Phase 3 |
| Django | Heavier ORM/middleware; slower iteration for API-only service |
| Go | Excellent performance but weak ML ecosystem |

---

## ADR-0002: Modular Monolith over Microservices

**Status:** Accepted  
**Date:** 2026-07-25

### Context

MVP must ship in 24 hours with a small team. System must scale to 100K+ DAU eventually.

### Decision

Single **modular monolith** FastAPI deployable with internal module boundaries (auth, search, bookings, dashboard, ratings).

### Rationale

- One deploy artifact, one database, minimal DevOps overhead
- Module seams (`services/`, `routers/`) allow future extraction without upfront cost
- Microservices add network latency, distributed tracing, and deployment complexity inappropriate for MVP

### Consequences

- All modules share PostgreSQL connection pool
- Future extraction of notifications or ETA service requires defined interfaces (already stubbed)

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Microservices from day 1 | 3× deployment complexity; no team to operate |
| Serverless (Lambda) | Cold starts hurt search latency; PostGIS connection pooling difficult |

---

## ADR-0003: PostgreSQL + PostGIS as Single Datastore

**Status:** Accepted  
**Date:** 2026-07-25

### Context

Core feature is geospatial restaurant search along travel routes. Need relational integrity for bookings and ratings.

### Decision

**PostgreSQL 16 with PostGIS 3.4** for all persistent data including spatial queries.

### Rationale

- Combines ACID transactions and geospatial indexing (GiST) in one database
- No separate geo database (MongoDB 2dsphere, Elasticsearch geo) to operate
- SQL is well-understood; PostGIS `ST_DWithin` is production-proven

### Consequences

- Must enable PostGIS extension in all environments
- Route polylines stored as `GEOMETRY(LINESTRING, 4326)`
- MVP sprint uses point-radius search first; corridor query in Phase 1.5

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| PostgreSQL without PostGIS | Would require app-level distance calc; no spatial index |
| MongoDB | Weaker transactional guarantees for booking state machine |
| Dedicated geo service (PostGIS + API) | Unnecessary service boundary for MVP scale |

---

## ADR-0004: Redis for Cache with Graceful Degradation

**Status:** Accepted  
**Date:** 2026-07-25

### Context

Restaurant search hits Overpass/Nominatim on cache miss. Redis may be unavailable on Render free tier cold starts or local dev without Docker.

### Decision

Use **Redis 7** for search and geocode caching. Every cache operation **fails open
individually** — any Redis error is logged and treated as a cache miss, and the request
continues against PostgreSQL and the external APIs.

### Rationale

- A 6-hour search cache substantially reduces Overpass load and latency
- Per-operation fallback prevents Redis from being a single point of failure at any moment,
  not just at boot
- Same Redis instance usable for rate limiting and refresh tokens in Phase 2

### Consequences

- `cache.py` wraps every get/set in exception handling; callers never see a Redis error
- Cache miss path must always produce correct results (cache is optimisation only)
- Rate limiting degrades to best-effort per-process when Redis is down
  ([10_SECURITY.md](./10_SECURITY.md) §9)

**Amended 2026-07-30:** originally this probed Redis once at startup and set a
`REDIS_AVAILABLE` flag. That covered only "Redis was already down when we booted" and would
have raised on every request if Redis died mid-run — the more likely failure on a free tier.
Replaced with per-operation fail-open.

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| No cache | Overpass rate limits would break search under load |
| DB-only cache (materialized views) | Slower than Redis; wrong tool for TTL-based API response cache |
| Required Redis | Blocks local dev and risks outage if Redis fails |

---

## ADR-0005: Phone + OTP Authentication (Stub in MVP)

**Status:** Accepted  
**Date:** 2026-07-25

### Context

Target users are Indian highway travellers. Need low-friction mobile login. Sprint excludes SMS integration.

### Decision

**Phone number + OTP** authentication. MVP OTP hardcoded to `123456`. JWT issued on success.

### Rationale

- Phone is universal identifier for target market (no email required)
- OTP stub unblocks all streams without SMS provider setup
- JWT is stateless and works across Flutter and web dashboard

### Consequences

- **Must replace OTP stub before public launch** ([10_SECURITY.md](./10_SECURITY.md))
- Auto-register on first login for sprint convenience
- Phase 2: real SMS via MSG91/Twilio; refresh tokens in Redis

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| OAuth (Google) | Out of sprint scope; not all users have Google accounts |
| Email + password | Higher friction; password reset complexity |
| Magic link | Requires email infrastructure; less common in India mobile-first |

---

## ADR-0006: MapLibre + OpenStreetMap over Google Maps

**Status:** Accepted  
**Date:** 2026-07-25

### Context

Map is core UX. Google Maps Platform charges per load; budget is zero for MVP.

### Decision

**MapLibre GL** for rendering with **OpenStreetMap** tiles. **Nominatim** for geocoding. **OSRM** for routing geometry.

### Rationale

- Fully open-source stack; no API key billing
- MapLibre is actively maintained fork of Mapbox GL OSS
- OSRM provides routing that MapLibre alone cannot

### Consequences

- Must display OSM attribution on all map views
- Self-host Nominatim/OSRM or throttle public instance usage (1 req/sec)
- OSM POI coverage gaps mitigated by manual restaurant seeding

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Google Maps Flutter plugin | Cost at scale; violates zero-cost principle |
| Mapbox (hosted) | Free tier limits; proprietary |
| Leaflet only | Less performant for mobile; MapLibre better for Flutter GL |

---

## ADR-0007: Pay-on-Arrival (No Payment Gateway in MVP)

**Status:** Accepted  
**Date:** 2026-07-25

### Context

Payment integration (Razorpay/UPI) adds 8+ hours and regulatory considerations. Restaurants on highways already accept cash/UPI directly.

### Decision

**Pay-on-arrival** only in MVP. `payment_status` column always `pending`. Payment provider interface stubbed in `services/payments.py`.

### Rationale

- Unblocks booking flow without PCI/compliance scope
- Matches operational reality of highway dhabas
- Payment abstraction allows Razorpay/Stripe in Phase 2 without schema migration

### Consequences

- No payment confirmation in order lifecycle
- Platform cannot take commission automatically until Phase 2
- Booking is commitment-based, not payment-secured

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Razorpay in MVP | Sprint time; webhook complexity |
| Stripe | Limited UPI support in India context |

---

## ADR-0008: Booking Items as JSONB (Not Normalized Line Items)

**Status:** Accepted  
**Date:** 2026-07-25

### Context

MVP menus are hardcoded/dummy. Full menu CRUD is Phase 2. Need fast booking creation in sprint.

### Decision

Store order line items as **JSONB array** on `bookings.items` column.

### Rationale

- Eliminates `order_items` join table for MVP
- Flexible schema for dummy menus without migration on menu changes
- Sufficient for MVP query patterns (always fetch booking with items)

### Consequences

- Cannot SQL-query individual item popularity without JSONB operators
- Phase 2: normalize to `menu_items` + `order_items` when menu CRUD ships
- Migration path: extract JSONB to rows with Alembic script

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Normalized order_items from day 1 | Requires menu table CRUD not in MVP scope |
| Items as comma-separated string | Not queryable; poor data integrity |

---

## ADR-0009: Render for MVP Hosting

**Status:** Accepted  
**Date:** 2026-07-25

### Context

Sprint requires live deployment in final 8 hours. Team uses GitHub. Budget is zero.

### Decision

Deploy backend to **Render** (free tier web service + PostgreSQL + Redis). Flutter web as Render static site or Netlify.

### Rationale

- GitHub integration for auto-deploy on push
- Managed PostgreSQL and Redis on same platform
- Docker support aligns with [12_DEPLOYMENT.md](./12_DEPLOYMENT.md)

### Consequences

- Free tier cold starts (~30 s) acceptable for demo
- GitHub Actions builds image; Render pulls on deploy
- Production hardening (custom domain, SSL) included in Render

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| AWS ECS | Higher setup complexity for 24h sprint |
| Fly.io | Good option but team sprint plan specifies Render |
| Self-hosted VPS | No time for server hardening in sprint |

---

## ADR-0010: AI Features as Extension Points Only

**Status:** Accepted  
**Date:** 2026-07-25

### Context

Roadmap includes ETA prediction and demand forecasting. MVP must not be blocked on ML infrastructure.

### Decision

Reserve `bus_gps_events` table and stub `services/eta.py` / `services/demand.py`. **No ML model in MVP.**

### Rationale

- GPS ingest table costs nothing now; enables future training data collection
- Stub interfaces document expected function signatures
- Prevents scope creep during 24h sprint

### Consequences

- Arrival time is user-declared, not model-predicted
- Dashboard countdown uses stated `booking_time`, not live GPS

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Simple linear ETA model in MVP | Still needs GPS feed not available in sprint |
| Skip GPS table entirely | Would require schema migration later |

---

## ADR-0011: Sequential Resumable Stages Replace the 24-Hour Sprint

**Status:** Accepted
**Date:** 2026-07-30

### Context

ADRs 0001–0010 were written against a **24-hour sprint executed by parallel agent
streams**. Several of their consequences were justified by that clock: skip automated
tests, leave the restaurant dashboard unauthenticated, accept client-supplied prices,
use `provider` instead of `riverpod`.

That constraint no longer exists. There is no deadline. The binding constraint is now
**resumability** — work may be interrupted at any point, and what has been built must
remain coherent and continuable by someone with no memory of the reasoning.

Parallel streams are the wrong shape for this. Five streams interrupted mid-flight leave
five partial modules and no working system. The same work sequenced leaves a working
system at every boundary.

### Decision

Work is sequenced as **numbered stages, each ending in a verified working state**, tracked
in [14_BUILD_PLAN.md](./14_BUILD_PLAN.md). Stream labels A–E are retired. A stage is not
complete until its tests pass.

Shortcuts justified only by the deadline are **fixed rather than carried**:

| Was | Now | Reason |
|-----|-----|--------|
| No automated tests | Tests ship with each stage | A stage cannot be verified working without them, and resumability depends on the next person trusting what came before |
| Client-supplied item prices | Server validates every line against its own menu | Nothing was buying this except sprint speed |
| `provider`, migrate to `riverpod` later | `riverpod` from the start | Writing the state layer twice costs more than doing it once |
| Unauthenticated dashboard, "obscure URL" | Shared token gated to non-production | Obscurity was never a control |

### Consequences

- ADRs 0001–0010 keep their original text. Their *context* remains historically accurate;
  where a *consequence* no longer holds, this ADR supersedes it.
- Specifically superseded: ADR-0005's "auto-register on first login for sprint
  convenience" (now gated to non-production and restricted to known phones) and the
  testing consequences implied throughout.
- ADR-0001's rationale for FastAPI is **unaffected** — it rested on the Python ML path,
  not on the sprint. Same for ADR-0002, 0003, 0004, 0006, 0007, 0008, 0009, 0010.
- Estimated dates in [13_ROADMAP.md](./13_ROADMAP.md) are planning aids, not commitments.

### Alternatives considered

| Option | Rejected because |
|--------|------------------|
| Keep parallel streams, drop the deadline | Parallel in-flight work is not recoverable after an interruption, which is the constraint that now matters most |
| Rewrite ADRs 0001–0010 to remove sprint language | Destroys the record of why decisions were actually made; an ADR log that is edited retroactively cannot be trusted |
| Carry all sprint shortcuts as Phase 1 debt | Several cost more to carry than to fix, and two of them are security gaps |

---

## 2. Decision Index

| ADR | Title | Status |
|-----|-------|--------|
| 0001 | FastAPI over Express | Accepted |
| 0002 | Modular monolith | Accepted |
| 0003 | PostgreSQL + PostGIS | Accepted |
| 0004 | Redis with graceful fallback | Accepted |
| 0005 | Phone + OTP auth (stub) | Accepted |
| 0006 | MapLibre + OSM | Accepted |
| 0007 | Pay-on-arrival | Accepted |
| 0008 | JSONB booking items | Accepted |
| 0009 | Render hosting | Accepted |
| 0010 | AI as extension points | Accepted |
| 0011 | Sequential resumable stages replace 24-hour sprint | Accepted |

---

## 3. Related Documents

- [02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md)
- [03_SYSTEM_ARCHITECTURE.md](./03_SYSTEM_ARCHITECTURE.md)
- [10_SECURITY.md](./10_SECURITY.md)
- [13_ROADMAP.md](./13_ROADMAP.md)
