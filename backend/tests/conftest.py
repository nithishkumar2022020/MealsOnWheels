"""Shared test fixtures.

Environment is set before any app module is imported, so config.Settings
validates against test values rather than whatever is in a local .env, and the
app engine is built pointing at the test database rather than the dev one.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

# Assigned, not setdefault: docker-compose sets ENVIRONMENT=development for the
# container, and the suite must not run under a different environment than the
# one it reports. ENVIRONMENT also selects NullPool in app/db.py, without which
# pooled asyncpg connections leak across pytest's per-test event loops.
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://mealsonwheels:localdev@localhost:5432/highway_food_booking",
)
os.environ.setdefault("JWT_SECRET", "test-secret-value-that-is-long-enough-32chars")
# Unset so tests exercise the no-cache path by default; cache behaviour is
# tested explicitly where it matters.
os.environ.pop("REDIS_URL", None)


def _as_test_database(url: str) -> str:
    """Point a DATABASE_URL at `<dbname>_test`.

    Derived from the ambient URL rather than hardcoded, because the host differs
    between a container run (`postgres:5432`) and a host run (`localhost:5432`)
    and only the database name should change. Deriving it also means the suite
    can never truncate the development database: the name it connects to is
    always the one ending in `_test`.
    """
    parts = urlparse(url)
    name = parts.path.lstrip("/")
    if name.endswith("_test"):
        return url
    return urlunparse(parts._replace(path=f"/{name}_test"))


os.environ["DATABASE_URL"] = _as_test_database(os.environ["DATABASE_URL"])

import psycopg2  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT  # noqa: E402
from sqlalchemy import text  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"

# Every table the schema owns, truncated between tests. Listed explicitly rather
# than discovered, so a new table has to be added here deliberately instead of
# silently leaking rows into the next test.
TABLES = ("ratings", "bookings", "bus_gps_events", "restaurants", "routes", "users")


def _sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _create_test_database_if_missing() -> None:
    """CREATE DATABASE cannot run inside a transaction, hence autocommit."""
    test_url = _sync_url(os.environ["DATABASE_URL"])
    target = urlparse(test_url).path.lstrip("/")
    admin_url = urlunparse(urlparse(test_url)._replace(path="/postgres"))

    conn = psycopg2.connect(admin_url)
    try:
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target,))
            if cur.fetchone() is None:
                # Identifier cannot be parameterised; `target` comes from our own
                # env-derived URL, not from a request.
                cur.execute(f'CREATE DATABASE "{target}"')
    finally:
        conn.close()


def _apply_migrations() -> None:
    conn = psycopg2.connect(_sync_url(os.environ["DATABASE_URL"]))
    try:
        with conn.cursor() as cur:
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                cur.execute(path.read_text())
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="session", autouse=True)
def database() -> None:
    """Ensure the test database exists and carries the current schema.

    Session-scoped: migrations are idempotent but re-running them per test would
    dominate the runtime.
    """
    _create_test_database_if_missing()
    _apply_migrations()


@pytest.fixture(autouse=True)
async def clean_tables(database: None):
    """Truncate before each test so ordering cannot affect an outcome."""
    from app.db import engine

    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
async def seeded(clean_tables) -> None:
    """Apply scripts/seed.py to the freshly truncated test database.

    Opt-in rather than autouse: most tests are clearer starting from nothing,
    and a test that needs seed data should say so. Runs after `clean_tables`,
    which is what makes the idempotency assertion meaningful — the counts it
    checks are against a known-empty start.
    """
    import psycopg2

    from scripts.seed import seed

    conn = psycopg2.connect(_sync_url(os.environ["DATABASE_URL"]))
    try:
        seed(conn)
    finally:
        conn.close()


@pytest.fixture(autouse=True)
def no_overpass(monkeypatch: pytest.MonkeyPatch):
    """Never call the real Overpass API from a test.

    Autouse and default-empty, so a test that forgets to stub it gets local
    results rather than silently sending traffic to a volunteer-run public
    service — which its usage policy prohibits, and which would also make the
    suite depend on someone else's uptime.

    Tests that exercise supplementation override this with their own POIs.
    """

    async def no_pois(latitude: float, longitude: float, radius_km: float):
        return []

    from app.services import overpass, restaurants

    monkeypatch.setattr(overpass, "find_restaurants", no_pois)
    monkeypatch.setattr(restaurants.overpass, "find_restaurants", no_pois)


@pytest.fixture
def db_exec(database: None):
    """Run a statement directly against the test database.

    For arranging state the API cannot set — flipping `is_active`, planting a
    rating aggregate. Synchronous and committed immediately so the app's own
    session sees it.
    """
    import psycopg2

    def run(sql: str) -> None:
        conn = psycopg2.connect(_sync_url(os.environ["DATABASE_URL"]))
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
        finally:
            conn.close()

    return run


@pytest.fixture
def db_scalar(database: None):
    """Read one value directly from the test database.

    For asserting on state the API does not expose — an `osm_id`, a stored
    address — without inferring it from a response shape.
    """
    import psycopg2

    def read(sql: str):
        conn = psycopg2.connect(_sync_url(os.environ["DATABASE_URL"]))
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()

    return read


@pytest.fixture
def db_count(db_scalar):
    """`SELECT count(*)`-shaped read, as an int."""

    def count(sql: str) -> int:
        return int(db_scalar(sql))

    return count


@pytest.fixture
async def client():
    """HTTP client bound to the app without starting a server."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
