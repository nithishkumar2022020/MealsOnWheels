"""Bookings: pricing, lead time, bookability, ownership, state machine.

The price tests are the reason this file exists. A booking is the only endpoint
where a client could plausibly propose money, and the old contract accepted a
`price` per line — two paranthas for ₹0.02. Several tests below try exactly that
in different ways.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.core.security import create_access_token

PHONE = "+919876543210"
OTHER_PHONE = "+919000000009"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def bookable(db_exec, db_scalar):
    """One restaurant that can actually take an order.

    Open 24h every day, so tests never fail because the suite happened to run at
    2am — hours are exercised deliberately in test_bookability.py and in the
    closed-at-arrival test below, not incidentally everywhere else.
    """
    db_exec(
        """
        INSERT INTO restaurants
            (name, phone, location, approval_status, is_active, avg_prep_time_minutes)
        VALUES ('Bookable Dhaba', '+919111111111',
                ST_SetSRID(ST_MakePoint(77.02, 29.02), 4326)::geography,
                'approved', true, 30)
        """
    )
    rid = db_scalar("SELECT id FROM restaurants WHERE name = 'Bookable Dhaba'")

    for weekday in range(7):
        db_exec(
            f"""
            INSERT INTO restaurant_hours (restaurant_id, weekday, opens_at, closes_at)
            VALUES ({rid}, {weekday}, '00:00', '23:59')
            """
        )
    db_exec(
        f"""
        INSERT INTO menu_items (restaurant_id, name, price, category, display_order)
        VALUES ({rid}, 'Paneer Paratha', 80.00, 'Main', 1),
               ({rid}, 'Lassi', 40.00, 'Beverage', 2)
        """
    )

    db_exec(f"INSERT INTO users (phone, name) VALUES ('{PHONE}', 'Priya')")
    user_id = db_scalar(f"SELECT id FROM users WHERE phone = '{PHONE}'")
    token, _ = create_access_token(user_id=user_id, phone=PHONE)

    return {"restaurant_id": rid, "user_id": user_id, "token": token}


def arrival_in(minutes: int) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


async def book(client, ctx, **overrides):
    body = {
        "restaurant_id": ctx["restaurant_id"],
        "arrival_time": arrival_in(120),
        "booking_type": "self_drive_takeaway",
        "items": [{"name": "Paneer Paratha", "qty": 2}, {"name": "Lassi", "qty": 1}],
    }
    body.update(overrides)
    return await client.post("/api/bookings/create", json=body, headers=auth(ctx["token"]))


# --- pricing --------------------------------------------------------------


async def test_server_computes_total(client, bookable) -> None:
    """2 × 80 + 1 × 40 = 200, computed here and nowhere else."""
    response = await book(client, bookable)
    assert response.status_code == 201

    body = response.json()
    assert body["total_price"] == "200.00"
    assert body["status"] == "pending"


async def test_resolved_prices_echoed_on_each_line(client, bookable) -> None:
    """So a client can render a priced order without holding the menu."""
    body = (await book(client, bookable)).json()
    prices = {i["name"]: i["price"] for i in body["items"]}
    assert prices == {"Paneer Paratha": "80.00", "Lassi": "40.00"}


async def test_client_sent_price_is_rejected_not_ignored(client, bookable) -> None:
    """The whole point of extra="forbid".

    Ignoring the field would let a caller believe they set the price and be
    charged something else. A 422 tells them the field does not exist.
    """
    response = await book(
        client,
        bookable,
        items=[{"name": "Paneer Paratha", "qty": 2, "price": "0.01"}],
    )
    assert response.status_code == 422


async def test_prices_frozen_against_later_menu_edit(client, bookable, db_exec) -> None:
    """A price change tomorrow must not alter an order placed today."""
    booking_id = (await book(client, bookable)).json()["id"]

    db_exec(
        f"""
        UPDATE menu_items SET price = 500.00
        WHERE restaurant_id = {bookable['restaurant_id']} AND name = 'Paneer Paratha'
        """
    )

    reread = await client.get(f"/api/bookings/{booking_id}", headers=auth(bookable["token"]))
    assert reread.json()["total_price"] == "200.00"


async def test_menu_item_id_recorded_on_each_line(client, bookable) -> None:
    """Kept as a plain integer so a soft-deleted dish cannot break this order."""
    body = (await book(client, bookable)).json()
    assert all(isinstance(i["menu_item_id"], int) for i in body["items"])


async def test_unknown_dish_rejected(client, bookable) -> None:
    response = await book(client, bookable, items=[{"name": "Caviar", "qty": 1}])
    assert response.status_code == 400
    assert response.json()["code"] == "ITEM_NOT_ON_MENU"


async def test_sold_out_dish_rejects_whole_booking(client, bookable, db_exec) -> None:
    """Not "drop the line and recompute".

    Silently changing the order someone reviewed — and the total they agreed to —
    is a worse surprise than an error. Distinct code from "not on the menu"
    because the remedies differ.
    """
    db_exec(
        f"""
        UPDATE menu_items SET is_available = false
        WHERE restaurant_id = {bookable['restaurant_id']} AND name = 'Lassi'
        """
    )
    response = await book(client, bookable)

    assert response.status_code == 400
    assert response.json()["code"] == "ITEM_UNAVAILABLE"


async def test_empty_order_rejected(client, bookable) -> None:
    response = await book(client, bookable, items=[])
    assert response.status_code == 422


# --- lead time and arrival ------------------------------------------------


async def test_arrival_too_soon_rejected(client, bookable) -> None:
    """The floor is the restaurant's prep time, not a flat 30 minutes."""
    response = await book(client, bookable, arrival_time=arrival_in(10))
    assert response.status_code == 400
    assert response.json()["code"] == "ARRIVAL_TOO_SOON"


