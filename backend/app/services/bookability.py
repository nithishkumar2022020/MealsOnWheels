"""Whether a restaurant can take an order, and when.

Three independent facts have to hold, each with a different owner and a different
lifetime (docs/16_FUNCTIONAL_PRODUCT_DATA.md section 2):

    approval_status = 'approved'   ops, ~never changes
    is_accepting_orders            owner, several times a day
    open at the requested time     owner, set once as weekly hours

They are deliberately not collapsed into one flag. An owner tapping "Closed" at
the end of a shift must not produce a state indistinguishable from "ops has not
approved this listing yet", because the two have completely different remedies.
"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models import Restaurant, RestaurantHours

# Why a restaurant cannot take an order. The caller turns these into an error
# code and a user-facing sentence; keeping them as an enum-ish string here means
# the reason survives being logged.
NOT_APPROVED = "not_approved"
NOT_ACCEPTING = "not_accepting_orders"
CLOSED_AT_TIME = "closed_at_requested_time"
NO_HOURS_SET = "no_hours_configured"
TYPE_UNSUPPORTED = "booking_type_unsupported"


def resolve_timezone(name: str) -> ZoneInfo:
    """Load a restaurant's zone, falling back rather than raising.

    An unknown zone is bad data, not a reason to fail a search. IST is the
    correct fallback for every corridor currently served, and the alternative —
    letting a typo in one row 500 an entire search — is worse.
    """
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("Asia/Kolkata")


def local_time_at(restaurant: Restaurant, moment: datetime) -> tuple[int, time]:
    """A UTC instant expressed as (weekday, wall-clock time) where the food is.

    This is the whole reason `restaurants.timezone` exists. "Is 07:30 UTC inside
    Monday 06:00-23:00" is unanswerable without it, and a booking placed near
    midnight UTC falls on a different weekday in IST — so the weekday has to come
    from the converted value, never from the UTC one.
    """
    local = moment.astimezone(resolve_timezone(restaurant.timezone))
    return local.weekday(), local.time()


def is_open_at(
    restaurant: Restaurant,
    hours: list[RestaurantHours],
    moment: datetime,
) -> bool:
    """Whether the restaurant's own hours cover this instant."""
    if not hours:
        # Absent hours mean closed. A newly approved restaurant that has not
        # configured them must not silently accept 3am orders.
        return False

    weekday, wall_clock = local_time_at(restaurant, moment)

    for window in hours:
        if window.weekday == weekday and window.covers(wall_clock):
            return True

    # An overnight window belongs to the day it STARTED. 01:00 on Tuesday is
    # covered by Monday's 22:00-02:00 row, which the loop above never checks
    # because it only looks at Tuesday.
    yesterday = (weekday - 1) % 7
    for window in hours:
        if (
            window.weekday == yesterday
            and window.is_overnight
            and wall_clock < window.closes_at
        ):
            return True

    return False


def unbookable_reason(
    restaurant: Restaurant,
    hours: list[RestaurantHours],
    moment: datetime,
    booking_type: str | None = None,
) -> str | None:
    """Why this restaurant cannot take an order at `moment`, or None if it can.

    Checked in order of how permanent the obstacle is, so the caller reports the
    most fundamental problem rather than the first one found: an unapproved
    restaurant is told it is unapproved, not that it is closed on a Tuesday.
    """
    if not restaurant.is_approved:
        return NOT_APPROVED
    if booking_type is not None and not restaurant.supports_booking_type(booking_type):
        return TYPE_UNSUPPORTED
    if not restaurant.is_accepting_orders:
        return NOT_ACCEPTING
    if not hours:
        return NO_HOURS_SET
    if not is_open_at(restaurant, hours, moment):
        return CLOSED_AT_TIME
    return None
