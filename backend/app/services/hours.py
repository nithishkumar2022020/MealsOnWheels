"""Owner-managed opening hours.

Replaced wholesale rather than patched per weekday: an owner editing hours is
setting a weekly pattern, and a partial update would leave whichever days they
did not mention in whatever state they were before — which is how a restaurant
ends up open on a day it thought it had closed.

Absent rows mean **closed**, so clearing a day is expressed by omitting it. That
also means submitting an empty week is a legitimate "closed all week", and is why
this is a `PUT` on the collection rather than a `PATCH` on rows.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import validation_error
from app.models import Restaurant, RestaurantHours
from app.schemas import HoursWindow

logger = logging.getLogger(__name__)


async def list_hours(db: AsyncSession, restaurant_id: int) -> list[RestaurantHours]:
    result = await db.execute(
        select(RestaurantHours)
        .where(RestaurantHours.restaurant_id == restaurant_id)
        .order_by(RestaurantHours.weekday)
    )
    return list(result.scalars().all())


async def replace_hours(
    db: AsyncSession, restaurant_id: int, windows: list[HoursWindow]
) -> list[RestaurantHours]:
    """Replace the whole weekly pattern in one transaction.

    One window per weekday. The table's primary key would reject a duplicate
    anyway, but the error it produces is an IntegrityError about a constraint
    name — this catches it as a 400 naming the day, which is what the owner
    needs to see.
    """
    seen: set[int] = set()
    for window in windows:
        if window.weekday in seen:
            raise validation_error(
                f"Weekday {window.weekday} appears more than once. " "Submit one window per day."
            )
        seen.add(window.weekday)

    await db.execute(delete(RestaurantHours).where(RestaurantHours.restaurant_id == restaurant_id))
    for window in windows:
        db.add(
            RestaurantHours(
                restaurant_id=restaurant_id,
                weekday=window.weekday,
                opens_at=window.opens_at,
                closes_at=window.closes_at,
            )
        )
    await db.commit()

    logger.info(
        "hours replaced",
        extra={
            "extra_fields": {
                "event": "hours_replaced",
                "restaurant_id": restaurant_id,
                "days_open": len(windows),
            }
        },
    )
    return await list_hours(db, restaurant_id)


async def set_accepting_orders(
    db: AsyncSession, restaurant: Restaurant, *, accepting: bool
) -> Restaurant:
    """The kitchen's own open/closed switch.

    Deliberately not `approval_status`, and deliberately not a row in
    `restaurant_hours`. It is a temporary override on top of the weekly pattern —
    "we are shut early tonight" — and conflating it with either of the other two
    was the bug that motivated splitting them (docs/16_FUNCTIONAL_PRODUCT_DATA.md
    section 2).
    """
    restaurant.is_accepting_orders = accepting
    await db.commit()
    await db.refresh(restaurant)

    logger.info(
        "accepting-orders toggled",
        extra={
            "extra_fields": {
                "event": "accepting_orders_changed",
                "restaurant_id": restaurant.id,
                "is_accepting_orders": accepting,
            }
        },
    )
    return restaurant
