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

Use **Redis 7** for search and geocode caching. Application detects Redis unavailability at startup and **continues without cache**.

### Rationale

- 7-day search cache dramatically reduces Overpass load and latency
- Graceful fallback prevents Redis from being a single point of failure
- Same Redis instance usable for rate limiting and refresh tokens in Phase 2

### Consequences

- `cache.py` exposes `is_available` flag checked before every cache operation
- Cache miss path must always produce correct results (cache is optimization only)

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

---

## 3. Related Documents

- [02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md)
- [03_SYSTEM_ARCHITECTURE.md](./03_SYSTEM_ARCHITECTURE.md)
- [10_SECURITY.md](./10_SECURITY.md)
- [13_ROADMAP.md](./13_ROADMAP.md)
