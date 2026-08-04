"""Restaurant staff login and the actor boundary.

The cross-actor tests are the point of this file. Two actor types now sign
against one secret, and without the `typ` claim a traveller token and a staff
token are byte-indistinguishable once decoded — both reduce to a signed integer
and a phone number. Since `users.id` and `restaurant_users.id` are independent
sequences, low IDs collide as a matter of course, so "traveller 1 presents their
own valid token to a restaurant endpoint" is the common case rather than an
exotic one.
"""

from __future__ import annotations

import pytest

from app.core.security import (
    ACTOR_RESTAURANT,
    ACTOR_TRAVELLER,
    TokenInvalid,
    create_access_token,
    create_restaurant_access_token,
    decode_token,
)

STAFF_PHONE = "+919000000001"
OTHER_PHONE = "+919000000002"
TRAVELLER_PHONE = "+919876543210"
OTP = "123456"


@pytest.fixture
def restaurant_with_staff(db_exec, db_scalar):
    """One approved restaurant with one active staff member."""
    db_exec(
        """
        INSERT INTO restaurants (name, phone, location, approval_status, is_active)
        VALUES ('Test Dhaba', '+919111111111',
                ST_SetSRID(ST_MakePoint(77.02, 29.02), 4326)::geography,
                'approved', true)
        """
    )
    restaurant_id = db_scalar("SELECT id FROM restaurants WHERE name = 'Test Dhaba'")
    db_exec(
        f"""
        INSERT INTO restaurant_users (restaurant_id, phone, name)
        VALUES ({restaurant_id}, '{STAFF_PHONE}', 'Rajesh')
        """
    )
    return restaurant_id


# --- login ----------------------------------------------------------------


