"""Stage 10 tests: restaurant search, detail, and the menu price boundary.

The search assertions that matter are the ones nothing else would catch: an
inactive restaurant staying out of results, an unrated one reporting `null`
rather than `0`, and distances that are actually in kilometres.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from scripts.seed_data import RESTAURANTS, SEARCH_ORIGIN_LAT, SEARCH_ORIGIN_LON
from scripts.seed_menus import DEFAULT_MENU, MENUS_BY_NAME, menu_for, price_of

SEARCH = "/api/restaurants/search"
ORIGIN = {"latitude": SEARCH_ORIGIN_LAT, "longitude": SEARCH_ORIGIN_LON}


async def search(client, **params):
    return await client.get(SEARCH, params={**ORIGIN, **params})


async def find(client, name: str = "Murthal Dhaba"):
    """A search result by name.

    Looked up rather than indexed: Murthal Dhaba is the coordinate the testing
    fixtures pin, but it is not the *nearest* seeded restaurant, and asserting
    on `restaurants[0]` would silently re-target whenever the seed changes.
    """
    body = (await search(client)).json()
    return next(r for r in body["restaurants"] if r["name"] == name)


# --- Search ---------------------------------------------------------------


async def test_search_returns_seeded_corridor_restaurants(client, seeded) -> None:
    response = await search(client)
    assert response.status_code == 200

    body = response.json()
    assert body["total_count"] == len(RESTAURANTS)
    assert body["cached"] is False
    assert all(r["source"] == "local" for r in body["restaurants"])


async def test_search_orders_by_distance_ascending(client, seeded) -> None:
    body = (await search(client)).json()
    distances = [r["distance_km"] for r in body["restaurants"]]
    assert distances == sorted(distances)


async def test_search_distance_is_kilometres_not_metres(client, seeded) -> None:
    """Murthal Dhaba is ~2.2 km from the demo point, per the testing fixture.

    A metres/kilometres mix-up still returns 200 with a plausible number, and
    would then be rendered to travellers as "2200 km away".
    """
    murthal = await find(client)
    assert 2.0 <= murthal["distance_km"] <= 2.5


async def test_search_respects_radius(client, seeded) -> None:
    tight = (await search(client, radius_km=1)).json()
    wide = (await search(client, radius_km=15)).json()
    assert tight["total_count"] < wide["total_count"]


async def test_search_out_of_range_returns_empty(client, seeded) -> None:
    """OUT_OF_RANGE from docs/11_TESTING.md §6 — empty, not an error."""
    response = await client.get(SEARCH, params={"latitude": 20.0, "longitude": 75.0})
    assert response.status_code == 200
    assert response.json() == {"restaurants": [], "total_count": 0, "cached": False}


async def test_search_excludes_inactive_restaurants(client, seeded, db_exec) -> None:
    """Inactive rows are invisible, which is what makes self-registration safe."""
    before = (await search(client)).json()["total_count"]

    db_exec("UPDATE restaurants SET is_active = false WHERE name = 'Murthal Dhaba'")

    body = (await search(client)).json()
    assert body["total_count"] == before - 1
    assert all(r["name"] != "Murthal Dhaba" for r in body["restaurants"])


async def test_search_reports_null_rating_for_unrated(client, seeded) -> None:
    """`null`, never `0` — an unrated restaurant is not a zero-star one."""
    body = (await search(client)).json()
    assert all(r["composite_rating"] is None for r in body["restaurants"])


async def test_search_reports_rating_once_rated(client, seeded, db_exec) -> None:
    db_exec(
        "UPDATE restaurants SET composite_rating = 4.5, rating_count = 28 "
        "WHERE name = 'Murthal Dhaba'"
    )

    body = (await search(client)).json()
    murthal = next(r for r in body["restaurants"] if r["name"] == "Murthal Dhaba")
    assert Decimal(str(murthal["composite_rating"])) == Decimal("4.50")


async def test_search_rejects_out_of_range_coordinates(client) -> None:
    response = await client.get(SEARCH, params={"latitude": 91.0, "longitude": 77.0})
    assert response.status_code == 422


async def test_search_rejects_radius_above_maximum(client) -> None:
    response = await search(client, radius_km=500)
    assert response.status_code == 422


async def test_search_accepts_and_ignores_route_id(client, seeded) -> None:
    """`route_id` is booking context, not a filter, until Stage 16."""
    with_route = (await search(client, route_id=1)).json()
    without = (await search(client)).json()
    assert with_route["total_count"] == without["total_count"]


# --- Cache ----------------------------------------------------------------


def test_cache_key_omits_route_id() -> None:
    """Including it would fragment the cache across routes returning the same rows."""
    from app.services.restaurants import search_cache_key

    key = search_cache_key(29.02, 77.02, 15.0)
    assert key == "restaurants:29.02:77.02:15.0"


def test_cache_key_rounds_coordinates() -> None:
    """A GPS fix jitters in the seventh decimal; unrounded, nothing ever hits."""
    from app.services.restaurants import search_cache_key

    assert search_cache_key(29.020001, 77.020001, 15.0) == search_cache_key(29.02, 77.02, 15.0)


async def test_search_reports_cached_on_second_call(client, seeded, monkeypatch) -> None:
    """Tests run without Redis, so the store is faked to exercise the path."""
    store: dict[str, object] = {}

    async def fake_get(key: str):
        return store.get(key)

    async def fake_set(key: str, value: object, ttl_seconds: int) -> None:
        store[key] = value

    from app.services import restaurants as service

    monkeypatch.setattr(service.cache, "get_json", fake_get)
    monkeypatch.setattr(service.cache, "set_json", fake_set)

    first = (await search(client)).json()
    second = (await search(client)).json()

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["restaurants"] == first["restaurants"]


# --- Detail ---------------------------------------------------------------


async def test_detail_returns_menu(client, seeded) -> None:
    listing = await find(client)

    response = await client.get(f"/api/restaurants/{listing['id']}")
    assert response.status_code == 200

    body = response.json()
    assert body["name"] == "Murthal Dhaba"
    assert body["menu"]
    # is_available joined the payload when menus became owner-managed: a
    # sold-out dish is returned and greyed out rather than hidden, because a
    # traveller who cannot find a dish they know assumes the app is broken.
    assert {"name", "price", "category", "is_available"} == set(body["menu"][0])


async def test_detail_menu_matches_authoritative_source(client, seeded) -> None:
    """What detail displays must be exactly what booking will charge."""
    listing = await find(client)
    body = (await client.get(f"/api/restaurants/{listing['id']}")).json()

    expected = menu_for("Murthal Dhaba")
    assert len(body["menu"]) == len(expected)
    for served, source in zip(body["menu"], expected, strict=True):
        assert served["name"] == source.name
        assert Decimal(str(served["price"])) == source.price


async def test_detail_unknown_id_is_404(client, seeded) -> None:
    response = await client.get("/api/restaurants/999999")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


async def test_detail_inactive_is_404(client, seeded, db_exec) -> None:
    """Not readable by guessing an id when search deliberately hides it."""
    listing = await find(client)
    db_exec(f"UPDATE restaurants SET is_active = false WHERE id = {listing['id']}")

    response = await client.get(f"/api/restaurants/{listing['id']}")
    assert response.status_code == 404


async def test_detail_reports_null_rating_for_unrated(client, seeded) -> None:
    listing = await find(client)
    body = (await client.get(f"/api/restaurants/{listing['id']}")).json()
    assert body["composite_rating"] is None
    assert body["rating_count"] == 0


# --- Menu -----------------------------------------------------------------


def test_every_seeded_restaurant_has_a_menu() -> None:
    for restaurant in RESTAURANTS:
        assert restaurant.name in MENUS_BY_NAME, f"{restaurant.name} has no menu"


def test_unknown_restaurant_falls_back_to_default_menu() -> None:
    """An empty menu would make OSM-promoted POIs unbookable."""
    assert menu_for("Some Overpass POI") == DEFAULT_MENU


def test_prices_are_decimal_not_float() -> None:
    """0.1 + 0.2 != 0.3 in binary floating point, and these are summed into money."""
    for items in (*MENUS_BY_NAME.values(), DEFAULT_MENU):
        for item in items:
            assert isinstance(item.price, Decimal)


def test_price_lookup_resolves_and_rejects() -> None:
    assert price_of("Murthal Dhaba", "Paneer Paratha") == Decimal("80.00")
    # None, not zero: Stage 11 turns this into a 400 rather than a free dish.
    assert price_of("Murthal Dhaba", "Caviar") is None


@pytest.mark.parametrize("items", [*MENUS_BY_NAME.values(), DEFAULT_MENU])
def test_menu_item_names_are_unique(items) -> None:
    """Booking resolves prices by name; a duplicate makes that ambiguous."""
    names = [i.name for i in items]
    assert len(names) == len(set(names))