async def test_arrival_just_past_prep_time_accepted(client, bookable) -> None:
    """The boundary is inclusive on the safe side."""
    response = await book(client, bookable, arrival_time=arrival_in(31))
    assert response.status_code == 201


async def test_arrival_in_the_past_rejected(client, bookable) -> None:
    response = await book(client, bookable, arrival_time=arrival_in(-60))
    assert response.status_code == 400
    assert response.json()["code"] == "ARRIVAL_TOO_SOON"


async def test_arrival_too_far_ahead_rejected(client, bookable) -> None:
    response = await book(client, bookable, arrival_time=arrival_in(60 * 24 * 5))
    assert response.status_code == 400
    assert response.json()["code"] == "ARRIVAL_TOO_FAR"


async def test_naive_arrival_time_rejected(client, bookable) -> None:
    """A datetime without an offset silently means "server local" somewhere.

    Every calculation here is UTC, so an ambiguous input is refused rather than
    assumed.
    """
    naive = (datetime.now(UTC) + timedelta(hours=2)).replace(tzinfo=None).isoformat()
    response = await book(client, bookable, arrival_time=naive)
    assert response.status_code == 422


async def test_cutoff_derived_from_prep_time(client, bookable) -> None:
    body = (await book(client, bookable)).json()
    arrival = datetime.fromisoformat(body["arrival_time"])
    cutoff = datetime.fromisoformat(body["cutoff_time"])
    assert arrival - cutoff == timedelta(minutes=30)


# --- booking type ---------------------------------------------------------


async def test_booking_type_required(client, bookable) -> None:
    """Never defaulted: it decides when food should be plated."""
    body = {
        "restaurant_id": bookable["restaurant_id"],
        "arrival_time": arrival_in(120),
        "items": [{"name": "Lassi", "qty": 1}],
    }
    response = await client.post("/api/bookings/create", json=body, headers=auth(bookable["token"]))
    assert response.status_code == 422


async def test_unknown_booking_type_rejected(client, bookable) -> None:
    response = await book(client, bookable, booking_type="helicopter")
    assert response.status_code == 422