async def test_login_returns_scoped_token(client, restaurant_with_staff) -> None:
    response = await client.post(
        "/api/restaurant/auth/login", json={"phone": STAFF_PHONE, "otp": OTP}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["restaurant_id"] == restaurant_with_staff
    assert body["restaurant_name"] == "Test Dhaba"
    assert body["staff_name"] == "Rajesh"
    assert body["token_type"] == "bearer"

    claims = decode_token(body["access_token"], expected_actor=ACTOR_RESTAURANT)
    assert claims.restaurant_id == restaurant_with_staff


async def test_login_reports_onboarding_incomplete(client, restaurant_with_staff) -> None:
    """A restaurant with no menu or hours is not ready, and says so.

    Without this the client cannot tell "no orders yet" from "not live yet" and
    shows an empty queue to an owner who is waiting on themselves.
    """
    response = await client.post(
        "/api/restaurant/auth/login", json={"phone": STAFF_PHONE, "otp": OTP}
    )
    assert response.json()["onboarding_complete"] is False


async def test_login_succeeds_while_pending_approval(
    client, restaurant_with_staff, db_exec
) -> None:
    """Approval gates taking orders, not signing in.

    An owner whose listing is pending needs to log in precisely to find out why
    they are not live. Locking them out makes the onboarding checklist
    unreachable.
    """
    db_exec(f"UPDATE restaurants SET approval_status='pending' WHERE id={restaurant_with_staff}")
    response = await client.post(
        "/api/restaurant/auth/login", json={"phone": STAFF_PHONE, "otp": OTP}
    )
    assert response.status_code == 200
    assert response.json()["approval_status"] == "pending"


async def test_unknown_phone_is_404(client, restaurant_with_staff) -> None:
    response = await client.post(
        "/api/restaurant/auth/login", json={"phone": OTHER_PHONE, "otp": OTP}
    )
    assert response.status_code == 404
    assert response.json()["code"] == "STAFF_NOT_FOUND"


async def test_wrong_otp_is_401(client, restaurant_with_staff) -> None:
    response = await client.post(
        "/api/restaurant/auth/login", json={"phone": STAFF_PHONE, "otp": "000000"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_OTP"


async def test_deactivated_staff_cannot_log_in(client, restaurant_with_staff, db_exec) -> None:
    """And the refusal is indistinguishable from a wrong credential.

    A distinct "your account is disabled" would confirm the number is real staff.
    """
    db_exec(f"UPDATE restaurant_users SET is_active=false WHERE phone='{STAFF_PHONE}'")
    response = await client.post(
        "/api/restaurant/auth/login", json={"phone": STAFF_PHONE, "otp": OTP}
    )
    assert response.status_code == 401


async def test_login_does_not_create_staff(client, db_count) -> None:
    """No implicit creation — the traveller-login rule, applied here.

    Self-service staff creation would let anyone attach themselves to an existing
    restaurant and read its order queue.
    """
    await client.post("/api/restaurant/auth/login", json={"phone": OTHER_PHONE, "otp": OTP})
    assert db_count("SELECT count(*) FROM restaurant_users") == 0


async def test_otp_checked_before_phone_lookup(client, restaurant_with_staff) -> None:
    """A bad OTP yields 401 for known and unknown numbers alike.

    If the lookup came first, the 404/401 split would enumerate which phone
    numbers belong to restaurant staff.
    """
    known = await client.post(
        "/api/restaurant/auth/login", json={"phone": STAFF_PHONE, "otp": "999999"}
    )
    unknown = await client.post(
        "/api/restaurant/auth/login", json={"phone": OTHER_PHONE, "otp": "999999"}
    )
    assert known.status_code == unknown.status_code == 401
    assert known.json()["code"] == unknown.json()["code"]


# --- the actor boundary ---------------------------------------------------


def test_traveller_token_rejected_as_restaurant() -> None:
    token, _ = create_access_token(user_id=1, phone=TRAVELLER_PHONE)
    with pytest.raises(TokenInvalid):
        decode_token(token, expected_actor=ACTOR_RESTAURANT)


def test_restaurant_token_rejected_as_traveller() -> None:
    token, _ = create_restaurant_access_token(
        restaurant_user_id=1, phone=STAFF_PHONE, restaurant_id=7
    )
    with pytest.raises(TokenInvalid):
        decode_token(token, expected_actor=ACTOR_TRAVELLER)


def test_restaurant_token_roundtrip() -> None:
    token, expires_in = create_restaurant_access_token(
        restaurant_user_id=3, phone=STAFF_PHONE, restaurant_id=9
    )
    claims = decode_token(token, expected_actor=ACTOR_RESTAURANT)

    assert claims.subject_id == 3
    assert claims.restaurant_id == 9
    assert claims.actor == ACTOR_RESTAURANT
    assert expires_in > 0


async def test_traveller_token_rejected_by_restaurant_dependency(
    client, restaurant_with_staff, db_exec, db_scalar
) -> None:
    """End to end: a real traveller token on a restaurant-scoped dependency.

    Exercises the collision directly — the traveller is created first so their
    `users.id` and the existing `restaurant_users.id` are both 1.
    """
    db_exec(f"INSERT INTO users (phone, name) VALUES ('{TRAVELLER_PHONE}', 'Priya')")
    user_id = db_scalar(f"SELECT id FROM users WHERE phone = '{TRAVELLER_PHONE}'")
    staff_id = db_scalar(f"SELECT id FROM restaurant_users WHERE phone = '{STAFF_PHONE}'")
    assert user_id == staff_id, "collision not reproduced; test would prove nothing"

    token, _ = create_access_token(user_id=user_id, phone=TRAVELLER_PHONE)

    from app.deps import get_current_staff
    from app.errors import AppError

    async def call() -> None:
        from app.db import SessionLocal

        async with SessionLocal() as session:
            await get_current_staff(db=session, authorization=f"Bearer {token}")

    with pytest.raises(AppError) as exc:
        await call()
    assert exc.value.status_code == 401


async def test_staff_token_resolves_to_row_not_claim(
    client, restaurant_with_staff, db_exec, db_scalar
) -> None:
    """Authorization follows the database row, not the `rid` claim.

    A token minted for restaurant 9999 must not grant access to restaurant 9999
    just because it says so — the dependency loads the staff row and reads
    `restaurant_id` from there.
    """
    staff_id = db_scalar(f"SELECT id FROM restaurant_users WHERE phone = '{STAFF_PHONE}'")
    forged, _ = create_restaurant_access_token(
        restaurant_user_id=staff_id, phone=STAFF_PHONE, restaurant_id=9999
    )

    from app.db import SessionLocal
    from app.deps import get_current_staff

    async with SessionLocal() as session:
        staff = await get_current_staff(db=session, authorization=f"Bearer {forged}")

    assert staff.restaurant_id == restaurant_with_staff, "claim overrode the row"


async def test_deactivated_staff_token_stops_working(
    restaurant_with_staff, db_exec, db_scalar
) -> None:
    """Revocation takes effect immediately, not at token expiry.

    That is the whole point of `restaurant_users.is_active`; without this check
    an ex-manager keeps access for up to 24 hours.
    """
    staff_id = db_scalar(f"SELECT id FROM restaurant_users WHERE phone = '{STAFF_PHONE}'")
    token, _ = create_restaurant_access_token(
        restaurant_user_id=staff_id,
        phone=STAFF_PHONE,
        restaurant_id=restaurant_with_staff,
    )
    db_exec(f"UPDATE restaurant_users SET is_active=false WHERE id={staff_id}")

    from app.db import SessionLocal
    from app.deps import get_current_staff
    from app.errors import AppError

    with pytest.raises(AppError) as exc:
        async with SessionLocal() as session:
            await get_current_staff(db=session, authorization=f"Bearer {token}")
    assert exc.value.status_code == 401
