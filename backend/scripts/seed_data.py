"""Seed values, separated from the script that applies them.

Kept in its own module so tests can assert against the same constants the seed
writes. A test that re-types a coordinate is testing its own typo, not the seed:
docs/11_TESTING.md section 6 exists because a swapped lat/lon puts Delhi in the
Indian Ocean and every documented search example silently returns nothing.
"""

from __future__ import annotations

from typing import NamedTuple

# Canonical demo search point — NH-44 just south of Murthal. Every seeded
# restaurant must fall inside the default 15 km radius of it
# (docs/05_API_SPEC.md section 6.1, docs/11_TESTING.md section 6).
SEARCH_ORIGIN_LAT = 29.02
SEARCH_ORIGIN_LON = 77.02
DEFAULT_RADIUS_KM = 15.0

TEST_USER_PHONE = "+919876543210"
TEST_USER_NAME = "Priya Sharma"


class RouteSeed(NamedTuple):
    name: str
    origin_name: str
    dest_name: str
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    distance_km: int


class RestaurantSeed(NamedTuple):
    name: str
    phone: str
    address: str
    lat: float
    lon: float
    avg_prep_time_minutes: int


# The five MVP routes (docs/04_DATABASE_DESIGN.md section 7). Delhi and
# Chandigarh coordinates match the DELHI_CENTER / CHANDIGARH_CENTER fixtures.
ROUTES: tuple[RouteSeed, ...] = (
    RouteSeed("Delhi-Chandigarh", "Delhi", "Chandigarh", 28.6139, 77.2090, 30.7333, 76.7794, 245),
    RouteSeed("Mumbai-Pune", "Mumbai", "Pune", 19.0760, 72.8777, 18.5204, 73.8567, 148),
    RouteSeed(
        "Bangalore-Hyderabad",
        "Bangalore",
        "Hyderabad",
        12.9716,
        77.5946,
        17.3850,
        78.4867,
        575,
    ),
    RouteSeed("Chennai-Bangalore", "Chennai", "Bangalore", 13.0827, 80.2707, 12.9716, 77.5946, 350),
    RouteSeed("Jaipur-Delhi", "Jaipur", "Delhi", 26.9124, 75.7873, 28.6139, 77.2090, 281),
)

# Ten restaurants along the Delhi–Chandigarh corridor, all within 15 km of the
# canonical search point. Murthal Dhaba's coordinates are fixed by the
# MURTHAL_DHABA fixture in docs/11_TESTING.md section 6 — do not move it.
RESTAURANTS: tuple[RestaurantSeed, ...] = (
    RestaurantSeed(
        "Murthal Dhaba", "+919811100001", "NH-44, Murthal, Haryana", 29.0012, 77.0123, 25
    ),
    RestaurantSeed(
        "Amrik Sukhdev", "+919811100002", "NH-44, Murthal, Sonipat, Haryana", 29.0089, 77.0201, 30
    ),
    RestaurantSeed(
        "Gulshan Dhaba", "+919811100003", "NH-44, Murthal, Haryana", 29.0154, 77.0098, 20
    ),
    RestaurantSeed(
        "Highway Kitchen", "+919811100004", "NH-44, Bahalgarh, Haryana", 29.0512, 77.0455, 35
    ),
    RestaurantSeed(
        "Sukhdev Vaishno Dhaba", "+919811100005", "NH-44, Sonipat, Haryana", 28.9834, 77.0312, 25
    ),
    RestaurantSeed(
        "Pehalwan Dhaba", "+919811100006", "NH-44, Murthal, Haryana", 29.0301, 76.9987, 30
    ),
    RestaurantSeed(
        "Garam Dharam Dhaba", "+919811100007", "NH-44, Murthal, Haryana", 29.0445, 77.0176, 40
    ),
    RestaurantSeed(
        "Jhilmil Dhaba", "+919811100008", "NH-44, Kundli, Haryana", 28.9612, 77.0489, 20
    ),
    RestaurantSeed(
        "Z Blue Jays", "+919811100009", "NH-44, Bahalgarh, Sonipat", 29.0678, 77.0021, 30
    ),
    RestaurantSeed(
        "Haveli Restaurant", "+919811100010", "NH-44, Murthal, Haryana", 29.0223, 77.0634, 45
    ),
)