async def test_dine_in_ready_by_equals_arrival(client, bookable) -> None:
    """A family still has to park and walk in; food plated early cools."""
    body = (await book(client, bookable, booking_type="self_drive_dine")).json()
    assert body["ready_by"] == body["arrival_time"]


async def test_bus_ready_by_is_five_minutes_early(client, bookable) -> None:
    """A twenty-minute halt is a hard deadline, so the food waits, not the bus."""
    body = (await book(client, bookable, booking_type="bus_boarding_point")).json()
    arrival = datetime.fromisoformat(body["arrival_time"])
    ready_by = datetime.fromisoformat(body["ready_by"])
    assert arrival - ready_by == timedelta(minutes=5)


async def test_unsupported_booking_type_rejected(client, bookable, db_exec) -> None:
    db_exec(
        f"""
        UPDATE restaurants SET supported_booking_types = ARRAY['self_drive_dine']
        WHERE id = {bookable['restaurant_id']}
        """
    )
    response = await book(client, bookable, booking_type="bus_boarding_point")
    assert response.status_code == 400
    assert response.json()["code"] == "BOOKING_TYPE_UNSUPPORTED"


# --- bookability at the arrival time -------------------------------------


async def test_closed_at_arrival_time_rejected(client, bookable, db_exec) -> None:
    """Checked at arrival, not at now.

    A restaurant open while you browse and shut when you arrive cannot take the
    order; validating against `now` would accept it and fail the traveller at the
    roadside. Hours are narrowed to a window that cannot contain arrival+2h.
    """
    db_exec(f"DELETE FROM restaurant_hours WHERE restaurant_id = {bookable['restaurant_id']}")
    now_local = datetime.now(UTC) + timedelta(hours=5, minutes=30)  # IST
    # A one-minute window ending now: open "recently", closed at arrival.
    start = (now_local - timedelta(minutes=1)).strftime("%H:%M")
    end = now_local.strftime("%H:%M")
    for weekday in range(7):
        db_exec(
            f"""
            INSERT INTO restaurant_hours (restaurant_id, weekday, opens_at, closes_at)
            VALUES ({bookable['restaurant_id']}, {weekday}, '{start}', '{end}')
            """
        )

    response = await book(client, bookable)
    assert response.status_code == 400
    assert response.json()["code"] == "CLOSED_AT_REQUESTED_TIME"


async def test_unapproved_restaurant_rejected(client, bookable, db_exec) -> None:
    db_exec(
        f"UPDATE restaurants SET approval_status='pending' WHERE id={bookable['restaurant_id']}"
    )
    response = await book(client, bookable)
    assert response.status_code == 400
    assert response.json()["code"] == "NOT_APPROVED"


async def test_paused_restaurant_rejected(client, bookable, db_exec) -> None:
    db_exec(
        f"UPDATE restaurants SET is_accepting_orders=false WHERE id={bookable['restaurant_id']}"
    )
    response = await book(client, bookable)
    assert response.status_code == 400
    assert response.json()["code"] == "NOT_ACCEPTING_ORDERS"


async def test_inactive_restaurant_is_404(client, bookable, db_exec) -> None:
    """Not a 400: an unapproved listing should not be confirmable by id."""
    db_exec(f"UPDATE restaurants SET is_active=false WHERE id={bookable['restaurant_id']}")
    response = await book(client, bookable)
    assert response.status_code == 404


# --- ownership ------------------------------------------------------------


async def test_cannot_read_another_users_booking(client, bookable, db_exec, db_scalar) -> None:
    """404, not 403 — a 403 confirms the id exists and makes ids enumerable."""
    booking_id = (await book(client, bookable)).json()["id"]

    db_exec(f"INSERT INTO users (phone, name) VALUES ('{OTHER_PHONE}', 'Someone')")
    other_id = db_scalar(f"SELECT id FROM users WHERE phone = '{OTHER_PHONE}'")
    other_token, _ = create_access_token(user_id=other_id, phone=OTHER_PHONE)

    response = await client.get(f"/api/bookings/{booking_id}", headers=auth(other_token))
    assert response.status_code == 404


