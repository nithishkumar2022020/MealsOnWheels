"""Stage 10b tests: Overpass supplementation and OSM POI promotion.

Nothing here touches the real Overpass API — `conftest.no_overpass` blocks it by
default and these tests substitute their own payloads. The public instance
prohibits sustained application traffic, and a suite that depends on a volunteer
service's uptime is not a suite you can trust.
"""

from __future__ import annotations

import httpx
import pytest

from app.services import overpass
from app.services.overpass import OverpassPoi, parse_response
from scripts.seed_data import SEARCH_ORIGIN_LAT, SEARCH_ORIGIN_LON

SEARCH = "/api/restaurants/search"
ORIGIN = {"latitude": SEARCH_ORIGIN_LAT, "longitude": SEARCH_ORIGIN_LON}

# A POI near the demo point, inside the default radius.
POI = OverpassPoi(
    osm_id=123456789,
    name="Highway Kitchen OSM",
    lat=29.0300,
    lon=77.0300,
    address="NH-44, Sonipat",
)


@pytest.fixture
def overpass_returns(monkeypatch):
    """Substitute the POIs a search will see."""

    def install(pois):
        async def fake(latitude: float, longitude: float, radius_km: float):
            return list(pois)

        from app.services import restaurants

        monkeypatch.setattr(restaurants.overpass, "find_restaurants", fake)

    return install


async def search(client, **params):
    return await client.get(SEARCH, params={**ORIGIN, **params})


# --- Promotion ------------------------------------------------------------


async def test_osm_poi_is_returned_with_a_real_id(client, seeded, overpass_returns) -> None:
    """The load-bearing test of this commit.

    `bookings.restaurant_id` is a NOT NULL foreign key. A search result with a
    null id could never be booked, which would disable booking exactly on the
    thin corridors supplementation exists to cover.
    """
    overpass_returns([POI])

    body = (await search(client)).json()
    promoted = next(r for r in body["restaurants"] if r["name"] == "Highway Kitchen OSM")

    assert isinstance(promoted["id"], int)
    assert promoted["id"] > 0
    assert promoted["source"] == "osm"


async def test_promoted_poi_is_discoverable_but_not_bookable(
    client, seeded, overpass_returns
) -> None:
    """A promoted row is a real restaurant row, but not an onboarded business.

    It gets an id and a detail page — that is what makes a thin corridor look
    populated instead of empty. It does **not** get a menu.

    This reverses an earlier decision. `menu_for()` used to fall back to a shared
    DEFAULT_MENU so promoted POIs stayed bookable, which was reasonable while
    every menu was equally fictional. Now that menus are owner-managed, a
    fallback would quote a traveller "Paneer Paratha, ₹80" for a dhaba that never
    agreed to either the dish or the price — and the failure would surface at the
    roadside, not here. Listed-but-not-yet-bookable is the honest state.
    """
    overpass_returns([POI])
    body = (await search(client)).json()
    promoted = next(r for r in body["restaurants"] if r["name"] == "Highway Kitchen OSM")

    response = await client.get(f"/api/restaurants/{promoted['id']}")
    assert response.status_code == 200

    detail = response.json()
    # Empty phone: nobody was onboarded, so there is no contact to notify.
    assert detail["phone"] == ""
    assert detail["avg_prep_time_minutes"] == 30

    assert detail["menu"] == []
    assert detail["is_bookable"] is False
    # A specific reason, so the client can say what is wrong rather than
    # "unavailable". Approval is the more fundamental obstacle and is reported
    # first: nobody has reviewed this listing.
    assert detail["unbookable_reason"] == "not_approved"


async def test_promotion_is_idempotent(client, seeded, overpass_returns, db_count) -> None:
    """A repeated search must not duplicate rows — this is a write on a read path."""
    overpass_returns([POI])

    await search(client, radius_km=15)
    after_first = db_count("SELECT count(*) FROM restaurants")

    # Vary the radius so the cache key differs and the search actually re-runs.
    await search(client, radius_km=14)
    after_second = db_count("SELECT count(*) FROM restaurants")

    assert after_first == after_second


async def test_promotion_updates_name_on_conflict(client, seeded, overpass_returns) -> None:
    overpass_returns([POI])
    await search(client, radius_km=15)

    renamed = POI._replace(name="Highway Kitchen Renamed")
    overpass_returns([renamed])
    body = (await search(client, radius_km=14)).json()

    names = [r["name"] for r in body["restaurants"]]
    assert "Highway Kitchen Renamed" in names
    assert "Highway Kitchen OSM" not in names


