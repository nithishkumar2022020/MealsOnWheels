"""Stage 7 tests: configuration guards, error envelope, health check.

The config tests matter more than they look. Three security controls key off
ENVIRONMENT, and the promise that the OTP stub cannot be reached in production
is only worth as much as the code enforcing it.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = {
    "ENVIRONMENT": "development",
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/db",
    "JWT_SECRET": "a-development-secret-that-is-long-enough-here",
    "RESTAURANT_DASHBOARD_TOKEN": "dev-token",
}

PROD = {
    **BASE,
    "ENVIRONMENT": "production",
    "JWT_SECRET": "x" * 48,
    "RESTAURANT_DASHBOARD_TOKEN": None,
    "CORS_ORIGINS": "https://app.example.org",
}


def test_environment_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    # Must clear the ambient value: pydantic-settings reads the real
    # environment, and docker-compose sets ENVIRONMENT for the container.
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    fields = {k: v for k, v in BASE.items() if k != "ENVIRONMENT"}
    with pytest.raises(ValidationError):
        # No default: a deploy that forgets this must fail loudly rather than
        # silently behaving as development.
        Settings(_env_file=None, **fields)


def test_environment_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**BASE, "ENVIRONMENT": "staging"})


def test_sync_database_url_rejected() -> None:
    with pytest.raises(ValidationError, match="asyncpg"):
        Settings(
            _env_file=None,
            **{**BASE, "DATABASE_URL": "postgresql://u:p@localhost:5432/db"},
        )


def test_dev_requires_dashboard_token() -> None:
    with pytest.raises(ValidationError, match="RESTAURANT_DASHBOARD_TOKEN"):
        Settings(_env_file=None, **{**BASE, "RESTAURANT_DASHBOARD_TOKEN": None})


def test_otp_stub_allowed_outside_production() -> None:
    assert Settings(_env_file=None, **BASE).otp_stub_allowed is True


def test_otp_stub_blocked_in_production() -> None:
    settings = Settings(_env_file=None, **PROD)
    assert settings.otp_stub_allowed is False
    assert settings.docs_enabled is False


def test_production_rejects_short_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(_env_file=None, **{**PROD, "JWT_SECRET": "too-short"})


def test_production_rejects_placeholder_secret() -> None:
    placeholder = "change-me-this-is-a-development-placeholder-value"
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(_env_file=None, **{**PROD, "JWT_SECRET": placeholder})


def test_production_rejects_shared_dashboard_token() -> None:
    # The shared static token is demo-grade; production must not run on it.
    with pytest.raises(ValidationError, match="RESTAURANT_DASHBOARD_TOKEN"):
        Settings(_env_file=None, **{**PROD, "RESTAURANT_DASHBOARD_TOKEN": "anything"})


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match=r"\*"):
        Settings(_env_file=None, **{**PROD, "CORS_ORIGINS": "*"})


def test_production_requires_cors_origins() -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(_env_file=None, **{**PROD, "CORS_ORIGINS": ""})


def test_production_rejects_placeholder_user_agent() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(
            _env_file=None,
            **{**PROD, "NOMINATIM_USER_AGENT": "MealsOnWheels/1.0 (contact@example.com)"},
        )


def test_cors_origins_parsed_into_list() -> None:
    settings = Settings(
        _env_file=None, **{**BASE, "CORS_ORIGINS": "http://a.test, http://b.test ,"}
    )
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


# --- Error envelope -------------------------------------------------------


async def test_unknown_route_returns_error_envelope(client) -> None:
    response = await client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    # Every error carries both keys — no bare FastAPI shape escapes.
    assert body["code"] == "NOT_FOUND"
    assert "detail" in body


async def test_request_id_echoed_in_response_header(client) -> None:
    response = await client.get("/api/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"


async def test_request_id_generated_when_absent(client) -> None:
    response = await client.get("/api/health")
    assert response.headers.get("X-Request-ID")


# --- Health ---------------------------------------------------------------


async def test_health_reports_dependency_states(client) -> None:
    """Health always answers with a known state for each dependency.

    Deliberately does not assert a *specific* cache state: whether Redis is
    configured depends on the environment this runs in (compose sets REDIS_URL,
    a bare local run may not). Pinning it here would make the suite pass or
    fail on ambient config rather than on behaviour.

    What matters is the contract: every dependency reports one of a closed set
    of states, and a cache problem never turns into a failed request.
    """
    response = await client.get("/api/health")
    body = response.json()

    assert body["redis"] in {"connected", "unreachable", "not_configured"}
    assert body["database"] in {"connected", "unreachable"}
    # `environment` is echoed but not asserted: it reflects whatever the host
    # environment supplies. The gating behaviour it drives is covered by the
    # Settings tests above, which construct their own values.
    assert "environment" in body

    # The load-bearing assertion: the response is only ever 503 because of the
    # database. A missing or broken cache leaves the service up.
    if body["database"] == "connected":
        assert response.status_code == 200
        assert body["status"] == "ok"
    else:
        assert response.status_code == 503


async def test_cache_operations_are_safe_without_redis() -> None:
    """A Cache with no URL behaves as a permanent miss, never raising.

    This is the fail-open contract from docs/03_SYSTEM_ARCHITECTURE.md section 8
    exercised directly, independent of whether a Redis happens to be running.
    """
    from app.cache import Cache

    unconfigured = Cache(None)
    assert unconfigured.configured is False
    assert await unconfigured.get_json("any-key") is None
    # Writes are silently dropped rather than raising.
    await unconfigured.set_json("any-key", {"a": 1}, ttl_seconds=60)
    assert await unconfigured.get_json("any-key") is None
    # None means "cannot enforce", which callers treat as best-effort.
    assert await unconfigured.incr_with_expiry("counter", ttl_seconds=60) is None
    assert await unconfigured.ping() is False
    await unconfigured.close()


async def test_cache_survives_unreachable_redis() -> None:
    """A configured-but-dead Redis degrades instead of raising.

    Points at a closed port, which is the mid-run failure mode the boot-time
    availability flag could not handle.
    """
    from app.cache import Cache

    dead = Cache("redis://127.0.0.1:6390/0")
    assert dead.configured is True
    assert await dead.ping() is False
    assert await dead.get_json("k") is None
    await dead.set_json("k", {"v": 1}, ttl_seconds=30)
    assert await dead.incr_with_expiry("c", ttl_seconds=30) is None
    await dead.close()
