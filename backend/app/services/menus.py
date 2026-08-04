"""Owner-managed menus.

Replaces the hardcoded tables that lived in `app/services/menu.py`. Moving prices
from a Python constant into a row does **not** move the trust boundary: they are
still resolved server-side from the server's own record, and still frozen onto the
booking line at order time. A client could not propose a price before and cannot
now.

Two distinctions the schema makes and this module has to respect:

- `is_available` vs `deleted_at` — "we are out of paneer today" and "we stopped
  selling this" differ in reversibility. Unavailable items are still returned so
  the client can grey them out; deleted ones are gone.
- `display_order` vs alphabetical — the owner decides. Alphabetical would put
  Beverage before Main on every menu in the country.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import conflict, not_found, validation_error
from app.models import MenuItem
from app.schemas import MenuItemCreate, MenuItemUpdate

logger = logging.getLogger(__name__)


async def list_items(
    db: AsyncSession, restaurant_id: int, *, include_unavailable: bool = True
) -> list[MenuItem]:
    """Live menu items in the owner's order.

    `include_unavailable=False` is for the booking path, which must not price an
    item nobody can cook. The traveller-facing menu keeps them: hiding a dish
    someone is looking for reads as a broken app, greying it out reads as
    "sold out".
    """
    stmt = (
        select(MenuItem)
        .where(MenuItem.restaurant_id == restaurant_id, MenuItem.deleted_at.is_(None))
        .order_by(MenuItem.display_order, MenuItem.id)
    )
    if not include_unavailable:
        stmt = stmt.where(MenuItem.is_available.is_(True))

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_item(db: AsyncSession, restaurant_id: int, item_id: int) -> MenuItem:
    """One live item belonging to this restaurant.

    Scoped by `restaurant_id` rather than fetched by primary key alone: an owner
    passing another restaurant's item id gets a 404, not that restaurant's dish.
    A 403 would confirm the id exists.
    """
    result = await db.execute(
        select(MenuItem).where(
            MenuItem.id == item_id,
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.deleted_at.is_(None),
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise not_found("Menu item not found")
    return item


async def _next_display_order(db: AsyncSession, restaurant_id: int) -> int:
    """Append to the end of the owner's ordering."""
    highest = await db.scalar(
        select(func.max(MenuItem.display_order)).where(
            MenuItem.restaurant_id == restaurant_id,
            MenuItem.deleted_at.is_(None),
        )
    )
    return (highest or 0) + 1


async def create_item(db: AsyncSession, restaurant_id: int, payload: MenuItemCreate) -> MenuItem:
    """Add a dish.

    A duplicate live name is a 409. The partial unique index is the real guard —
    this check only produces a better message in the common case, and loses the
    race to a concurrent insert, which is why the IntegrityError path exists.
    """
    item = MenuItem(
        restaurant_id=restaurant_id,
        name=payload.name,
        description=payload.description,
        price=payload.price,
        category=payload.category,
        prep_time_minutes=payload.prep_time_minutes,
        image_url=payload.image_url,
        is_available=payload.is_available,
        display_order=(
            payload.display_order
            if payload.display_order is not None
            else await _next_display_order(db, restaurant_id)
        ),
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise conflict(
            f"'{payload.name}' is already on this menu.",
            code="MENU_ITEM_EXISTS",
        ) from None

    await db.refresh(item)
    logger.info(
        "menu item created",
        extra={
            "extra_fields": {
                "event": "menu_item_created",
                "restaurant_id": restaurant_id,
                "menu_item_id": item.id,
            }
        },
    )
    return item


async def update_item(
    db: AsyncSession, restaurant_id: int, item_id: int, payload: MenuItemUpdate
) -> MenuItem:
    """Edit a dish.

    A price change here does **not** touch bookings already placed: those froze
    their unit prices at order time, which is the whole reason they are frozen.
    """
    item = await get_item(db, restaurant_id, item_id)

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise validation_error("No fields to update")

    for field, value in changes.items():
        setattr(item, field, value)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise conflict(
            f"'{changes.get('name')}' is already on this menu.",
            code="MENU_ITEM_EXISTS",
        ) from None

    await db.refresh(item)
    return item


async def set_availability(
    db: AsyncSession, restaurant_id: int, item_id: int, *, is_available: bool
) -> MenuItem:
    """The most-used control in the product.

    Split out from `update_item` because it is tapped mid-service, one-handed, on
    a kitchen tablet — it deserves an endpoint that cannot fail on an unrelated
    validation error in a field the caller never sent.
    """
    item = await get_item(db, restaurant_id, item_id)
    item.is_available = is_available
    await db.commit()
    await db.refresh(item)

    logger.info(
        "menu availability changed",
        extra={
            "extra_fields": {
                "event": "menu_availability_changed",
                "restaurant_id": restaurant_id,
                "menu_item_id": item.id,
                "is_available": is_available,
            }
        },
    )
    return item


async def delete_item(db: AsyncSession, restaurant_id: int, item_id: int) -> None:
    """Soft delete.

    Hard deletion would strand `menu_item_id` references on historical booking
    lines. Those lines carry a frozen name and price, so an order stays readable
    either way — but the id is the only link back to what was ordered, and losing
    it silently makes past orders unattributable.
    """
    item = await get_item(db, restaurant_id, item_id)
    item.deleted_at = datetime.now(UTC)
    await db.commit()

    logger.info(
        "menu item deleted",
        extra={
            "extra_fields": {
                "event": "menu_item_deleted",
                "restaurant_id": restaurant_id,
                "menu_item_id": item_id,
            }
        },
    )


async def price_lookup(db: AsyncSession, restaurant_id: int) -> dict[str, Decimal]:
    """Name -> unit price, for orderable items only.

    The booking path's single source of prices. Excludes unavailable items on
    purpose: an order must not be priced for a dish the kitchen has run out of,
    and the caller turns a miss into a rejection rather than a guess.
    """
    items = await list_items(db, restaurant_id, include_unavailable=False)
    return {item.name: item.price for item in items}
