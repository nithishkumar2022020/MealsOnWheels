"""Bookability: the three facts, timezone handling, and overnight windows.

These are pure-function tests against lightweight stand-ins rather than database
rows, because what is being checked is the *logic* — weekday arithmetic across a
timezone boundary, and the overnight wrap — not the persistence.
"""

from __future__ import annotations

from datetime import UTC, datetime, time

from app.services.bookability import (
    CLOSED_AT_TIME,
    NO_HOURS_SET,
    NOT_ACCEPTING,
    NOT_APPROVED,
    TYPE_UNSUPPORTED,
    is_open_at,
    local_time_at,
    resolve_timezone,
    unbookable_reason,
)


class FakeRestaurant:
    """Stands in for a Restaurant row without needing a session."""

    def __init__(
        self,
        *,
        approval_status: str = "approved",
        is_accepting_orders: bool = True,
        tz: str = "Asia/Kolkata",
        types: tuple[str, ...] = (
            "bus_boarding_point",
            "self_drive_dine",
            "self_drive_takeaway",
        ),
    ) -> None:
        self.approval_status = approval_status
        self.is_accepting_orders = is_accepting_orders
        self.timezone = tz
        self.supported_booking_types = list(types)

    @property
    def is_approved(self) -> bool:
        return self.approval_status == "approved"

    def supports_booking_type(self, booking_type: str) -> bool:
        return booking_type in self.supported_booking_types


class FakeHours:
    def __init__(self, weekday: int, opens: str, closes: str) -> None:
        self.weekday = weekday
        self.opens_at = time.fromisoformat(opens)
        self.closes_at = time.fromisoformat(closes)

    @property
    def is_overnight(self) -> bool:
        return self.closes_at < self.opens_at

    def covers(self, at: time) -> bool:
        if self.is_overnight:
            return at >= self.opens_at or at < self.closes_at
        return self.opens_at <= at < self.closes_at


def utc(spec: str) -> datetime:
    return datetime.fromisoformat(spec).replace(tzinfo=UTC)


# --- timezone -------------------------------------------------------------


def test_unknown_timezone_falls_back_rather_than_raising() -> None:
    # Bad data in one row must not 500 an entire search.
    assert resolve_timezone("Not/AZone").key == "Asia/Kolkata"


def test_utc_instant_converts_to_local_weekday_and_wall_clock() -> None:
    # 02:00 UTC Monday is 07:30 IST Monday.
    weekday, wall = local_time_at(FakeRestaurant(), utc("2026-08-03T02:00:00"))
    assert weekday == 0
    assert wall == time(7, 30)


def test_weekday_comes_from_local_time_not_utc() -> None:
    """The case that makes `timezone` load-bearing rather than cosmetic.

    20:00 UTC on Sunday is 01:30 IST on Monday. Reading the weekday off the UTC
    value would check Sunday's hours for what is, where the food is, a Monday.
    """
    weekday, wall = local_time_at(FakeRestaurant(), utc("2026-08-02T20:00:00"))
    assert weekday == 0, "should be Monday in IST, not Sunday as in UTC"
    assert wall == time(1, 30)


# --- open / closed --------------------------------------------------------


def test_no_hours_means_closed_not_open_all_day() -> None:
    # A newly approved restaurant that has not configured hours must not
    # silently accept orders at any time.
    assert is_open_at(FakeRestaurant(), [], utc("2026-08-03T02:00:00")) is False


def test_inside_window_is_open() -> None:
    hours = [FakeHours(0, "06:00", "23:00")]  # Monday
    assert is_open_at(FakeRestaurant(), hours, utc("2026-08-03T02:00:00")) is True


def test_before_opening_is_closed() -> None:
    hours = [FakeHours(0, "06:00", "23:00")]
    # 00:30 UTC Monday = 06:00... no: 00:30 UTC = 06:00 IST exactly at open.
    # Use 23:00 UTC Sunday = 04:30 IST Monday, before a 06:00 open.
    assert is_open_at(FakeRestaurant(), hours, utc("2026-08-02T23:00:00")) is False


