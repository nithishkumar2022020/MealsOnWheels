"""Best-effort rate limiting on top of the Redis counter.

Fails **open**: when Redis cannot answer, the request is allowed and the fact
that the limit was unenforceable is logged. Failing closed would turn a cache
outage into a total auth outage — the cache is an optimisation and must never be
able to fail a request (docs/10_SECURITY.md section 9, ADR-0004).

That is also why the stub OTP is unreachable in production. A constant password
behind a limit that resets on every cold start is no protection, so the limit is
not asked to carry weight it cannot.
"""

from __future__ import annotations

import logging

from app.cache import cache
from app.errors import AppError

logger = logging.getLogger(__name__)

# Limits from docs/10_SECURITY.md section 9, as (limit, window_seconds).
LOGIN_LIMIT = (10, 3600)  # per phone
REGISTER_LIMIT = (5, 3600)  # per IP


async def enforce(key: str, limit: int, window_seconds: int) -> None:
    """Raise 429 when `key` has exceeded `limit` within the window.

    Returns silently when the counter is unavailable.
    """
    count = await cache.incr_with_expiry(f"ratelimit:{key}", window_seconds)
    if count is None:
        logger.warning(
            "rate limit not enforceable (cache unavailable)",
            extra={"extra_fields": {"event": "rate_limit_unenforceable", "limit_key": key}},
        )
        return

    if count > limit:
        logger.info(
            "rate limit exceeded",
            extra={"extra_fields": {"event": "rate_limited", "limit_key": key, "count": count}},
        )
        raise _too_many_requests(window_seconds)


def _too_many_requests(window_seconds: int) -> AppError:
    error = AppError(
        status_code=429,
        code="RATE_LIMITED",
        detail="Too many requests. Try again later.",
    )
    # Retry-After is part of the documented 429 contract. Worst case the caller
    # waits the full window; the per-key TTL may already be shorter.
    error.headers = {"Retry-After": str(window_seconds)}
    return error


def login_key(phone: str) -> str:
    """Login is limited per phone, so one number cannot be brute-forced."""
    return f"login:{phone}"


def register_key(client_ip: str) -> str:
    """Register is limited per IP: there is no account to key on yet."""
    return f"register:{client_ip}"
