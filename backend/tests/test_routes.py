"""Stage 9 tests: seed script and GET /api/routes.

The coordinate assertions are the point of this file. A swapped `ST_X`/`ST_Y`
still returns 200 with plausible-looking floats — it just puts Delhi in the
Indian Ocean and makes every documented search example return nothing
(docs/11_TESTING.md section 6). Nothing else in the suite would catch it.
"""

from __future__ import annotations

import psycopg2

from scripts.seed import seed, to_sync_url
from scripts.seed_data import (
    DEFAULT_RADIUS_KM,
    RESTAURANTS,
    ROUTES,
    SEARCH_ORIGIN_LAT,
    SEARCH_ORIGIN_LON,
    TEST_USER_PHONE,
)

# Fixtures from docs/11_TESTING.md section 6. Duplicated here deliberately: if
# the seed module's values drift from the documented ones, these fail.
DELHI_LAT, DELHI_LON = 28.6139, 77.2090
CHANDIGARH_LAT, CHANDIGARH_LON = 30.7333, 76.7794
MURTHAL_DHABA_LAT, MURTHAL_DHABA_LON = 29.0012, 77.0123


def _connect(database_url: str):
    return psycopg2.connect(to_sync_url(database_url))


# --- GET /api/routes ------------------------------------------------------


async def test_routes_listed_after_seed(client, seeded) -> None:
    response = await client.get("/api/routes")
    assert response.status_code == 200

    body = response.json()
    assert body["total_count"] == 5
    assert len(body["routes"]) == 5
    assert [r["name"] for r in body["routes"]] == [r.name for r in ROUTES]


async def test_routes_requires_no_auth(client, seeded) -> None:
    """Public read: this is the first screen, before login."""
    response = await client.get("/api/routes")
    assert response.status_code == 200


async def test_route_coordinates_are_not_swapped(client, seeded) -> None:
    """Latitude must come from ST_Y and longitude from ST_X, not the reverse.

    Delhi is at 28.6 N, 77.2 E. Swapped, the response claims 77.2 N — which is
    in the Arctic Ocean, and is a perfectly valid-looking float.
    """
    response = await client.get("/api/routes")
    delhi_chandigarh = next(r for r in response.json()["routes"] if r["name"] == "Delhi-Chandigarh")

    assert delhi_chandigarh["origin_lat"] == DELHI_LAT
    assert delhi_chandigarh["origin_lon"] == DELHI_LON
    assert delhi_chandigarh["dest_lat"] == CHANDIGARH_LAT
    assert delhi_chandigarh["dest_lon"] == CHANDIGARH_LON
    # Latitude is bounded at ±90; longitude is not. A swap that happens to stay
    # in range is caught by the equality assertions above, but this states the
    # invariant for every route.
    for route in response.json()["routes"]:
        assert -90 <= route["origin_lat"] <= 90
        assert -90 <= route["dest_lat"] <= 90


async def test_route_response_omits_geometry(client, seeded) -> None:
    """The polyline is internal — corridor search uses it server-side."""
    response = await client.get("/api/routes")
    for route in response.json()["routes"]:
        assert "geometry" not in route
        assert set(route) == {
            "id",
            "name",
            "origin_name",
            "dest_name",
            "origin_lat",
            "origin_lon",
            "dest_lat",
            "dest_lon",
            "distance_km",
        }


async def test_routes_empty_before_seed(client) -> None:
    """An unseeded database is an empty list, not an error."""
    response = await client.get("/api/routes")
    assert response.status_code == 200
    assert response.json() == {"routes": [], "total_count": 0}


async def test_routes_ordered_by_id(client, seeded) -> None:
    """Stable ordering: the client renders this as a dropdown."""
    response = await client.get("/api/routes")
    ids = [r["id"] for r in response.json()["routes"]]
    assert ids == sorted(ids)


# --- Seed script ----------------------------------------------------------


async def test_seed_is_idempotent(clean_tables) -> None:
    """Re-running must update, never duplicate.

    The script is run by hand and will be run twice; if the second run doubled
    the row counts, every documented search example would return each restaurant
    twice.
    """
    import os

    url = os.environ["DATABASE_URL"]

    conn = _connect(url)
    try:
        first = seed(conn)
        second = seed(conn)
    finally:
        conn.close()

    assert first == {"routes": 5, "restaurants": 10, "users": 1}
    assert second == first


async def test_seeded_restaurants_are_within_default_radius(clean_tables) -> None:
    """Every seeded restaurant must be inside 15 km of the demo search point.

    This is the assertion that stops the documented examples from silently
    returning nothing — the failure the canonical coordinate change fixed
    (docs/04_DATABASE_DESIGN.md section 7).
    """
    import os

    conn = _connect(os.environ["DATABASE_URL"])
    try:
        seed(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT name,
                       ST_Distance(
                           location,
                           ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                       ) / 1000.0
                FROM restaurants
                ORDER BY 2
                """,
                (SEARCH_ORIGIN_LON, SEARCH_ORIGIN_LAT),
            )
            distances = cur.fetchall()
    finally:
        conn.close()

    assert len(distances) == len(RESTAURANTS)
    for name, km in distances:
        assert km <= DEFAULT_RADIUS_KM, f"{name} is {km:.1f} km away, outside the default radius"


async def test_murthal_dhaba_matches_documented_fixture(clean_tables) -> None:
    """MURTHAL_DHABA is pinned by docs/11_TESTING.md section 6 at ~2.2 km."""
    import os

    conn = _connect(os.environ["DATABASE_URL"])
    try:
        seed(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ST_Y(location::geometry),
                       ST_X(location::geometry),
                       ST_Distance(
                           location,
                           ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                       ) / 1000.0
                FROM restaurants WHERE name = 'Murthal Dhaba'
                """,
                (SEARCH_ORIGIN_LON, SEARCH_ORIGIN_LAT),
            )
            lat, lon, km = cur.fetchone()
    finally:
        conn.close()

    assert round(lat, 4) == MURTHAL_DHABA_LAT
    assert round(lon, 4) == MURTHAL_DHABA_LON
    assert 2.0 <= km <= 2.5, f"expected ~2.2 km per the fixture, got {km:.2f}"


async def test_seed_creates_test_user(clean_tables) -> None:
    import os

    conn = _connect(os.environ["DATABASE_URL"])
    try:
        seed(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT phone FROM users")
            phones = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()

    assert phones == [TEST_USER_PHONE]


async def test_seed_leaves_route_geometry_null(clean_tables) -> None:
    """Polylines are generated offline by OSRM and are not seeded yet.

    Asserted rather than left implicit: a fabricated LINESTRING would put wrong
    data behind the Stage 16 corridor query, and the point-radius search that
    ships today does not read it.
    """
    import os

    conn = _connect(os.environ["DATABASE_URL"])
    try:
        seed(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM routes WHERE geometry IS NOT NULL")
            with_geometry = cur.fetchone()[0]
    finally:
        conn.close()

    assert with_geometry == 0


async def test_seed_does_not_reset_ratings(clean_tables) -> None:
    """A re-seed must not discard aggregates derived from real ratings."""
    import os

    conn = _connect(os.environ["DATABASE_URL"])
    try:
        seed(conn)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE restaurants SET composite_rating = 4.5, rating_count = 28 "
                "WHERE name = 'Murthal Dhaba'"
            )
        conn.commit()

        seed(conn)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT composite_rating, rating_count FROM restaurants "
                "WHERE name = 'Murthal Dhaba'"
            )
            rating, count = cur.fetchone()
    finally:
        conn.close()

    assert float(rating) == 4.5
    assert count == 28