def test_closing_time_is_exclusive() -> None:
    hours = [FakeHours(0, "06:00", "23:00")]
    # 17:30 UTC Monday = 23:00 IST exactly. Closed: a kitchen closing at 23:00
    # is not taking an order at 23:00.
    assert is_open_at(FakeRestaurant(), hours, utc("2026-08-03T17:30:00")) is False


def test_wrong_weekday_is_closed() -> None:
    hours = [FakeHours(0, "06:00", "23:00")]  # Monday only
    # Tuesday 07:30 IST.
    assert is_open_at(FakeRestaurant(), hours, utc("2026-08-04T02:00:00")) is False


# --- overnight windows ----------------------------------------------------


def test_overnight_window_covers_late_evening() -> None:
    hours = [FakeHours(0, "22:00", "02:00")]  # Monday 22:00 -> Tuesday 02:00
    # 17:00 UTC Monday = 22:30 IST Monday.
    assert is_open_at(FakeRestaurant(), hours, utc("2026-08-03T17:00:00")) is True


def test_overnight_window_covers_small_hours_of_next_day() -> None:
    """The bug this exists to prevent.

    A dhaba open Monday 22:00-02:00 is open at 01:00 on Tuesday. Checking only
    Tuesday's rows finds nothing, because the window belongs to the day it
    started — highway dhabas routinely run past midnight, so getting this wrong
    closes them during their busiest hours.
    """
    hours = [FakeHours(0, "22:00", "02:00")]  # Monday only
    # 19:30 UTC Monday = 01:00 IST Tuesday.
    assert is_open_at(FakeRestaurant(), hours, utc("2026-08-03T19:30:00")) is True


def test_overnight_window_does_not_cover_after_it_closes() -> None:
    hours = [FakeHours(0, "22:00", "02:00")]
    # 21:00 UTC Monday = 02:30 IST Tuesday, past the 02:00 close.
    assert is_open_at(FakeRestaurant(), hours, utc("2026-08-03T21:00:00")) is False


# --- reason ordering ------------------------------------------------------


def test_unapproved_reported_before_closed() -> None:
    """Report the most fundamental obstacle, not the first one found.

    An unapproved restaurant told "closed on Tuesday" would have its owner
    waiting for Wednesday instead of chasing an operator.
    """
    restaurant = FakeRestaurant(approval_status="pending")
    reason = unbookable_reason(restaurant, [], utc("2026-08-03T02:00:00"))
    assert reason == NOT_APPROVED


def test_unsupported_booking_type_reported_before_accepting_flag() -> None:
    restaurant = FakeRestaurant(is_accepting_orders=False, types=("self_drive_dine",))
    reason = unbookable_reason(
        restaurant, [], utc("2026-08-03T02:00:00"), booking_type="bus_boarding_point"
    )
    assert reason == TYPE_UNSUPPORTED


def test_owner_toggle_reported_when_approved_and_type_ok() -> None:
    restaurant = FakeRestaurant(is_accepting_orders=False)
    hours = [FakeHours(0, "06:00", "23:00")]
    reason = unbookable_reason(restaurant, hours, utc("2026-08-03T02:00:00"))
    assert reason == NOT_ACCEPTING


def test_missing_hours_distinguished_from_closed_now() -> None:
    # Different remedies: one needs configuration, the other needs waiting.
    assert unbookable_reason(FakeRestaurant(), [], utc("2026-08-03T02:00:00")) == NO_HOURS_SET
    hours = [FakeHours(0, "06:00", "23:00")]
    assert unbookable_reason(FakeRestaurant(), hours, utc("2026-08-04T02:00:00")) == CLOSED_AT_TIME


def test_bookable_returns_none() -> None:
    hours = [FakeHours(0, "06:00", "23:00")]
    reason = unbookable_reason(
        FakeRestaurant(), hours, utc("2026-08-03T02:00:00"), booking_type="self_drive_dine"
    )
    assert reason is None
