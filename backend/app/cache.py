"""Redis cache wrapper with per-operation fail-open semantics.

The cache is an optimisation and must never be able to fail a request. Every
operation here swallows Redis errors, logs them, and reports a miss, so a Redis
outage degrades latency rather than availability.

This is deliberately not a boot-time availability flag. Probing once at startup
only handles "Redis was already down when we booted"; the more common failure —
Redis dying, restarting, or dropping connections mid-run, which is routine on a
free tier — would raise on every subsequent request. See
docs/03_SYSTEM_ARCHITECTURE.md section 8.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.config import get_settings

logger = logging.getLogger(__name__)

# Warn at most once per interval instead of once per failed operation: a Redis
# outage would otherwise emit a line per request and bury everything else.
_WARN_INTERVAL_SECONDS = 60.0


class Cache:
    def __init__(self, url: str | None) -> None:
        self._url = url
        self._client: aioredis.Redis | None = None
        self._last_warned_at: float = 0.0

        if url:
            self._client = aioredis.from_url(
                url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=False,
            )
        else:
            # Not a failure: running without a cache is a supported mode.
            logger.info("REDIS_URL not set; running without cache")

    @property
    def configured(self) -> bool:
        return self._client is not None

    def _warn(self, operation: str, exc: Exception) -> None:
        now = time.monotonic()
        if now - self._last_warned_at >= _WARN_INTERVAL_SECONDS:
            self._last_warned_at = now
            logger.warning("cache unavailable, continuing without it (op=%s): %s", operation, exc)

    async def get_json(self, key: str) -> Any | None:
        """Return the cached value, or None on miss or any Redis failure."""
        if self._client is None:
            return None
        try:
            raw = await self._client.get(key)
        except (RedisError, OSError) as exc:
            self._warn("get", exc)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Corrupt or stale-format entry: treat as a miss and move on.
            logger.warning("discarding malformed cache entry for key=%s", key)
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Best-effort write. A failure here is never surfaced to the caller."""
        if self._client is None:
            return
        try:
            await self._client.set(key, json.dumps(value), ex=ttl_seconds)
        except (RedisError, OSError, TypeError) as exc:
            self._warn("set", exc)

    async def incr_with_expiry(self, key: str, ttl_seconds: int) -> int | None:
        """Increment a counter, setting its TTL on first use.

        Returns the new count, or None if Redis is unavailable — callers treat
        None as "cannot enforce", which is why rate limits are documented as
        best-effort without Redis (docs/10_SECURITY.md section 9).
        """
        if self._client is None:
            return None
        try:
            async with self._client.pipeline(transaction=True) as pipe:
                pipe.incr(key)
                pipe.expire(key, ttl_seconds, nx=True)
                count, _ = await pipe.execute()
            return int(count)
        except (RedisError, OSError) as exc:
            self._warn("incr", exc)
            return None

    async def ping(self) -> bool:
        """Health-check probe. Never raises."""
        if self._client is None:
            return False
        try:
            return bool(await self._client.ping())
        except (RedisError, OSError):
            return False

    async def close(self) -> None:
        if self._client is not None:
            # Shutdown path: a Redis error here is not worth surfacing.
            with contextlib.suppress(RedisError, OSError):
                await self._client.aclose()


cache = Cache(get_settings().REDIS_URL)
