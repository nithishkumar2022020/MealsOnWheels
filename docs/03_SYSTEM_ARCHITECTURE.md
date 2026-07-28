# System Architecture — Highway Food Pre-Booking Platform

**Document version:** 1.0  
**Last updated:** 2026-07-25  
**Parent:** [02_TECHNICAL_SPEC.md](./02_TECHNICAL_SPEC.md)

---

## 1. Architecture Overview

MealsOnWheels follows a **modular monolith** pattern: a single FastAPI deployable unit with clear internal module boundaries. This avoids microservice operational overhead in MVP while preserving clean seams for future extraction (notifications, ETA service).

**Design goals:**

- Open-source first, zero-cost where practical
- Simple before clever
- Security by default
- Horizontal scale path via stateless API + managed PostgreSQL/Redis

---

## 2. Context Diagram (C4 Level 1)

```mermaid
flowchart TB
  Traveller[Traveller_FlutterApp]
  Restaurant[Restaurant_Dashboard]
  Admin[Internal_Admin]

  subgraph platform [MealsOnWheels_Platform]
    API[FastAPI_Backend]
    DB[(PostgreSQL_PostGIS)]
    Cache[(Redis)]
    R2[(Cloudflare_R2)]
  end

  subgraph external [External_OSS_Services]
    OSM[OpenStreetMap_Tiles]
    Nominatim[Nominatim]
    Overpass[Overpass_API]
    OSRM[OSRM_Routing]
    SMTP[Email_SMTP]
  end

  Traveller --> API
  Restaurant --> API
  Admin --> API
  API --> DB
  API --> Cache
  API --> R2
  API --> Nominatim
  API --> Overpass
  API --> OSRM
  API --> SMTP
  Traveller --> OSM
```

---

## 3. Container Diagram (C4 Level 2)

```mermaid
flowchart LR
  subgraph clients [Clients]
    Flutter[Flutter_App]
    DashWeb[Dashboard_Web]
  end

  subgraph render [Render_Hosting_MVP]
    WebSvc[FastAPI_Container]
    PG[(PostgreSQL)]
    Redis[(Redis)]
  end

  subgraph localDev [Local_DockerCompose]
    DevAPI[backend:8000]
    DevPG[postgres:5432]
    DevRedis[redis:6379]
    DevOSRM[osrm:5000]
  end

  Flutter -->|HTTPS_JSON| WebSvc
  DashWeb -->|HTTPS_JSON| WebSvc
  WebSvc --> PG
  WebSvc --> Redis
  WebSvc -->|optional| DevOSRM
```

---

## 4. Backend Internal Structure

```mermaid
flowchart TB
  subgraph fastapi [FastAPI_App]
    Main[main.py]
    AuthR[routers/auth]
    UserR[routers/users]
    RestR[routers/restaurants]
    BookR[routers/bookings]
    DashR[routers/dashboard]
    RateR[routers/ratings]
  end

  subgraph services [Services_Layer]
    NomSvc[nominatim.py]
    OvSvc[overpass.py]
    NotifSvc[notifications.py]
  end

  subgraph data [Data_Layer]
    ORM[SQLAlchemy_Models]
    RedisC[cache.py]
  end

  Main --> AuthR & UserR & RestR & BookR & DashR & RateR
  RestR --> NomSvc & OvSvc & RedisC
  BookR --> NotifSvc
  DashR --> NotifSvc
  AuthR & UserR & RestR & BookR & DashR & RateR --> ORM
  ORM --> PG[(PostgreSQL)]
  RedisC --> Redis[(Redis)]
```

---

## 5. Request Flow — Restaurant Search

```mermaid
sequenceDiagram
  participant C as Client
  participant API as FastAPI
  participant Redis as Redis
  participant DB as PostgreSQL
  participant OV as Overpass

  C->>API: GET /restaurants/search
  API->>Redis: GET cache_key
  alt Cache hit
    Redis-->>API: Cached JSON
    API-->>C: 200 restaurants
  else Cache miss
    API->>DB: SELECT route + local restaurants
    API->>OV: nearby_restaurants query
    alt Overpass OK
      OV-->>API: OSM nodes
    else Overpass down
      API-->>API: Use DB results only
    end
    API->>API: Merge + dedupe
    API->>Redis: SET cache_key TTL 7d
    API-->>C: 200 restaurants
  end
```

---

## 6. Request Flow — Booking Lifecycle

