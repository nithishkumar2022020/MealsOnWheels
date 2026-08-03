# Deployment — Highway Food Pre-Booking Platform

**Document version:** 1.0  
**Last updated:** 2026-07-25  
**Parent:** [03_SYSTEM_ARCHITECTURE.md](./03_SYSTEM_ARCHITECTURE.md), [08_DEVELOPMENT_GUIDELINES.md](./08_DEVELOPMENT_GUIDELINES.md)

---

## 1. Deployment Overview

| Environment | Purpose | Infrastructure |
|-------------|---------|----------------|
| Local | Development | docker-compose (postgres, redis, backend) |
| Production (MVP) | Live demo | Render web service + managed PG + Redis |
| CI | Build & verify | GitHub Actions |

**Target URL (production):** `https://<service-name>.onrender.com`

---

## 2. Docker Architecture

### 2.1 Backend Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.2 docker-compose.yml (local)

| Service | Image | Ports | Volumes |
|---------|-------|-------|---------|
| `postgres` | `postgis/postgis:16-3.4` | 5432 | `pgdata` |
| `redis` | `redis:7-alpine` | 6379 | — |
| `backend` | build `./backend` | 8000 | — |

**postgres init:** Mount `backend/migrations/001_create_tables.sql` to `/docker-entrypoint-initdb.d/`

**Environment:** Backend reads from `.env` file or compose `environment` block.

---

## 3. Environment Variables

### 3.1 Backend (all environments)

| Variable | Local example | Production |
|----------|---------------|------------|
| `DATABASE_URL` | `postgresql+asyncpg://mealsonwheels:password@postgres:5432/highway_food_booking` | Render PostgreSQL URL (convert to asyncpg) |
| `REDIS_URL` | `redis://redis:6379/0` | Render Redis URL |
| `JWT_SECRET` | dev-only random string | 32+ byte random (Render secret) |
| `JWT_EXPIRE_HOURS` | `24` | `24` |
| `ENVIRONMENT` | `development` | `production` — **must be set explicitly**; no default |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8080` | Flutter web URL; never `*` |
| `NOMINATIM_BASE_URL` | `https://nominatim.openstreetmap.org` | Same (throttled) |
| `NOMINATIM_USER_AGENT` | `MealsOnWheels/1.0 (+https://github.com/nithishkumar2022020/MealsOnWheels)` | Same |
| `OVERPASS_URL` | `https://overpass-api.de/api/interpreter` | Same (throttled) |

Setting `ENVIRONMENT=production` disables the OTP stub, refuses the shared dashboard token,
and turns off `/docs`, `/redoc`, and `/openapi.json`. Since the platform has no SMS provider
and no per-restaurant auth yet, a production deploy today has **no working login path** —
that is intentional. See [10_SECURITY.md](./10_SECURITY.md) §10 for what must land first.

### 3.2 Email

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | Gmail or Mailgun SMTP host |
| `SMTP_PORT` | 587 |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP password |
| `EMAIL_FROM` | Sender address |

---

## 4. Database Migrations

### 4.1 Local (first run)

```bash
docker compose up -d postgres
docker compose exec postgres psql -U mealsonwheels -d highway_food_booking \
  -f /docker-entrypoint-initdb.d/001_create_tables.sql
```

### 4.2 Production (Render)

Run via `backend/scripts/migrate.py`:

```bash
python scripts/migrate.py
```

`migrate.py` runs `001_create_tables.sql` via psycopg2 against `DATABASE_URL`.

**Render first deploy:** Run migration as one-off job or in startup script (idempotent `IF NOT EXISTS`).

---

## 5. Render Setup

### 5.1 Create resources

1. **PostgreSQL** — Render dashboard → New → PostgreSQL (free tier)
2. **Redis** — New → Redis (free tier)
3. **Web Service** — New → Web Service → Connect GitHub repo

### 5.2 Web service configuration

| Setting | Value |
|---------|-------|
| Root directory | `backend` |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/health` |

### 5.3 Environment variables

Copy all vars from section 3.1 into Render dashboard. Link `DATABASE_URL` and `REDIS_URL` from managed services.

### 5.4 Flutter web deploy

```bash
cd mobile
flutter build web --dart-define=API_URL=https://<service>.onrender.com
```

Deploy `build/web/` to Render Static Site or Netlify free tier.

---

## 6. CI/CD Pipeline (GitHub Actions)

```mermaid
flowchart LR
  Push[Push_to_main] --> Lint[Lint_ruff_black]
  Lint --> Test[Test_pytest_optional]
  Test --> Build[Build_Docker_image]
  Build --> Deploy[Deploy_Render]
  Deploy --> Health[Health_check]
