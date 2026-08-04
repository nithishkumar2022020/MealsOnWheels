"""Booking creation, retrieval, and the state machine.

Three rules hold everywhere in this module, and each one silently re-opens a
hole if it drifts:

1. **The server computes every price.** Line items carry a name and a quantity;
   the unit price comes from `menu_items` and the total is summed here. The
   request schema has no price field at all, so a client-sent one is a 422 rather
   than something quietly ignored.
2. **Resolved prices are frozen onto the booking.** A later menu edit must not
   retroactively change what someone agreed to pay.
3. **Ownership is checked on every read and write**, and a booking belonging to
   someone else is a 404 rather than a 403 — a 403 confirms the id exists and
   makes booking ids enumerable.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.errors import forbidden, not_found, validation_error
from app.models import ALLOWED_TRANSITIONS, Booking, Restaurant, User
from app.schemas import BookingCreateRequest
from app.services import menus as menu_service
from app.services.bookability import NO_MENU, unbookable_reason
from app.services.hours import list_hours

logger = logging.getLogger(__name__)

# Longest a traveller may book ahead. Not a technical limit — beyond a couple of
# days an arrival time is a guess, and a booking nobody shows up for costs a
# kitchen real food.
MAX_LEAD_DAYS = 2

# Why a restaurant could not take the order, phrased for a traveller. The
# machine-readable code goes in `code`; this is what they read.
_UNBOOKABLE_MESSAGES = {
    "not_approved": "This restaurant is not yet open for orders on MealsOnWheels.",
    "not_accepting_orders": "This restaurant has paused orders. Try again later.",
    "closed_at_requested_time": "This restaurant is closed at your arrival time.",
    "no_hours_configured": "This restaurant has not set its opening hours yet.",
    "booking_type_unsupported": "This restaurant does not offer that kind of pickup.",
    NO_MENU: "This restaurant has not published a menu yet.",
}


def summarise_items(items: list[dict]) -> str:
    """ "2× Paneer Paratha, 1× Lassi" for a list row.

    Formatted server-side so a client rendering an order history does not ship
    logic to summarise an array it never otherwise displays.
    """
    return ", ".join(f"{i['qty']}× {i['name']}" for i in items)


async def _load_owned_booking(db: AsyncSession, booking_id: int, user: User) -> Booking:
    """Fetch a booking the user owns, or 404.

    Scoped by `user_id` in the query rather than fetched and then compared: there
    is no window in which the wrong row is loaded, and no branch that could be
    written to forget the comparison.
    """
    result = await db.execute(
        select(Booking)
        .where(Booking.id == booking_id, Booking.user_id == user.id)
        .options(joinedload(Booking.restaurant))
    )
    booking = result.unique().scalar_one_or_none()
    if booking is None:
        raise not_found("Booking not found")
    return booking


async def _resolve_items(
    db: AsyncSession, restaurant_id: int, requested: list
) -> tuple[list[dict], Decimal]:
    """Price the order against the restaurant's own menu.

    `price_lookup` excludes unavailable dishes, so "sold out" and "not on the
    menu" both land here — but they get different messages, because the remedies
    differ: one is "pick something else", the other is "you have the wrong
    restaurant".

    An unavailable item rejects the **whole** booking rather than being dropped
    with the total recomputed. Silently changing what someone agreed to pay is a
    worse surprise than an error
    (docs/16_FUNCTIONAL_PRODUCT_DATA.md section 3.6).
    """
    prices = await menu_service.price_lookup(db, restaurant_id)
    live = await menu_service.list_items(db, restaurant_id)
    ids = {item.name: item.id for item in live}
    known = {item.name for item in live}

    resolved: list[dict] = []
    total = Decimal("0")

    for line in requested:
        price = prices.get(line.name)
        if price is None:
            if line.name in known:
                raise validation_error(
                    f"'{line.name}' is sold out. Remove it and try again.",
                    code="ITEM_UNAVAILABLE",
                )
            raise validation_error(
                f"'{line.name}' is not on this restaurant's menu.",
                code="ITEM_NOT_ON_MENU",
            )

        resolved.append(
            {
                "name": line.name,
                "qty": line.qty,
                # Frozen here. The menu may change tomorrow; this order does not.
                "price": str(price),
                # Plain integer, not an FK — a soft-deleted dish must not break a
                # historical order.
                "menu_item_id": ids.get(line.name),
            }
        )
        total += price * line.qty

    return resolved, total


async def create_booking(db: AsyncSession, user: User, payload: BookingCreateRequest) -> Booking:
    """Place an order.

    Checks run cheapest-and-most-fundamental first, so the traveller is told the
    most useful thing: "this restaurant is closed" rather than "that dish is
    sold out" when both are true.
    """
    restaurant = await db.get(Restaurant, payload.restaurant_id)
    if restaurant is None or not restaurant.is_active:
        raise not_found("Restaurant not found")

    now = datetime.now(UTC)
    arrival = payload.arrival_time.astimezone(UTC)

    # Bookability is evaluated at the ARRIVAL time, not now. A restaurant open
    # while you browse and shut when you arrive cannot take the order — checking
    # `now` would accept it and fail the traveller at the roadside.
    hours = await list_hours(db, restaurant.id)
    reason = unbookable_reason(restaurant, hours, arrival, payload.booking_type)
    if reason is not None:
        raise validation_error(
            _UNBOOKABLE_MESSAGES.get(reason, "This restaurant cannot take orders."),
            code=reason.upper(),
        )

    # The floor is the restaurant's own prep time, not a flat 30 minutes: a
    # kitchen needing 45 cannot meet a 30-minute deadline, and the failure would
    # be silent and land on them.
    prep = timedelta(minutes=restaurant.avg_prep_time_minutes)
    if arrival < now + prep:
        raise validation_error(
            f"{restaurant.name} needs {restaurant.avg_prep_time_minutes} minutes' "
            "notice. Choose a later arrival time.",
            code="ARRIVAL_TOO_SOON",
        )
    if arrival > now + timedelta(days=MAX_LEAD_DAYS):
        raise validation_error(
            f"Bookings can be made up to {MAX_LEAD_DAYS} days ahead.",
            code="ARRIVAL_TOO_FAR",
        )

    resolved, total = await _resolve_items(db, restaurant.id, payload.items)

    booking = Booking(
        user_id=user.id,
        restaurant_id=restaurant.id,
        route_id=payload.route_id,
        arrival_time=arrival,
        cutoff_time=arrival - prep,
        booking_type=payload.booking_type,
        status="pending",
        items=resolved,
        total_price=total,
        notes=payload.notes,
        payment_status="pending",
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking, ["restaurant"])

    logger.info(
        "booking created",
        extra={
            "extra_fields": {
                "event": "booking_created",
                "booking_id": booking.id,
                "restaurant_id": restaurant.id,
                "booking_type": booking.booking_type,
                "total_price": str(total),
            }
        },
    )
    return booking


async def get_booking(db: AsyncSession, user: User, booking_id: int) -> Booking:
    return await _load_owned_booking(db, booking_id, user)


async def list_bookings(
    db: AsyncSession, user: User, *, status: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[Booking], int]:
    """The traveller's own bookings, newest arrival first."""
    conditions = [Booking.user_id == user.id]
    if status is not None:
        conditions.append(Booking.status == status)

    total = await db.scalar(select(func.count()).select_from(Booking).where(*conditions))

    result = await db.execute(
        select(Booking)
        .where(*conditions)
        .options(joinedload(Booking.restaurant))
        .order_by(Booking.arrival_time.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.unique().scalars().all()), int(total or 0)


async def cancel_booking(db: AsyncSession, user: User, booking_id: int) -> Booking:
    """Cancel, if the state machine allows it.

    `handed_over` is terminal: the food has changed hands, so there is nothing
    left to cancel. `ALLOWED_TRANSITIONS` is the single source of that rule —
    this does not re-implement it.
    """
    booking = await _load_owned_booking(db, booking_id, user)

    if not booking.can_transition_to("cancelled"):
        if booking.status == "cancelled":
            raise validation_error(
                "This booking is already cancelled.",
                code="INVALID_STATUS_TRANSITION",
            )
        raise validation_error(
            f"A booking that is already {booking.status.replace('_', ' ')} " "cannot be cancelled.",
            code="INVALID_STATUS_TRANSITION",
        )

    booking.status = "cancelled"
    await db.commit()
    await db.refresh(booking, ["restaurant"])

    logger.info(
        "booking cancelled",
        extra={
            "extra_fields": {
                "event": "booking_cancelled",
                "booking_id": booking.id,
                "restaurant_id": booking.restaurant_id,
            }
        },
    )
    return booking


async def transition(
    db: AsyncSession, booking: Booking, new_status: str, *, restaurant_id: int
) -> Booking:
    """Move a booking to `new_status` on behalf of a restaurant.

    Used by the dashboard (Stage 12). Two guards, both required:

    - the booking must belong to `restaurant_id` — a token alone does not say
      *which* restaurant, so without this one could drive another's orders;
    - the move must be legal, per `ALLOWED_TRANSITIONS`.

    Stamps the matching lifetime column, without which the charter's north-star
    metric cannot be computed at all.
    """
    if booking.restaurant_id != restaurant_id:
        raise forbidden("This booking belongs to another restaurant.")

    if not booking.can_transition_to(new_status):
        allowed = ALLOWED_TRANSITIONS.get(booking.status, set())
        detail = (
            f"Cannot move a {booking.status} booking to {new_status}."
            if allowed
            else f"A {booking.status} booking is final."
        )
        raise validation_error(detail, code="INVALID_STATUS_TRANSITION")

    booking.status = new_status
    stamp = {"confirmed": "confirmed_at", "ready": "ready_at", "handed_over": "handed_over_at"}
    if new_status in stamp:
        setattr(booking, stamp[new_status], datetime.now(UTC))

    await db.commit()
    await db.refresh(booking, ["restaurant"])
    return booking