```mermaid
sequenceDiagram
  participant T as Traveller
  participant API as FastAPI
  participant DB as PostgreSQL
  participant N as Notifications
  participant Rest as RestaurantDashboard

  T->>API: POST /bookings/create
  API->>DB: INSERT booking status=pending
  API->>N: send_booking_confirmation
  API-->>T: booking_id cutoff_time

  Rest->>API: GET /dashboard/orders
  API->>DB: SELECT pending by cutoff
  API-->>Rest: orders list

  Rest->>API: PUT /dashboard/orders/:id/confirm
  API->>DB: UPDATE status=confirmed
  API->>N: send_order_status_update
  API-->>Rest: 200

  T->>API: GET /bookings/:id
  API-->>T: status=confirmed
```

---

## 7. Authentication Architecture

```mermaid
flowchart LR
  Login[POST_auth_login] --> VerifyOTP[Verify_OTP_123456]
  VerifyOTP --> IssueJWT[Issue_JWT_HS256]
  IssueJWT --> Client[Client_Stores_Token]
  Client --> Bearer[Authorization_Bearer]
  Bearer --> Deps[get_current_user]
  Deps --> Decode[python_jose_decode]
  Decode --> LoadUser[Load_User_From_DB]
```

**MVP:** Single access token, 24h expiry.  
**Phase 2:** Access (15 min) + refresh (7 days) in Redis; token blocklist on logout. See [10_SECURITY.md](./10_SECURITY.md).

---

## 8. Caching Strategy

| Layer | What | Invalidation |
|-------|------|--------------|
| Redis | Restaurant search results | TTL 7 days; manual flush on restaurant update |
| Redis | Nominatim reverse geocode | TTL 30 days |
| Client (Flutter) | JWT in SharedPreferences | On logout / 401 |
| PostgreSQL | Materialized views (Phase 2) | Nightly refresh for stats |

**Redis unavailable:** Application sets `REDIS_AVAILABLE=false` at startup and skips cache reads/writes. All requests hit DB and external APIs directly. Log warning once at boot.

---

## 9. Geospatial Architecture

### MVP (sprint)

- Point-radius search: restaurants within `radius_km` of `(latitude, longitude)`
- Overpass supplements OSM POIs not yet in local DB
- 10 manually seeded restaurants on Delhi-Chandigarh corridor

### Production (Phase 1.5)

- Route polylines stored as PostGIS `LINESTRING`
- Corridor buffer via `ST_DWithin(geography)`
- OSRM generates polylines when admin creates routes

```mermaid
flowchart LR
  Origin[Origin_Coords] --> OSRM
  Dest[Destination_Coords] --> OSRM
  OSRM --> Polyline[Route_Polyline]
  Polyline --> PostGIS[ST_DWithin_Query]
  PostGIS --> Results[Matching_Restaurants]
```

---

## 10. Deployment Topology (Render MVP)

```mermaid
flowchart TB
  GitHub[GitHub_Repo] -->|push main| GHA[GitHub_Actions]
  GHA -->|build push| Docker[Docker_Image]
  Docker --> Render[Render_Web_Service]
  Render --> RenderPG[Render_PostgreSQL]
  Render --> RenderRedis[Render_Redis]
  FlutterWeb[Flutter_Web_Build] --> RenderStatic[Render_Static_Site]
  FlutterWeb --> API[Render_API_URL]
```

Details in [12_DEPLOYMENT.md](./12_DEPLOYMENT.md).

---

## 11. Failure Modes & Degradation

| Failure | System behavior |
|---------|-----------------|
| Redis down | Continue without cache; higher latency |
| Overpass timeout | Return DB-seeded restaurants only |
| Nominatim rate limit | Return cached or skip reverse geocode label |
| PostgreSQL down | 503 on all data endpoints; health check fails |
| OSRM down | Route polylines unavailable; point search still works |
| Email SMTP down | Log notification; booking still created |

---

## 12. Scalability Path

| Stage | Architecture |
|-------|--------------|
| MVP | Single Render web service, managed PG + Redis |
| 10K DAU | Horizontal API replicas behind load balancer; connection pooling (PgBouncer) |
| 100K DAU | Read replica for search; CDN for static assets; dedicated Overpass/Nominatim |
| 1M+ DAU | Extract notification service; event bus (Redis Streams → Kafka); ETA microservice |

No premature extraction in MVP.

---

## 13. Related Documents

- [04_DATABASE_DESIGN.md](./04_DATABASE_DESIGN.md)
- [05_API_SPEC.md](./05_API_SPEC.md)
- [09_ARCHITECTURE_DECISIONS.md](./09_ARCHITECTURE_DECISIONS.md)
- [10_SECURITY.md](./10_SECURITY.md)
- [12_DEPLOYMENT.md](./12_DEPLOYMENT.md)
