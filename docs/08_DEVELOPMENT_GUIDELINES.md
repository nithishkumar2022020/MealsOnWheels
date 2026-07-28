# Development Guidelines — Highway Food Pre-Booking Platform

**Document version:** 1.0  
**Last updated:** 2026-07-25  
**Parent:** [02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md)

---

## 1. Engineering Philosophy

- **Open-source first** — Prefer OSS libraries with active communities
- **Zero-cost where practical** — OSM, Nominatim, Render free tier, Cloudflare R2 free tier
- **Simple before clever** — Readable code beats premature abstraction
- **Maintainability over shortcuts** — Except during 24h sprint: ship now, optimize later
- **No refactoring during sprint** — Fix bugs only; structural cleanup post-launch
- **Security by default** — Never commit secrets; validate all inputs server-side

---

## 2. Repository & Branch Strategy

### 2.1 Branch naming

```
main                          # Production-ready
feature/backend-auth          # Stream A
feature/restaurant-search     # Stream B
feature/bookings              # Stream C
feature/flutter-frontend      # Stream D
feature/deploy-notifications  # Stream E
```

### 2.2 Sprint merge cadence

- Merge feature branches to `main` every **3 hours** during 24h sprint
- Resolve conflicts in favor of `main` for shared config files
- Each agent commits to their feature branch every **2 hours**

### 2.3 Commit message format

```
<type>(<scope>): <short description>

Types: feat, fix, docs, chore, refactor, test
Scopes: backend, mobile, dashboard, infra, docs

Examples:
feat(backend): add phone OTP login endpoint
docs: add database design ER diagram
chore(infra): add docker-compose for postgres and redis
```

---

## 3. Local Development Setup

### 3.1 Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker Desktop | Latest | PostgreSQL, Redis, OSRM |
| Python | 3.11+ | Backend |
| Flutter | 3.22+ | Mobile client |
| Git | 2.40+ | Version control |

### 3.2 First-time setup

```bash
git clone https://github.com/nithishkumar202020/MealsOnWheels.git
cd MealsOnWheels

# Start infrastructure
docker compose up -d postgres redis

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Run migrations
docker compose exec postgres psql -U mealsonwheels -d highway_food_booking \
  -f /docker-entrypoint-initdb.d/001_create_tables.sql

# Start API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3.3 Verify setup

```bash
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"phone": "+919876543210", "otp": "123456"}'
```

---

## 4. Python / FastAPI Conventions

### 4.1 Project layout

```
backend/app/
├── main.py           # App factory, middleware, router includes
├── config.py         # pydantic-settings Settings class
├── db.py             # Engine, sessionmaker, get_db dependency
├── cache.py          # Redis wrapper
├── deps.py           # Shared dependencies (get_current_user)
├── core/security.py  # JWT, hashing
├── models/           # SQLAlchemy ORM (one file per entity)
├── schemas/          # Pydantic models (request/response)
├── routers/          # APIRouter modules
└── services/         # External integrations, business logic
```

### 4.2 Code style

- **Formatter:** `black` (line length 100)
- **Linter:** `ruff`
- **Type hints:** Required on all function signatures
- **Imports:** stdlib → third-party → local; sorted by ruff
- **Async:** Use `async def` for route handlers and DB operations

### 4.3 Patterns

**Router example shape:**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from app.deps import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    ...
```

**Rules:**
- Routers are thin — delegate to services for complex logic
- Pydantic schemas for all request/response bodies
- Raise `HTTPException` with appropriate status codes
- Never return raw SQLAlchemy models — always map to schemas

### 4.4 Environment variables

- Load via `pydantic-settings` in `config.py`
- Never hardcode secrets
- `.env` is gitignored; `.env.example` documents all vars

---

## 5. Flutter / Dart Conventions

### 5.1 Project layout

```
mobile/lib/
├── main.dart
├── theme/app_theme.dart
├── models/           # Data classes (restaurant, booking, user)
├── services/         # api_service.dart, auth_service.dart
├── providers/        # Riverpod providers (Phase 2; Provider in sprint)
├── screens/          # One file per screen
└── widgets/          # Reusable UI components
```

### 5.2 Code style

- **Formatter:** `dart format` (default settings)
- **Linter:** `flutter_lints` package
- **Naming:** `lowerCamelCase` variables, `UpperCamelCase` classes
- **Files:** `snake_case.dart`

### 5.3 State management

- **MVP sprint:** `provider` package (per execution plan)
- **Post-MVP:** migrate to `riverpod` ([02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md))

### 5.4 API service pattern

- Base URL from environment/config constant
- JWT attached via interceptor reading SharedPreferences
- On 401: clear token, navigate to login

---

## 6. Database Conventions

- Table names: plural snake_case (`users`, `bookings`)
- Primary keys: `BIGSERIAL id`
- Timestamps: `TIMESTAMPTZ`, always UTC in application layer
- Migrations: numbered SQL files in `backend/migrations/`
- PostGIS: always `GEOGRAPHY(POINT, 4326)` for lat/lon points

---

## 7. API Conventions

- Prefix: `/api`
- JSON only
- Errors: `{ "detail": "...", "code": "..." }` per [05_API_SPEC.md](./05_API_SPEC.md)
- Auth: `Authorization: Bearer <token>`
- FastAPI auto-docs at `/docs` — keep in sync with [05_API_SPEC.md](./05_API_SPEC.md)

---

## 8. Testing (Sprint vs Post-Sprint)

**24h sprint:** Manual testing only in final 2 hours. No automated test requirement.

**Post-sprint:** See [11_TESTING.md](./11_TESTING.md) for pytest + Flutter test strategy.

During sprint, each stream owner verifies their endpoints with `curl` before marking checkpoint complete.

---

## 9. Pull Request Checklist

- [ ] Endpoint tested locally with curl or Flutter
- [ ] No secrets in diff
- [ ] `.env.example` updated if new env vars added
- [ ] Related doc updated if API contract changed
- [ ] No unrelated refactoring

---

## 10. Docker Compose Services

| Service | Port | Image |
|---------|------|-------|
| `postgres` | 5432 | `postgis/postgis:16-3.4` |
| `redis` | 6379 | `redis:7-alpine` |
| `backend` | 8000 | Built from `backend/Dockerfile` |
| `osrm` | 5000 | `osrm/osrm-backend` (optional) |

---

## 11. Debugging Tips

| Issue | Check |
|-------|-------|
| DB connection refused | `docker compose ps`; verify `DATABASE_URL` |
| Redis fallback active | Look for startup log "Redis unavailable, running without cache" |
| JWT 401 | Verify `JWT_SECRET` matches; check token expiry |
| CORS error | Add Flutter web origin to `CORS_ORIGINS` |
| PostGIS error | Ensure `CREATE EXTENSION postgis` ran |

---

## 12. Related Documents

- [05_API_SPEC.md](./05_API_SPEC.md)
- [11_TESTING.md](./11_TESTING.md)
- [12_DEPLOYMENT.md](./12_DEPLOYMENT.md)
- [09_ARCHITECTURE_DECISIONS.md](./09_ARCHITECTURE_DECISIONS.md)