async def test_promotion_keeps_known_address_when_response_omits_it(
    client, seeded, overpass_returns, db_scalar
) -> None:
    """COALESCE: a later response without addr:* tags must not blank the address."""
    overpass_returns([POI])
    await search(client, radius_km=15)

    overpass_returns([POI._replace(address=None)])
    await search(client, radius_km=14)

    address = db_scalar(f"SELECT address FROM restaurants WHERE osm_id = {POI.osm_id}")
    assert address == "NH-44, Sonipat"


async def test_osm_results_are_ordered_with_local_by_distance(
    client, seeded, overpass_returns
) -> None:
    """One SQL ordering over promoted rows, not a hand-merged Python list."""
    overpass_returns([POI])
    body = (await search(client)).json()

    distances = [r["distance_km"] for r in body["restaurants"]]
    assert distances == sorted(distances)
    assert {"local", "osm"} <= {r["source"] for r in body["restaurants"]}


# --- Degradation ----------------------------------------------------------


def _client_that(*, raises: Exception | None = None, returns: httpx.Response | None = None):
    """A stand-in httpx.AsyncClient whose post() fails or answers as told."""

    class Stub:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            if raises is not None:
                raise raises
            return returns

    return Stub


async def test_search_succeeds_when_overpass_is_down(client, seeded, monkeypatch) -> None:
    """Search returns less, never fails, when the external service is gone.

    Patched at the transport boundary rather than at `find_restaurants`, so the
    module's own error handling is what is under test.
    """
    from app.services import restaurants

    monkeypatch.setattr(restaurants.overpass, "find_restaurants", overpass.find_restaurants)
    monkeypatch.setattr(
        overpass.httpx,
        "AsyncClient",
        _client_that(raises=httpx.ConnectError("overpass unreachable")),
    )

    response = await search(client)
    assert response.status_code == 200

    body = response.json()
    assert body["total_count"] == 10
    assert all(r["source"] == "local" for r in body["restaurants"])


@pytest.mark.parametrize(
    "stub",
    [
        # Timeout, connection failure, a 504 HTML error page parsed as JSON, and
        # an HTTP error status — all normal Overpass failure modes.
        _client_that(raises=httpx.ReadTimeout("too slow")),
        _client_that(raises=httpx.ConnectError("no route to host")),
        _client_that(returns=httpx.Response(200, text="<html>gateway timeout</html>")),
        _client_that(returns=httpx.Response(504, request=httpx.Request("POST", "http://overpass"))),
    ],
    ids=["timeout", "connect_error", "html_body", "server_error"],
)
async def test_overpass_client_returns_empty_on_failure(monkeypatch, stub) -> None:
    monkeypatch.setattr(overpass.httpx, "AsyncClient", stub)
    assert await overpass.find_restaurants(29.02, 77.02, 15) == []


# --- Response parsing -----------------------------------------------------


def test_parse_extracts_pois() -> None:
    payload = {
        "elements": [
            {
                "id": 1,
                "lat": 29.0,
                "lon": 77.0,
                "tags": {
                    "name": "Dhaba One",
                    "addr:housenumber": "12",
                    "addr:street": "NH-44",
                    "addr:city": "Sonipat",
                },
            }
        ]
    }
    (poi,) = parse_response(payload)

    assert poi.osm_id == 1
    assert poi.name == "Dhaba One"
    assert poi.address == "12, NH-44, Sonipat"


def test_parse_drops_unnamed_pois() -> None:
    """ "Unnamed restaurant, 3 km away" is not a choice a traveller can make."""
    payload = {
        "elements": [
            {"id": 1, "lat": 29.0, "lon": 77.0, "tags": {}},
            {"id": 2, "lat": 29.0, "lon": 77.0, "tags": {"name": "  "}},
            {"id": 3, "lat": 29.0, "lon": 77.0, "tags": {"name": "Real Dhaba"}},
        ]
    }
    assert [p.name for p in parse_response(payload)] == ["Real Dhaba"]


def test_parse_drops_pois_without_coordinates() -> None:
    payload = {"elements": [{"id": 1, "tags": {"name": "No Location"}}]}
    assert parse_response(payload) == []


def test_parse_handles_empty_payload() -> None:
    assert parse_response({}) == []
    assert parse_response({"elements": []}) == []


def test_parse_truncates_overlong_names() -> None:
    """restaurants.name is VARCHAR(200); OSM does not enforce a length."""
    payload = {"elements": [{"id": 1, "lat": 29.0, "lon": 77.0, "tags": {"name": "x" * 500}}]}
    (poi,) = parse_response(payload)
    assert len(poi.name) == 200


def test_parse_omits_address_when_no_tags_present() -> None:
    payload = {"elements": [{"id": 1, "lat": 29.0, "lon": 77.0, "tags": {"name": "Bare"}}]}
    (poi,) = parse_response(payload)
    assert poi.address is None
