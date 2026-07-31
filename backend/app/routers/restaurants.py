"""Restaurant routes: search and detail.

Both are public reads — a traveller browses before logging in. The write
endpoint (`POST /register`) is added in the next commit and requires a JWT.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import DbSession
from app.schemas import RestaurantDetailResponse, RestaurantSearchResponse
from app.services import restaurants as restaurants_service

router = APIRouter(prefix="/api/restaurants", tags=["restaurants"])


@router.get("/search", response_model=RestaurantSearchResponse)
async def search(
    db: DbSession,
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
    radius_km: Annotated[float, Query(gt=0, le=restaurants_service.MAX_RADIUS_KM)] = (
        restaurants_service.DEFAULT_RADIUS_KM
    ),
    route_id: Annotated[int | None, Query()] = None,
) -> RestaurantSearchResponse:
    """Restaurants near a point, nearest first.

    `route_id` is accepted and ignored: the MVP search is point-radius. It is
    recorded on the resulting booking, not used to filter, and it is deliberately
    not part of the cache key (docs/05_API_SPEC.md §6.1). It becomes meaningful
    when corridor search lands in Stage 16.
    """
    results, cached = await restaurants_service.search(db, latitude, longitude, radius_km)
    return RestaurantSearchResponse(
        restaurants=results,
        total_count=len(results),
        cached=cached,
    )


@router.get("/{restaurant_id}", response_model=RestaurantDetailResponse)
async def get_detail(restaurant_id: int, db: DbSession) -> RestaurantDetailResponse:
    """Restaurant detail with its menu.

    The menu here is authoritative — it is the same source booking uses to
    resolve unit prices, so what a client displays is what it will be charged.
    """
    return await restaurants_service.get_detail(db, restaurant_id)
