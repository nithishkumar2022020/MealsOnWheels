"""Booking routes.

Thin: every rule that matters lives in `app/services/bookings.py` so it is
testable without an HTTP layer and cannot be subtly different between two routes.

No endpoint here accepts a `user_id`. It comes from the token, so a caller cannot
read or cancel someone else's order by passing an id.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.deps import CurrentUser, DbSession
from app.errors import validation_error
from app.models import BOOKING_STATUSES, Booking
from app.schemas import (
    BookingCreateRequest,
    BookingItemResponse,
    BookingListResponse,
    BookingResponse,
    BookingSummary,
)
from app.services import bookings as booking_service
from app.services import rate_limit

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


def _to_response(booking: Booking) -> BookingResponse:
    return BookingResponse(
        id=booking.id,
        restaurant_id=booking.restaurant_id,
        restaurant_name=booking.restaurant.name,
        route_id=booking.route_id,
        booking_type=booking.booking_type,
        status=booking.status,
        arrival_time=booking.arrival_time,
        cutoff_time=booking.cutoff_time,
        ready_by=booking.ready_by,
        items=[BookingItemResponse.model_validate(i) for i in booking.items],
        total_price=booking.total_price,
        notes=booking.notes,
        payment_status=booking.payment_status,
        confirmed_at=booking.confirmed_at,
        ready_at=booking.ready_at,
        handed_over_at=booking.handed_over_at,
        created_at=booking.created_at,
    )


def _to_summary(booking: Booking) -> BookingSummary:
    return BookingSummary(
        id=booking.id,
        restaurant_id=booking.restaurant_id,
        restaurant_name=booking.restaurant.name,
        booking_type=booking.booking_type,
        status=booking.status,
        arrival_time=booking.arrival_time,
        cutoff_time=booking.cutoff_time,
        total_price=booking.total_price,
        items_summary=booking_service.summarise_items(booking.items),
        created_at=booking.created_at,
    )


@router.post("/create", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreateRequest, user: CurrentUser, db: DbSession
) -> BookingResponse:
    """Place an order.

    The response echoes resolved unit prices and `ready_by` so the client can
    show a priced order and an accurate "food ready at" without recomputing
    either — and without holding an authoritative copy of the menu.
    """
    limit, window = rate_limit.BOOKING_CREATE_LIMIT
    await rate_limit.enforce(rate_limit.booking_create_key(user.id), limit, window)

    booking = await booking_service.create_booking(db, user, payload)
    return _to_response(booking)


@router.get("", response_model=BookingListResponse)
async def list_bookings(
    user: CurrentUser,
    db: DbSession,
    booking_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> BookingListResponse:
    """The caller's own bookings, newest arrival first.

    `status` is validated against the known set rather than passed through: an
    unknown value would otherwise return an empty list, which reads as "you have
    no orders" instead of "that filter is wrong".
    """
    if booking_status is not None and booking_status not in BOOKING_STATUSES:
        raise validation_error(f"status must be one of {', '.join(BOOKING_STATUSES)}")

    found, total = await booking_service.list_bookings(
        db, user, status=booking_status, limit=limit, offset=offset
    )
    return BookingListResponse(
        bookings=[_to_summary(b) for b in found],
        total_count=total,
    )


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking(booking_id: int, user: CurrentUser, db: DbSession) -> BookingResponse:
    """One booking. Another user's id is a 404, not a 403 — ids stay unenumerable."""
    booking = await booking_service.get_booking(db, user, booking_id)
    return _to_response(booking)


@router.put("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking(booking_id: int, user: CurrentUser, db: DbSession) -> BookingResponse:
    """Cancel before handover.

    No `refund_amount` in the response: payment is on arrival, so no money has
    changed hands. Reporting a refund of money never taken is worse than
    reporting nothing.
    """
    booking = await booking_service.cancel_booking(db, user, booking_id)
    return _to_response(booking)
