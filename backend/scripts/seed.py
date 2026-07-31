"""Seed routes, corridor restaurants, and the test user.

Idempotent: re-running updates the existing rows rather than inserting
duplicates. Matching is by natural key — route `name`, restaurant `name`, user
`phone` — because ids are serial and would differ between a freshly created
database and one seeded before.

Uses psycopg2 (sync), matching scripts/migrate.py: this is a one-shot script and
there is nothing for an event loop to overlap with.

Route `geometry` is left NULL. Polylines are generated offline by OSRM at seed
time (docs/03_SYSTEM_ARCHITECTURE.md section 3) and no OSRM service exists in
this compose file yet, so writing a fabricated LINESTRING would put wrong data
behind the Stage 16 corridor query. NULL is the honest value; the column is
nullable for exactly this reason.

Usage:
    python scripts/seed.py
"""

from __future__ import annotations

import os
import sys

import psycopg2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.seed_data import (  # noqa: E402
    RESTAURANTS,
    ROUTES,
    TEST_USER_NAME,
    TEST_USER_PHONE,
)


def to_sync_url(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


# ST_MakePoint takes (longitude, latitude) — the opposite order to how
# coordinates are written. Getting it backwards puts Delhi in the Indian Ocean,
# which is why tests/test_routes.py asserts the round-trip.
_POINT = "ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography"

# Matched by SELECT rather than ON CONFLICT: neither routes.name nor
# restaurants.name is UNIQUE, and neither should be. Two real dhabas can share a
# name, and OSM-derived rows are deduplicated on osm_id (docs/04_DATABASE_DESIGN
# section 3.2.1). Adding a unique index purely to make a seed script shorter
# would constrain production data to suit a dev convenience.
#
# The seed is single-threaded and run by hand, so the read-then-write is not
# racing anything.

ROUTE_INSERT = f"""
INSERT INTO routes (name, origin_name, dest_name, origin_point, dest_point, distance_km)
VALUES (%s, %s, %s, {_POINT}, {_POINT}, %s)
"""

ROUTE_UPDATE = f"""
UPDATE routes SET
    origin_name  = %s,
    dest_name    = %s,
    origin_point = {_POINT},
    dest_point   = {_POINT},
    distance_km  = %s,
    updated_at   = now()
WHERE id = %s
"""

RESTAURANT_INSERT = f"""
INSERT INTO restaurants (name, phone, address, location, avg_prep_time_minutes, is_active)
VALUES (%s, %s, %s, {_POINT}, %s, true)
"""

# composite_rating and rating_count are deliberately not touched: they are
# derived from the ratings table, so resetting them on a re-seed would discard
# real ratings.
RESTAURANT_UPDATE = f"""
UPDATE restaurants SET
    phone    = %s,
    address  = %s,
    location = {_POINT},
    avg_prep_time_minutes = %s,
    is_active = true,
    updated_at = now()
WHERE id = %s
"""

# users.phone IS unique, so this one conflict target is real.
USER_UPSERT = """
INSERT INTO users (phone, name)
VALUES (%s, %s)
ON CONFLICT (phone) DO UPDATE SET name = EXCLUDED.name, updated_at = now()
"""


def seed(conn: psycopg2.extensions.connection) -> dict[str, int]:
    with conn.cursor() as cur:
        for r in ROUTES:
            cur.execute("SELECT id FROM routes WHERE name = %s", (r.name,))
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    ROUTE_INSERT,
                    (
                        r.name,
                        r.origin_name,
                        r.dest_name,
                        r.origin_lon,
                        r.origin_lat,
                        r.dest_lon,
                        r.dest_lat,
                        r.distance_km,
                    ),
                )
            else:
                cur.execute(
                    ROUTE_UPDATE,
                    (
                        r.origin_name,
                        r.dest_name,
                        r.origin_lon,
                        r.origin_lat,
                        r.dest_lon,
                        r.dest_lat,
                        r.distance_km,
                        row[0],
                    ),
                )

        for x in RESTAURANTS:
            # Scoped to osm_id IS NULL so a re-seed can never overwrite a POI
            # promoted from OpenStreetMap that happens to share a name.
            cur.execute(
                "SELECT id FROM restaurants WHERE name = %s AND osm_id IS NULL",
                (x.name,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    RESTAURANT_INSERT,
                    (x.name, x.phone, x.address, x.lon, x.lat, x.avg_prep_time_minutes),
                )
            else:
                cur.execute(
                    RESTAURANT_UPDATE,
                    (x.phone, x.address, x.lon, x.lat, x.avg_prep_time_minutes, row[0]),
                )

        cur.execute(USER_UPSERT, (TEST_USER_PHONE, TEST_USER_NAME))

        cur.execute("SELECT count(*) FROM routes")
        routes = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM restaurants")
        restaurants = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM users")
        users = cur.fetchone()[0]

    conn.commit()
    return {"routes": routes, "restaurants": restaurants, "users": users}


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 1

    conn = psycopg2.connect(to_sync_url(database_url))
    try:
        counts = seed(conn)
    except Exception as exc:
        conn.rollback()
        print(f"seed failed, rolled back: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print(
        f"seeded: {counts['routes']} routes, "
        f"{counts['restaurants']} restaurants, {counts['users']} users"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
