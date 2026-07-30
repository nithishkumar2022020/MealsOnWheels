"""Shared test fixtures.

Environment is set before any app module is imported, so config.Settings
validates against test values rather than whatever is in a local .env.
"""

from __future__ import annotations

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://mealsonwheels:localdev@localhost:5432/highway_food_booking_test",
)
os.environ.setdefault("JWT_SECRET", "test-secret-value-that-is-long-enough-32chars")
os.environ.setdefault("RESTAURANT_DASHBOARD_TOKEN", "test-restaurant-token")
# Unset so tests exercise the no-cache path by default; cache behaviour is
# tested explicitly where it matters.
os.environ.pop("REDIS_URL", None)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402


@pytest.fixture
async def client():
    """HTTP client bound to the app without starting a server."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
