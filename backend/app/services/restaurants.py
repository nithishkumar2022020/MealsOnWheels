"""Restaurant search and detail.

The radius query follows docs/04_DATABASE_DESIGN.md section 5.1 exactly:
`ST_DWithin` against the `GEOGRAPHY` column so the GiST index on
`idx_restaurants_location` is usable, and `location` is *not* re-cast — casting a
column inline makes the expression non-indexable and turns the search into a
sequential scan.

`ST_Distance` on two geography values returns metres along the spheroid, which is
what the API reports as `distance_km`.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from geoalchemy2 import Geography, Geometry
from geoalchemy2.elements import WKTElement
from sqlalchemy import cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import cache
from app.errors import not_found
from app.logging_config import cache_hit_ctx
from app.models import Restaurant, User
from app.schemas import (
    MenuItemResponse,
    RestaurantDetailResponse,
    RestaurantRegisterRequest,
    RestaurantSearchResult,
)
from app.services import overpass
from app.services.bookability import NO_MENU, unbookable_reason
from app.services.hours import list_hours
from app.services.menus import list_items as list_menu_items
from app.services.overpass import OverpassPoi

logger = logging.getLogger(__name__)

# Six hours, not seven days: a self-registered restaurant has to become
# discoverable within a usable window, and the only documented invalidation is a
# manual flush (docs/02_TECHNICAL_SPEC.md section 5.5).
SEARCH_CACHE_TTL_SECONDS = 6 * 3600

DEFAULT_RADIUS_KM = 15.0
MAX_RADIUS_KM = 50.0

# Coordinates are rounded to ~11 m before they enter the cache key. Raw floats
# would give almost every request its own key — a GPS fix jitters in the seventh
# decimal place — and the cache would never be hit.
_KEY_PRECISION = 4


def search_cache_key(latitude: float, longitude: float, radius_km: float) -> str:
    """`restaurants:{lat}:{lon}:{radius}` per docs/02_TECHNICAL_SPEC.md §5.5.

    `route_id` is deliberately absent: the MVP search is point-radius and never
    reads it, so including it would fragment the cache across routes that return
    identical results.
    """
    lat = round(latitude, _KEY_PRECISION)
    lon = round(longitude, _KEY_PRECISION)
    return f"restaurants:{lat}:{lon}:{radius_km}"


def _to_result(row: object) -> RestaurantSearchResult:
    mapping = dict(row)  # type: ignore[call-overload]
    rating: Decimal | None = mapping["composite_rating"]
    return RestaurantSearchResult(
        id=mapping["id"],
        name=mapping["name"],
        lat=mapping["lat"],
        lon=mapping["lon"],
        # Metres from PostGIS; the API reports kilometres to 1 decimal.
        distance_km=round(mapping["distance_m"] / 1000.0, 1),
        # 0 means unrated. Reported as null so a client does not render a new
        # restaurant as zero stars (docs/05_API_SPEC.md §6.1).
        composite_rating=rating if mapping["rating_count"] > 0 else None,
        avg_prep_time_minutes=mapping["avg_prep_time_minutes"],
        address=mapping["address"],
        source="osm" if mapping["osm_id"] is not None else "local",
    )


async def search_local(
    db: AsyncSession,
    latitude: float,
    longitude: float,
    radius_km: float,
) -> list[RestaurantSearchResult]:
    """Active restaurants within `radius_km`, nearest first.

    `is_active = false` rows are excluded, which is what makes self-registration
    safe: an unreviewed submission is never served.
    """
    point = cast(func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326), Geography)
    distance = func.ST_Distance(Restaurant.location, point)

    # Cast for the accessors only. Restaurant.location itself is never re-cast
    # in the WHERE clause — that would make the expression non-indexable and
    # turn this into a sequential scan.
    location_geom = cast(Restaurant.location, Geometry)

    stmt = (
        select(
            Restaurant.id,
            Restaurant.name,
            Restaurant.address,
            Restaurant.composite_rating,
            Restaurant.rating_count,
            Restaurant.avg_prep_time_minutes,
            Restaurant.osm_id,
            func.ST_Y(location_geom).label("lat"),
            func.ST_X(location_geom).label("lon"),
            distance.label("distance_m"),
        )
        .where(
            Restaurant.is_active.is_(True),
            func.ST_DWithin(Restaurant.location, point, radius_km * 1000.0),
        )
        .order_by(distance)
    )

    result = await db.execute(stmt)
    return [_to_result(row) for row in result.mappings()]


async def promote_osm_pois(
    db: AsyncSession,
    pois: Sequence[OverpassPoi],
) -> None:
    """Upsert Overpass POIs into `restaurants`, keyed on `osm_id`.

    This is the only write on the search read path, and it is what makes OSM
    results bookable: `bookings.restaurant_id` is a NOT NULL foreign key, so a
    result returned with `id: null` could never be booked
    (docs/04_DATABASE_DESIGN.md section 3.2.1). Returning null ids was rejected
    because Overpass supplementation exists precisely to cover corridors where
    seeded data is thin — it would disable booking exactly where it is needed.

    Idempotent, so a repeated search does not duplicate rows.

    `phone` is empty: nobody was onboarded, so there is no contact. The booking
    still succeeds and the notification stub logs that it had nobody to notify.
    """
    if not pois:
        return

    for poi in pois:
        await db.execute(
            text(
                """
                INSERT INTO restaurants
                    (name, phone, address, location, osm_id, avg_prep_time_minutes)
                VALUES
                    (:name, '', :address,
                     ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                     :osm_id, 30)
                -- The predicate is required, not decoration: idx_restaurants_osm_id
                -- is a PARTIAL unique index (WHERE osm_id IS NOT NULL), and
                -- Postgres will not infer a partial index unless the conflict
                -- target repeats its predicate. Without it this raises
                -- "no unique or exclusion constraint matching the ON CONFLICT
                -- specification" — see docs/04_DATABASE_DESIGN.md section 3.2.1.
                ON CONFLICT (osm_id) WHERE osm_id IS NOT NULL DO UPDATE SET
                    name       = EXCLUDED.name,
                    -- COALESCE keeps a previously known address when this
                    -- response happens to omit the addr:* tags.
                    address    = COALESCE(EXCLUDED.address, restaurants.address),
                    updated_at = now()
                """
            ),
            {
                "name": poi.name,
                "address": poi.address,
                "lat": poi.lat,
                "lon": poi.lon,
                "osm_id": poi.osm_id,
            },
        )

    await db.commit()


async def search(
    db: AsyncSession,
    latitude: float,
    longitude: float,
    radius_km: float,
) -> tuple[list[RestaurantSearchResult], bool]:
    """Cached search, supplemented by Overpass. Returns `(results, was_cached)`.

    A cache failure is a miss, never an error: `app/cache.py` swallows Redis
    problems, so the worst case is that the database is queried.

    Overpass POIs are promoted into `restaurants` and then the local query is
    re-run, rather than merging two lists in Python. One SQL ordering is easier
    to trust than a hand-rolled merge, and it means promoted rows are
    deduplicated by the `osm_id` unique index rather than by application logic.
    """
    key = search_cache_key(latitude, longitude, radius_km)

    cached = await cache.get_json(key)
    if cached is not None:
        cache_hit_ctx.set(True)
        return [RestaurantSearchResult.model_validate(r) for r in cached], True

    cache_hit_ctx.set(False)
    results = await search_local(db, latitude, longitude, radius_km)

    # Returns [] if Overpass is down, slow, or malformed — search then answers
    # with local rows alone rather than failing.
    pois = await overpass.find_restaurants(latitude, longitude, radius_km)
    if pois:
        await promote_osm_pois(db, pois)
        results = await search_local(db, latitude, longitude, radius_km)

    await cache.set_json(
        key,
        [r.model_dump(mode="json") for r in results],
        ttl_seconds=SEARCH_CACHE_TTL_SECONDS,
    )
    return results, False


async def register(
    db: AsyncSession,
    payload: RestaurantRegisterRequest,
    submitted_by: User,
) -> Restaurant:
    """Create a restaurant, inactive, pending operator review.

    Two controls, both load-bearing (docs/05_API_SPEC.md section 6.3):

    **A JWT is required.** This is a public-facing write that inserts geospatial
    rows. Left open it is a search-poisoning vector, and a spammed row would then
    persist in the search cache for its full TTL. Requiring a token gives every
    submission an accountable origin.

    **`is_active` is false and is not settable by the caller.** An unreviewed row
    is never served — search filters on `is_active` and detail 404s. There is no
    field on the request schema for it, and `extra="forbid"` refuses one that is
    sent anyway.

    Activation is manual until the approval UI lands in Phase 1: an operator
    flips the flag in the database.
    """
    restaurant = Restaurant(
        name=payload.name,
        phone=payload.phone,
        email=str(payload.email) if payload.email else None,
        address=payload.address,
        location=WKTElement(f"POINT({payload.longitude} {payload.latitude})", srid=4326),
        avg_prep_time_minutes=payload.avg_prep_time_minutes,
        is_active=False,
    )
    db.add(restaurant)
    await db.commit()
    await db.refresh(restaurant)

    logger.info(
        "restaurant registered, pending activation",
        extra={
            "extra_fields": {
                "event": "restaurant_registered",
                "restaurant_id": restaurant.id,
                "submitted_by_user_id": submitted_by.id,
            }
        },
    )
    return restaurant


async def get_detail(db: AsyncSession, restaurant_id: int) -> RestaurantDetailResponse:
    """Restaurant detail with its authoritative menu and bookability.

    Inactive restaurants are 404, not 200: a pending self-registration must not
    be readable by guessing an id when search deliberately hides it.

    Unavailable items are included. The client greys them out rather than hiding
    them — a traveller who cannot find a dish they know assumes the app is
    broken, whereas "sold out" is information.

    **A restaurant with no menu is listed but not bookable.** Menus used to fall
    back to a shared default, which kept OSM-promoted POIs bookable while every
    menu was equally fictional. Now that menus are real, inventing one would show
    a traveller a price no restaurant ever agreed to, and the failure would land
    at the roadside rather than here. `is_bookable` carries that distinction
    instead.
    """
    restaurant = await db.get(Restaurant, restaurant_id)
    if restaurant is None or not restaurant.is_active:
        raise not_found("Restaurant not found")

    items = await list_menu_items(db, restaurant_id)
    hours = await list_hours(db, restaurant_id)

    reason = unbookable_reason(restaurant, hours, datetime.now(UTC))
    if reason is None and not any(i.is_available for i in items):
        # Approved, open, and staffed — but nothing on the menu can be cooked.
        reason = NO_MENU

    return RestaurantDetailResponse(
        id=restaurant.id,
        name=restaurant.name,
        phone=restaurant.phone,
        address=restaurant.address,
        composite_rating=restaurant.composite_rating if restaurant.rating_count > 0 else None,
        rating_count=restaurant.rating_count,
        avg_prep_time_minutes=restaurant.avg_prep_time_minutes,
        menu=[
            MenuItemResponse(
                name=i.name,
                price=i.price,
                category=i.category,
                is_available=i.is_available,
            )
            for i in items
        ],
        is_bookable=reason is None,
        unbookable_reason=reason,
        supported_booking_types=list(restaurant.supported_booking_types or ()),
    )