```

### 6.1 Workflow file

`.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        working-directory: backend
        run: |
          pip install -r requirements.txt
          pip install ruff black

      - name: Lint
        working-directory: backend
        run: |
          ruff check app/
          black --check app/

      - name: Test
        working-directory: backend
        run: pytest tests/ -v --cov=app --cov-fail-under=60

  deploy:
    needs: backend
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Render deploy
        run: echo "Render auto-deploys on push when connected"
```

Lint and tests both gate the merge. A failing test blocks deploy — see
[11_TESTING.md](./11_TESTING.md) §7. Flutter steps activate once the client exists.

### 6.2 Render auto-deploy

Connect Render web service to GitHub `main` branch. Push triggers deploy automatically after CI passes.

---

## 7. Production Topology

```mermaid
flowchart TB
  User[Traveller_FlutterWeb]
  RestDash[Restaurant_Dashboard]
  Render[Render_LoadBalancer]
  API[FastAPI_Container]
  PG[(Render_PostgreSQL)]
  Redis[(Render_Redis)]

  User --> Render
  RestDash --> Render
  Render --> API
  API --> PG
  API --> Redis
```

---

## 8. Health Checks & Monitoring

### 8.1 Health endpoint

`GET /api/health` returns:

```json
{
  "status": "ok",
  "database": "connected",
  "redis": "connected"
}
```

Render uses this for service health checks.

### 8.2 Logging (MVP)

- Structured JSON logs to stdout (Render captures)
- Log level: `INFO` in production, `DEBUG` in development
- Include request ID per request (middleware)
- Never log PII or JWT tokens; phone numbers masked as `+919****3210`

**Request timing line.** The middleware emits one line per request so the P95 targets in
[02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md) §7 can actually be computed before
Prometheus exists:

```json
{
  "event": "request",
  "request_id": "3f2a…",
  "method": "GET",
  "route": "/api/restaurants/search",
  "status_code": 200,
  "duration_ms": 84,
  "cache_hit": true
}
```

`route` is the **template**, not the resolved path — `/api/bookings/{id}`, never
`/api/bookings/42`. Logging resolved paths makes percentiles impossible to group and leaks
identifiers into logs. `cache_hit` is omitted on routes that do not consult the cache.

### 8.3 Monitoring (Phase 2)

- Uptime monitoring: UptimeRobot (free) on `/api/health`
- Error tracking: Sentry
- Metrics: Prometheus + Grafana or Render metrics

---

## 9. Backup & Recovery

| Component | Strategy |
|-----------|----------|
| PostgreSQL | Render daily automated backups (7-day retention free tier) |
| Redis | Ephemeral cache; no backup needed |
| Code | GitHub repository |
| Secrets | Render env vars; document in password manager |

**Recovery procedure:**
1. Restore PostgreSQL from Render backup snapshot
2. Redeploy latest Docker image from `main`
3. Verify `/api/health` and run manual smoke test ([11_TESTING.md](./11_TESTING.md))

---

## 10. Rollback

1. Render dashboard → Deploys → select previous successful deploy → Rollback
2. If migration caused issue: restore DB backup; migrations are forward-only in MVP

---

## 11. SSL & Domain

- Render provides free SSL on `*.onrender.com`
- Custom domain (Phase 2): add CNAME in DNS; Render auto-provisions Let's Encrypt

---

## 12. Pre-Deploy Checklist

- [ ] PostgreSQL created on Render; `DATABASE_URL` set
- [ ] Redis created; `REDIS_URL` set
- [ ] `JWT_SECRET` set to production random value
- [ ] Migrations run successfully
- [ ] `/api/health` returns 200
- [ ] `POST /api/auth/login` works on production
- [ ] Flutter `API_URL` points to production
- [ ] CORS includes Flutter web origin
- [ ] Automated suite green in CI; manual smoke test
      ([11_TESTING.md](./11_TESTING.md) §3) passes against the deployed URL

---

## 13. Related Documents

- [08_DEVELOPMENT_GUIDELINES.md](./08_DEVELOPMENT_GUIDELINES.md)
- [10_SECURITY.md](./10_SECURITY.md)
- [11_TESTING.md](./11_TESTING.md)
- [09_ARCHITECTURE_DECISIONS.md](./09_ARCHITECTURE_DECISIONS.md) — ADR-0009