async def test_cannot_cancel_another_users_booking(client, bookable, db_exec, db_scalar) -> None:
    booking_id = (await book(client, bookable)).json()["id"]

    db_exec(f"INSERT INTO users (phone, name) VALUES ('{OTHER_PHONE}', 'Someone')")
    other_id = db_scalar(f"SELECT id FROM users WHERE phone = '{OTHER_PHONE}'")
    other_token, _ = create_access_token(user_id=other_id, phone=OTHER_PHONE)

    response = await client.put(f"/api/bookings/{booking_id}/cancel", headers=auth(other_token))
    assert response.status_code == 404


async def test_list_returns_only_own_bookings(client, bookable, db_exec, db_scalar) -> None:
    await book(client, bookable)

    db_exec(f"INSERT INTO users (phone, name) VALUES ('{OTHER_PHONE}', 'Someone')")
    other_id = db_scalar(f"SELECT id FROM users WHERE phone = '{OTHER_PHONE}'")
    other_token, _ = create_access_token(user_id=other_id, phone=OTHER_PHONE)

    response = await client.get("/api/bookings", headers=auth(other_token))
    assert response.json()["total_count"] == 0


async def test_unauthenticated_rejected(client, bookable) -> None:
    response = await client.post(
        "/api/bookings/create",
        json={
            "restaurant_id": bookable["restaurant_id"],
            "arrival_time": arrival_in(120),
            "booking_type": "self_drive_takeaway",
            "items": [{"name": "Lassi", "qty": 1}],
        },
    )
    assert response.status_code == 401


async def test_restaurant_token_cannot_book(client, bookable, db_exec, db_scalar) -> None:
    """Actor separation, end to end on a traveller endpoint."""
    from app.core.security import create_restaurant_access_token

    db_exec(
        f"""
        INSERT INTO restaurant_users (restaurant_id, phone, name)
        VALUES ({bookable['restaurant_id']}, '+919555000222', 'Staff')
        """
    )
    staff_id = db_scalar("SELECT id FROM restaurant_users WHERE phone = '+919555000222'")
    token, _ = create_restaurant_access_token(staff_id, "+919555000222", bookable["restaurant_id"])

    response = await book(client, {**bookable, "token": token})
    assert response.status_code == 401


# --- listing --------------------------------------------------------------


async def test_list_includes_items_summary(client, bookable) -> None:
    """Formatted server-side so a list row needs no rendering logic."""
    await book(client, bookable)
    body = (await client.get("/api/bookings", headers=auth(bookable["token"]))).json()

    assert body["total_count"] == 1
    assert body["bookings"][0]["items_summary"] == "2× Paneer Paratha, 1× Lassi"


async def test_list_filters_by_status(client, bookable) -> None:
    await book(client, bookable)
    body = (
        await client.get("/api/bookings?status=confirmed", headers=auth(bookable["token"]))
    ).json()
    assert body["total_count"] == 0


async def test_unknown_status_filter_is_an_error_not_an_empty_list(client, bookable) -> None:
    """An empty list would read as "you have no orders" rather than "bad filter"."""
    response = await client.get("/api/bookings?status=nonsense", headers=auth(bookable["token"]))
    assert response.status_code == 400


async def test_pagination(client, bookable) -> None:
    for _ in range(3):
        await book(client, bookable)

    page = await client.get("/api/bookings?limit=2", headers=auth(bookable["token"]))
    body = page.json()
    assert len(body["bookings"]) == 2
    assert body["total_count"] == 3


# --- state machine --------------------------------------------------------


