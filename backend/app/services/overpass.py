"""Overpass API client.

Supplements thin local data with OpenStreetMap POIs. Three constraints shape
this module, all from docs/02_TECHNICAL_SPEC.md section 6.2:

**It must never fail a search.** Every error path returns `[]` and logs. Overpass
is a public volunteer-run service; treating its availability as load-bearing
would make our search only as reliable as someone else's donated hardware.

**One request per second, globally.** Not per worker, not per request — a module
level lock serialises callers. The public instance prohibits sustained
application traffic regardless of throttling, so this keeps development
compliant and a public launch still requires self-hosting (Stage 19).

**Ten second timeout.** Longer than that and the traveller is staring at a
spinner while we wait on an optional enhancement.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, NamedTuple

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10.0
MIN_INTERVAL_SECONDS = 1.0

# Overpass caps its own runtime with [timeout:...]; ours is the transport-level
# bound. `out body` returns tags, which is where the name lives.
_QUERY_TEMPLATE = """
[out:json][timeout:{timeout}];
node["amenity"="restaurant"](around:{radius_m},{lat},{lon});
out body {limit};
"""

# Enough to supplement a thin corridor without turning one search into a
# hundred upserts on the write path.
MAX_RESULTS = 30


class OverpassPoi(NamedTuple):
    osm_id: int
    name: str
    lat: float
    lon: float
    address: str | None


_throttle_lock = asyncio.Lock()
_last_request_at: float = 0.0


async def _throttle() -> None:
    """Serialise callers to at most one request per second, process-wide."""
    global _last_request_at
    async with _throttle_lock:
        elapsed = time.monotonic() - _last_request_at
        if elapsed < MIN_INTERVAL_SECONDS:
            await asyncio.sleep(MIN_INTERVAL_SECONDS - elapsed)
        _last_request_at = time.monotonic()


def _address_from_tags(tags: dict[str, Any]) -> str | None:
    """Assemble a street address from the addr:* tags, if present.

    OSM addresses are optional and frequently partial; a POI with only a name is
    normal and still useful.
    """
    parts = [
        tags.get("addr:housenumber"),
        tags.get("addr:street"),
        tags.get("addr:city"),
        tags.get("addr:state"),
    ]
    joined = ", ".join(p for p in parts if p)
    return joined or None


def parse_response(payload: dict[str, Any]) -> list[OverpassPoi]:
    """Extract usable POIs, discarding anything unbookable.

    A POI with no name cannot be shown to a traveller — "Unnamed restaurant,
    3 km away" is not a choice anyone can make — so it is dropped rather than
    given a placeholder.
    """
    pois: list[OverpassPoi] = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        name = (tags.get("name") or "").strip()
        osm_id = element.get("id")
        lat = element.get("lat")
        lon = element.get("lon")

        if not name or osm_id is None or lat is None or lon is None:
            continue

        pois.append(
            OverpassPoi(
                osm_id=int(osm_id),
                name=name[:200],  # restaurants.name is VARCHAR(200)
                lat=float(lat),
                lon=float(lon),
                address=_address_from_tags(tags),
            )
        )
    return pois


async def find_restaurants(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> list[OverpassPoi]:
    """Nearby OSM restaurants. Returns `[]` on any failure — never raises.

    The broad `except Exception` is deliberate. This is an optional enhancement
    on a read path, and the set of ways a third-party HTTP call can fail is
    open-ended: DNS, TLS, a 504 HTML error page parsed as JSON, a malformed
    payload. Any of them must degrade the result, not the request.
    """
    settings = get_settings()
    query = _QUERY_TEMPLATE.format(
        timeout=int(TIMEOUT_SECONDS),
        radius_m=int(radius_km * 1000),
        lat=latitude,
        lon=longitude,
        limit=MAX_RESULTS,
    )

    try:
        await _throttle()
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as http:
            response = await http.post(
                settings.OVERPASS_URL,
                content=query.encode("utf-8"),
                headers={
                    # Overpass blocks generic and placeholder user agents, and
                    # asks that clients identify themselves with a contact.
                    "User-Agent": settings.NOMINATIM_USER_AGENT,
                    "Content-Type": "text/plain; charset=utf-8",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning(
            "overpass unavailable, returning local results only",
            extra={"extra_fields": {"event": "overpass_failed", "error": str(exc)[:200]}},
        )
        return []

    pois = parse_response(payload)
    logger.info(
        "overpass supplement",
        extra={"extra_fields": {"event": "overpass_ok", "poi_count": len(pois)}},
    )
    return pois
