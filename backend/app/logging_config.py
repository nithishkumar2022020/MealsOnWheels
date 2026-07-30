"""Structured logging and the request-timing middleware.

Emits one JSON line per request so the P95 targets in
docs/02_TECHNICAL_SPEC.md section 7 can actually be computed from logs before
Prometheus exists. Targets nobody can measure are not requirements.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# Set by handlers that consult the cache; read and cleared by the middleware.
cache_hit_ctx: ContextVar[bool | None] = ContextVar("cache_hit", default=None)


def mask_phone(phone: str | None) -> str:
    """+919876543210 -> +919****3210. Never log or display an unmasked phone."""
    if not phone:
        return "-"
    if len(phone) < 8:
        return "*" * len(phone)
    return f"{phone[:4]}****{phone[-4:]}"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        if isinstance(getattr(record, "extra_fields", None), dict):
            payload.update(record.extra_fields)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Uvicorn's access log duplicates our request line in a different shape.
    logging.getLogger("uvicorn.access").disabled = True


logger = logging.getLogger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request_id_ctx.set(request_id)
        cache_hit_ctx.set(None)

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            logger.exception(
                "request failed",
                extra={
                    "extra_fields": {
                        "event": "request",
                        "method": request.method,
                        "route": _route_template(request),
                        "status_code": 500,
                        "duration_ms": duration_ms,
                    }
                },
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        fields = {
            "event": "request",
            "method": request.method,
            # Template, not the resolved path: /api/bookings/{id}, never
            # /api/bookings/42. Resolved paths make percentiles ungroupable and
            # leak identifiers into logs.
            "route": _route_template(request),
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        cache_hit = cache_hit_ctx.get()
        if cache_hit is not None:
            fields["cache_hit"] = cache_hit

        logger.info("request", extra={"extra_fields": fields})
        response.headers["X-Request-ID"] = request_id
        return response


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)