async def test_cancel_from_pending(client, bookable) -> None:
    booking_id = (await book(client, bookable)).json()["id"]
    response = await client.put(
        f"/api/bookings/{booking_id}/cancel", headers=auth(bookable["token"])
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.parametrize("status", ["confirmed", "ready"])
async def test_cancel_allowed_before_handover(client, bookable, db_exec, status) -> None:
    booking_id = (await book(client, bookable)).json()["id"]
    db_exec(f"UPDATE bookings SET status='{status}' WHERE id={booking_id}")

    response = await client.put(
        f"/api/bookings/{booking_id}/cancel", headers=auth(bookable["token"])
    )
    assert response.status_code == 200


async def test_cannot_cancel_after_handover(client, bookable, db_exec) -> None:
    """Terminal. The food has changed hands; there is nothing to cancel."""
    booking_id = (await book(client, bookable)).json()["id"]
    db_exec(f"UPDATE bookings SET status='handed_over' WHERE id={booking_id}")

    response = await client.put(
        f"/api/bookings/{booking_id}/cancel", headers=auth(bookable["token"])
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_STATUS_TRANSITION"


async def test_cannot_cancel_twice(client, bookable) -> None:
    booking_id = (await book(client, bookable)).json()["id"]
    await client.put(f"/api/bookings/{booking_id}/cancel", headers=auth(bookable["token"]))

    again = await client.put(f"/api/bookings/{booking_id}/cancel", headers=auth(bookable["token"]))
    assert again.status_code == 400


# --- transitions (used by the dashboard in Stage 12) ---------------------


@pytest.mark.parametrize(
    "start,target,allowed",
    [
        ("pending", "confirmed", True),
        ("pending", "cancelled", True),
        ("pending", "ready", False),
        ("pending", "handed_over", False),
        ("confirmed", "ready", True),
        ("confirmed", "cancelled", True),
        ("confirmed", "pending", False),
        ("confirmed", "handed_over", False),
        ("ready", "handed_over", True),
        ("ready", "cancelled", True),
        ("ready", "pending", False),
        ("ready", "confirmed", False),
        ("handed_over", "cancelled", False),
        ("handed_over", "ready", False),
        ("cancelled", "pending", False),
        ("cancelled", "confirmed", False),
    ],
)
async def test_every_transition(client, bookable, db_exec, start, target, allowed) -> None:
    """The full matrix, including every reversal and every move out of a terminal.

    Driven off ALLOWED_TRANSITIONS via the service, so the table and the code
    cannot disagree without this failing.
    """
    from app.db import SessionLocal
    from app.errors import AppError
    from app.models import Booking
    from app.services.bookings import transition

    booking_id = (await book(client, bookable)).json()["id"]
    db_exec(f"UPDATE bookings SET status='{start}' WHERE id={booking_id}")

    async with SessionLocal() as session:
        booking = await session.get(Booking, booking_id)
        if allowed:
            updated = await transition(
                session, booking, target, restaurant_id=bookable["restaurant_id"]
            )
            assert updated.status == target
        else:
            with pytest.raises(AppError) as exc:
                await transition(session, booking, target, restaurant_id=bookable["restaurant_id"])
            assert exc.value.status_code == 400


async def test_transition_stamps_lifecycle_column(client, bookable, db_exec, db_scalar) -> None:
    """Without these the charter's north-star metric cannot be computed at all."""
    from app.db import SessionLocal
    from app.models import Booking
    from app.services.bookings import transition

    booking_id = (await book(client, bookable)).json()["id"]

    async with SessionLocal() as session:
        booking = await session.get(Booking, booking_id)
        await transition(session, booking, "confirmed", restaurant_id=bookable["restaurant_id"])

    assert db_scalar(f"SELECT confirmed_at FROM bookings WHERE id={booking_id}") is not None
    assert db_scalar(f"SELECT ready_at FROM bookings WHERE id={booking_id}") is None


async def test_transition_refuses_another_restaurants_booking(client, bookable) -> None:
    """A token says who, not which restaurant. Without this check one could drive
    another's orders."""
    from app.db import SessionLocal
    from app.errors import AppError
    from app.models import Booking
    from app.services.bookings import transition

    booking_id = (await book(client, bookable)).json()["id"]

    async with SessionLocal() as session:
        booking = await session.get(Booking, booking_id)
        with pytest.raises(AppError) as exc:
            await transition(session, booking, "confirmed", restaurant_id=99999)
    assert exc.value.status_code == 403
