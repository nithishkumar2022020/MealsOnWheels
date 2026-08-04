"""Restaurant routes: search and detail.

Both are public reads — a traveller browses before logging in. The write
endpoint (`POST /register`) is added in the next commit and requires a JWT.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.deps import CurrentUser, DbSession
from app.schemas import (
    RestaurantDetailResponse,
    RestaurantRegisterRequest,
    RestaurantRegisterResponse,
    RestaurantSearchResponse,
)
from app.services import rate_limit
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


@router.post(
    "/register",
    response_model=RestaurantRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    payload: RestaurantRegisterRequest,
    db: DbSession,
    user: CurrentUser,
) -> RestaurantRegisterResponse:
    """Self-register a restaurant. Requires a traveller JWT.

    The row lands `is_active = false` and does not appear in search until an
    operator activates it. Unauthenticated, this would be a search-poisoning
    vector whose rows then sit in the cache; unreviewed, it would serve
    unverified restaurants to travellers.

    Rate limited per user, not per IP: there is an authenticated identity here,
    and it is the more meaningful key.
    """
    limit, window = rate_limit.RESTAURANT_REGISTER_LIMIT
    await rate_limit.enforce(rate_limit.restaurant_register_key(user.id), limit, window)

    restaurant = await restaurants_service.register(db, payload, submitted_by=user)
    return RestaurantRegisterResponse(
        id=restaurant.id,
        name=restaurant.name,
        phone=restaurant.phone,
        address=restaurant.address,
        lat=payload.latitude,
        lon=payload.longitude,
        avg_prep_time_minutes=restaurant.avg_prep_time_minutes,
        is_active=restaurant.is_active,
    )


@router.get("/{restaurant_id}", response_model=RestaurantDetailResponse)
async def get_detail(restaurant_id: int, db: DbSession) -> RestaurantDetailResponse:
    """Restaurant detail with its menu.

    The menu here is authoritative — it is the same source booking uses to
    resolve unit prices, so what a client displays is what it will be charged.
    """
    return await restaurants_service.get_detail(db, restaurant_id)
