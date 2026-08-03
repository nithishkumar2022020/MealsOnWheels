"""What a restaurant still needs before it can go live.

Approval now depends on things an owner supplies — a menu, hours, at least one
fulfilment mode — so `approval_status = 'pending'` on its own is a dead end: the
owner sees "not live" with no way to tell whether they are waiting on an operator
or on themselves.

This computes the difference. The client renders it as a checklist
(docs/16_FUNCTIONAL_PRODUCT_DATA.md section 4.1); an operator reviewing a
submission reads the same structure.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MenuItem, Restaurant, RestaurantHours


@dataclass(frozen=True)
class OnboardingStatus:
    has_menu_items: bool
    has_hours: bool
    has_booking_types: bool
    has_contact: bool

    @property
    def is_complete(self) -> bool:
        """Whether the owner has done everything they can.

        Deliberately excludes `approval_status`: this answers "is the ball in the
        owner's court", and conflating it with the operator's decision is the
        confusion the checklist exists to remove.
        """
        return (
            self.has_menu_items and self.has_hours and self.has_booking_types and self.has_contact
        )

    @property
    def missing(self) -> list[str]:
        """Machine-readable list of what is outstanding, in the order to fix it."""
        gaps = []
        if not self.has_contact:
            gaps.append("contact_phone")
        if not self.has_menu_items:
            gaps.append("menu_items")
        if not self.has_hours:
            gaps.append("opening_hours")
        if not self.has_booking_types:
            gaps.append("booking_types")
        return gaps


async def onboarding_status(db: AsyncSession, restaurant: Restaurant) -> OnboardingStatus:
    """Compute what is outstanding for one restaurant.

    Two counts rather than loading the collections: this runs on every staff
    login and an owner with a hundred dishes should not pay for all of them to
    answer "is there at least one".
    """
    menu_count = await db.scalar(
        select(func.count())
        .select_from(MenuItem)
        .where(
            MenuItem.restaurant_id == restaurant.id,
            MenuItem.deleted_at.is_(None),
        )
    )
    hours_count = await db.scalar(
        select(func.count())
        .select_from(RestaurantHours)
        .where(RestaurantHours.restaurant_id == restaurant.id)
    )

    return OnboardingStatus(
        has_menu_items=bool(menu_count),
        has_hours=bool(hours_count),
        has_booking_types=bool(restaurant.supported_booking_types),
        # OSM-promoted rows carry an empty phone: they were never onboarded, so
        # there is nobody to ring when an order lands.
        has_contact=bool(restaurant.phone),
    )
