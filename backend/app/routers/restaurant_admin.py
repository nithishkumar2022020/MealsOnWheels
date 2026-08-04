"""Owner-facing restaurant management.

Every endpoint here scopes to `staff.restaurant_id` — read from the
`restaurant_users` row the token resolved to, never from a path or query
parameter. There is deliberately no `restaurant_id` in any signature below: if it
is not accepted, it cannot be trusted by mistake.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.deps import CurrentStaff, DbSession
from app.schemas import (
    AcceptingOrdersUpdate,
    AvailabilityUpdate,
    HoursReplaceRequest,
    HoursResponse,
    HoursWindowResponse,
    MenuItemCreate,
    MenuItemUpdate,
    OnboardingResponse,
    OwnerMenuItemResponse,
    OwnerMenuResponse,
)
from app.services import hours as hours_service
from app.services import menus as menu_service
from app.services.onboarding import onboarding_status

router = APIRouter(prefix="/api/restaurant", tags=["restaurant-management"])


def _hours_response(restaurant, windows) -> HoursResponse:
    return HoursResponse(
        hours=[
            HoursWindowResponse(
                weekday=w.weekday,
                opens_at=w.opens_at,
                closes_at=w.closes_at,
                is_overnight=w.is_overnight,
            )
            for w in windows
        ],
        timezone=restaurant.timezone,
    )


# --- Menu -----------------------------------------------------------------


@router.get("/menu", response_model=OwnerMenuResponse)
async def list_menu(staff: CurrentStaff, db: DbSession) -> OwnerMenuResponse:
    """The owner's full menu, including items currently marked unavailable."""
    items = await menu_service.list_items(db, staff.restaurant_id)
    return OwnerMenuResponse(
        items=[OwnerMenuItemResponse.model_validate(i) for i in items],
        total_count=len(items),
    )


@router.post("/menu", response_model=OwnerMenuItemResponse, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    payload: MenuItemCreate, staff: CurrentStaff, db: DbSession
) -> OwnerMenuItemResponse:
    item = await menu_service.create_item(db, staff.restaurant_id, payload)
    return OwnerMenuItemResponse.model_validate(item)


@router.put("/menu/{item_id}", response_model=OwnerMenuItemResponse)
async def update_menu_item(
    item_id: int, payload: MenuItemUpdate, staff: CurrentStaff, db: DbSession
) -> OwnerMenuItemResponse:
    """Edit a dish. Does not touch bookings already placed — their prices froze at
    order time."""
    item = await menu_service.update_item(db, staff.restaurant_id, item_id, payload)
    return OwnerMenuItemResponse.model_validate(item)


@router.patch("/menu/{item_id}/availability", response_model=OwnerMenuItemResponse)
async def set_menu_item_availability(
    item_id: int, payload: AvailabilityUpdate, staff: CurrentStaff, db: DbSession
) -> OwnerMenuItemResponse:
    """Mark a dish in or out of stock.

    Its own endpoint because it is the most-used control in the product — tapped
    mid-service, one-handed, on a kitchen tablet. Routing it through the general
    update would let an unrelated validation error block a stock change.
    """
    item = await menu_service.set_availability(
        db, staff.restaurant_id, item_id, is_available=payload.is_available
    )
    return OwnerMenuItemResponse.model_validate(item)


@router.delete("/menu/{item_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_menu_item(item_id: int, staff: CurrentStaff, db: DbSession) -> Response:
    """Soft delete. Historical bookings keep their frozen line items.

    Returns an explicit empty `Response`: FastAPI refuses to build a 204 route
    that could serialise a body, and the default JSON response class counts as
    one even when the handler returns None.
    """
    await menu_service.delete_item(db, staff.restaurant_id, item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Hours ----------------------------------------------------------------


@router.get("/hours", response_model=HoursResponse)
async def get_hours(staff: CurrentStaff, db: DbSession) -> HoursResponse:
    windows = await hours_service.list_hours(db, staff.restaurant_id)
    return _hours_response(staff.restaurant, windows)


@router.put("/hours", response_model=HoursResponse)
async def replace_hours(
    payload: HoursReplaceRequest, staff: CurrentStaff, db: DbSession
) -> HoursResponse:
    """Replace the whole weekly pattern.

    A replace rather than a merge: omitting a day is how it is marked closed, and
    a partial update would silently leave unmentioned days as they were — which
    is how a restaurant ends up open on a day it thought it had closed.
    """
    windows = await hours_service.replace_hours(db, staff.restaurant_id, payload.windows)
    return _hours_response(staff.restaurant, windows)


# --- Open / closed --------------------------------------------------------


@router.patch("/accepting-orders", response_model=OnboardingResponse)
async def set_accepting_orders(
    payload: AcceptingOrdersUpdate, staff: CurrentStaff, db: DbSession
) -> OnboardingResponse:
    """The kitchen's own open/closed switch, independent of hours and approval."""
    restaurant = await hours_service.set_accepting_orders(
        db, staff.restaurant, accepting=payload.is_accepting_orders
    )
    state = await onboarding_status(db, restaurant)
    return OnboardingResponse(
        approval_status=restaurant.approval_status,
        is_accepting_orders=restaurant.is_accepting_orders,
        onboarding_complete=state.is_complete,
        missing=state.missing,
    )


@router.get("/onboarding", response_model=OnboardingResponse)
async def get_onboarding(staff: CurrentStaff, db: DbSession) -> OnboardingResponse:
    """What the owner still owes before the listing can go live.

    Drives the checklist. Without it `approval_status = 'pending'` is a dead end —
    the owner cannot tell whether they are waiting on an operator or on
    themselves.
    """
    state = await onboarding_status(db, staff.restaurant)
    return OnboardingResponse(
        approval_status=staff.restaurant.approval_status,
        is_accepting_orders=staff.restaurant.is_accepting_orders,
        onboarding_complete=state.is_complete,
        missing=state.missing,
    )
