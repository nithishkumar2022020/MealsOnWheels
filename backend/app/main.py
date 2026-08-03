"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.cache import cache
from app.config import get_settings
from app.db import SessionLocal, engine
from app.errors import AppError
from app.logging_config import RequestContextMiddleware, configure_logging
from app.routers import auth as auth_router
from app.routers import restaurant_auth as restaurant_auth_router
from app.routers import restaurants as restaurants_router
from app.routers import routes as routes_router
from app.routers import users as users_router

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "starting up",
        extra={
            "extra_fields": {
                "environment": settings.ENVIRONMENT,
                "cache_configured": cache.configured,
                "docs_enabled": settings.docs_enabled,
            }
        },
    )
    yield
    await cache.close()
    await engine.dispose()


app = FastAPI(
    title="MealsOnWheels API",
    description="Highway food pre-booking platform",
    version="0.1.0",
    lifespan=lifespan,
    # Interactive docs enumerate every endpoint and schema. Disabled in
    # production (docs/10_SECURITY.md section 3.5).
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


# --- Error handlers: normalise everything to {detail, code} ----------------


@app.exception_handler(AppError)
async def _app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        # Carries Retry-After on a 429; empty otherwise.
        headers=exc.headers,
    )


@app.exception_handler(StarletteHTTPException)
async def _http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Covers 404s on unmatched routes and anything raising a bare
    # HTTPException, so no response escapes without a code.
    default_codes = {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
    }
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "code": default_codes.get(exc.status_code, "HTTP_ERROR"),
        },
    )


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    message = first.get("msg", "Invalid request")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": f"{location}: {message}" if location else message,
            "code": "UNPROCESSABLE_ENTITY",
        },
    )


@app.exception_handler(Exception)
async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Logged with a stack trace; the client gets none of it.
    logger.exception("unhandled exception")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "code": "INTERNAL_ERROR"},
    )


# --- Routers --------------------------------------------------------------

app.include_router(auth_router.router)
app.include_router(restaurant_auth_router.router)
app.include_router(users_router.router)
app.include_router(routes_router.router)
app.include_router(restaurants_router.router)


# --- Health ---------------------------------------------------------------


@app.get("/api/health", tags=["health"])
async def health() -> JSONResponse:
    """Liveness and dependency check.

    Returns 503 when the database is unreachable, since nothing useful works
    without it. A missing or broken cache is reported but stays 200 — degraded
    is not down (docs/05_API_SPEC.md section 10).
    """
    db_state = "connected"
    http_status = status.HTTP_200_OK
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("health check: database unreachable: %s", exc)
        db_state = "unreachable"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE

    if not cache.configured:
        redis_state = "not_configured"
    else:
        redis_state = "connected" if await cache.ping() else "unreachable"

    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ok" if http_status == status.HTTP_200_OK else "degraded",
            "database": db_state,
            "redis": redis_state,
            "environment": settings.ENVIRONMENT,
        },
    )
