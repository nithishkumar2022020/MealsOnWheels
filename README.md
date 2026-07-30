# MealsOnWheels

**Highway food pre-booking platform.** Travellers pre-order from restaurants along their
route so the food is ready the moment they pull off the road.

> This is not a food delivery app. There is no courier and no home address. The booking
> anchors on **when the traveller arrives at a highway stop**, not on distance from home.

Two actors: **travellers** (bus passengers, drivers, highway commuters) and
**restaurants** (highway dhabas, food courts, QSR outlets) that prepare against a stated
arrival time instead of on-demand dispatch. Built for Indian highway corridors —
NH-44, Delhi→Chandigarh, Mumbai→Pune.

---

## Status

**Pre-release. Backend implementation in progress.**

The full technical and product specification is written and reviewed. Code is being
built against it stage by stage. See **[docs/14_BUILD_PLAN.md](./docs/14_BUILD_PLAN.md)**
for exactly what is done, what is next, and how to pick up mid-stream.

---

## Stack

| Layer | Technology |
|-------|------------|
| Mobile / web client | Flutter (Dart) |
| Backend API | FastAPI (Python 3.11+), async SQLAlchemy |
| Database | PostgreSQL 16 + PostGIS 3.4 |
| Cache | Redis 7 (optional — app runs without it) |
| Maps | MapLibre GL + OpenStreetMap tiles |
| Geocoding / POI / routing | Nominatim, Overpass, OSRM |
| Auth | JWT (HS256) + phone OTP |
| Containers / CI | Docker Compose, GitHub Actions |
| Hosting | Render |

Open-source first, zero-cost where practical. No Google Maps billing, no paid tiers
required to run the stack locally.

---

## Quick start

```bash
git clone https://github.com/nithishkumar2022020/MealsOnWheels.git
cd MealsOnWheels

docker compose up -d postgres redis

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python scripts/migrate.py      # create schema
python scripts/seed.py         # 5 routes, 10 restaurants, 1 test user

uvicorn app.main:app --reload --port 8000
```

Then `curl http://localhost:8000/api/health`.

Full setup notes, conventions, and troubleshooting:
**[docs/08_DEVELOPMENT_GUIDELINES.md](./docs/08_DEVELOPMENT_GUIDELINES.md)**.

---

## Documentation

Start at **[docs/README.md](./docs/README.md)** — it carries the reading order, a
cross-reference index, and the document map.

| | |
|---|---|
| Why this exists | [00_PROJECT_CHARTER.md](./docs/00_PROJECT_CHARTER.md) |
| What it does | [01_PRODUCT_SPEC.md](./docs/01_PRODUCT_SPEC.md) |
| How it is built | [02_TECHNICAL_SPEC.md](./docs/02_TECHNICAL_SPEC.md) |
| Schema | [04_DATABASE_DESIGN.md](./docs/04_DATABASE_DESIGN.md) |
| REST contract | [05_API_SPEC.md](./docs/05_API_SPEC.md) |
| Security posture | [10_SECURITY.md](./docs/10_SECURITY.md) |
| What is built so far | [14_BUILD_PLAN.md](./docs/14_BUILD_PLAN.md) |

---

## Security note

This project is pre-launch and **not safe to expose publicly yet**. The OTP is a
development stub and the restaurant dashboard uses a shared token rather than per-account
auth. Both are gated to non-production environments and tracked in
[10_SECURITY.md](./docs/10_SECURITY.md) §10. Do not deploy to a public URL until that
checklist is clear.

---

## License

Not yet licensed. All rights reserved by the repository owner.
