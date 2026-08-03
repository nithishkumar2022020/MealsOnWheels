"""Owner-managed menus and hours.

The scoping tests matter most. Every endpoint here derives `restaurant_id` from
the token's staff row, and none of them accept one — so the interesting question
is not "does the happy path work" but "can staff at one dhaba touch another's
menu". They cannot, and these prove it.
"""

from __future__ import annotations

import pytest

from app.core.security import create_restaurant_access_token

OTP = "123456"


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def two_restaurants(db_exec, db_scalar):
    """Two approved restaurants, one staff member each.

    Two rather than one because the scoping tests need a second restaurant that
    the first's staff must not be able to reach.
    """
    for name, phone in (("Dhaba A", "+919111111111"), ("Dhaba B", "+919222222222")):
        db_exec(
            f"""
            INSERT INTO restaurants (name, phone, location, approval_status, is_active)
            VALUES ('{name}', '{phone}',
                    ST_SetSRID(ST_MakePoint(77.02, 29.02), 4326)::geography,
                    'approved', true)
            """
        )

    a_id = db_scalar("SELECT id FROM restaurants WHERE name = 'Dhaba A'")
    b_id = db_scalar("SELECT id FROM restaurants WHERE name = 'Dhaba B'")

    db_exec(
        f"""
        INSERT INTO restaurant_users (restaurant_id, phone, name) VALUES
            ({a_id}, '+919000000001', 'Owner A'),
            ({b_id}, '+919000000002', 'Owner B')
        """
    )
    a_staff = db_scalar("SELECT id FROM restaurant_users WHERE phone = '+919000000001'")
    b_staff = db_scalar("SELECT id FROM restaurant_users WHERE phone = '+919000000002'")

    a_token, _ = create_restaurant_access_token(a_staff, "+919000000001", a_id)
    b_token, _ = create_restaurant_access_token(b_staff, "+919000000002", b_id)

    return {"a_id": a_id, "b_id": b_id, "a_token": a_token, "b_token": b_token}


async def add_item(client, token: str, **overrides):
    body = {"name": "Paneer Paratha", "price": "80.00", "category": "Main"}
    body.update(overrides)
    return await client.post("/api/restaurant/menu", json=body, headers=auth(token))


# --- menu CRUD ------------------------------------------------------------


async def test_create_and_list_item(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    created = await add_item(client, token)
    assert created.status_code == 201
    assert created.json()["name"] == "Paneer Paratha"
    assert created.json()["is_available"] is True

    listed = await client.get("/api/restaurant/menu", headers=auth(token))
    assert listed.status_code == 200
    assert listed.json()["total_count"] == 1


async def test_display_order_appends(client, two_restaurants) -> None:
    """An owner adding a dish should not have to know how many they already have."""
    token = two_restaurants["a_token"]
    first = await add_item(client, token, name="Lassi", category="Beverage")
    second = await add_item(client, token, name="Chai", category="Beverage")

    assert second.json()["display_order"] > first.json()["display_order"]


async def test_duplicate_live_name_rejected(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    await add_item(client, token)
    duplicate = await add_item(client, token)

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "MENU_ITEM_EXISTS"


async def test_price_is_not_taken_from_a_float(client, two_restaurants) -> None:
    """Prices round-trip exactly.

    These are summed into a NUMERIC column that money is owed against; a float
    round-trip would introduce error before anyone has ordered anything.
    """
    token = two_restaurants["a_token"]
    created = await add_item(client, token, price="80.10")
    assert created.json()["price"] == "80.10"


async def test_update_changes_only_sent_fields(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    item_id = (await add_item(client, token, description="Stuffed")).json()["id"]

    updated = await client.put(
        f"/api/restaurant/menu/{item_id}",
        json={"price": "95.00"},
        headers=auth(token),
    )
    assert updated.status_code == 200
    assert updated.json()["price"] == "95.00"
    # Untouched because it was never sent — exclude_unset, not a full replace.
    assert updated.json()["description"] == "Stuffed"


async def test_empty_update_rejected(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    item_id = (await add_item(client, token)).json()["id"]

    response = await client.put(f"/api/restaurant/menu/{item_id}", json={}, headers=auth(token))
    assert response.status_code == 400


async def test_availability_toggle(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    item_id = (await add_item(client, token)).json()["id"]

    response = await client.patch(
        f"/api/restaurant/menu/{item_id}/availability",
        json={"is_available": False},
        headers=auth(token),
    )
    assert response.status_code == 200
    assert response.json()["is_available"] is False


async def test_unavailable_item_still_listed_for_owner(client, two_restaurants) -> None:
    """Sold out is not deleted. The client greys it; hiding it reads as a bug."""
    token = two_restaurants["a_token"]
    item_id = (await add_item(client, token)).json()["id"]
    await client.patch(
        f"/api/restaurant/menu/{item_id}/availability",
        json={"is_available": False},
        headers=auth(token),
    )

    listed = await client.get("/api/restaurant/menu", headers=auth(token))
    assert listed.json()["total_count"] == 1


async def test_delete_is_soft_and_frees_the_name(client, two_restaurants, db_count) -> None:
    """The row survives so historical bookings stay attributable.

    And because the unique index covers live names only, the dish can be added
    again — an owner who deletes by accident is not locked out of the name.
    """
    token = two_restaurants["a_token"]
    item_id = (await add_item(client, token)).json()["id"]

    deleted = await client.delete(f"/api/restaurant/menu/{item_id}", headers=auth(token))
    assert deleted.status_code == 204

    assert db_count("SELECT count(*) FROM menu_items") == 1
    assert db_count("SELECT count(*) FROM menu_items WHERE deleted_at IS NULL") == 0

    listed = await client.get("/api/restaurant/menu", headers=auth(token))
    assert listed.json()["total_count"] == 0

    readded = await add_item(client, token)
    assert readded.status_code == 201


# --- scoping --------------------------------------------------------------


async def test_menu_is_scoped_to_the_token(client, two_restaurants) -> None:
    await add_item(client, two_restaurants["a_token"], name="A dish")
    await add_item(client, two_restaurants["b_token"], name="B dish")

    a_menu = await client.get("/api/restaurant/menu", headers=auth(two_restaurants["a_token"]))
    names = [i["name"] for i in a_menu.json()["items"]]
    assert names == ["A dish"]


async def test_cannot_edit_another_restaurants_item(client, two_restaurants) -> None:
    """404, not 403 — a 403 would confirm the id exists."""
    b_item = (await add_item(client, two_restaurants["b_token"])).json()["id"]

    response = await client.put(
        f"/api/restaurant/menu/{b_item}",
        json={"price": "1.00"},
        headers=auth(two_restaurants["a_token"]),
    )
    assert response.status_code == 404


async def test_cannot_delete_another_restaurants_item(client, two_restaurants) -> None:
    b_item = (await add_item(client, two_restaurants["b_token"])).json()["id"]

    response = await client.delete(
        f"/api/restaurant/menu/{b_item}", headers=auth(two_restaurants["a_token"])
    )
    assert response.status_code == 404


async def test_traveller_token_rejected(client, two_restaurants) -> None:
    from app.core.security import create_access_token

    token, _ = create_access_token(user_id=1, phone="+919876543210")
    response = await client.get("/api/restaurant/menu", headers=auth(token))
    assert response.status_code == 401


async def test_no_token_rejected(client, two_restaurants) -> None:
    response = await client.get("/api/restaurant/menu")
    assert response.status_code == 401


# --- hours ----------------------------------------------------------------


async def test_replace_hours(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    response = await client.put(
        "/api/restaurant/hours",
        json={
            "windows": [
                {"weekday": 0, "opens_at": "06:00", "closes_at": "23:00"},
                {"weekday": 1, "opens_at": "06:00", "closes_at": "23:00"},
            ]
        },
        headers=auth(token),
    )
    assert response.status_code == 200
    assert len(response.json()["hours"]) == 2
    assert response.json()["timezone"] == "Asia/Kolkata"


async def test_replace_removes_omitted_days(client, two_restaurants) -> None:
    """The reason this is a replace and not a merge.

    A merge would leave Tuesday open because the owner did not mention it, which
    is how a restaurant ends up taking orders on a day it thought it had closed.
    """
    token = two_restaurants["a_token"]
    await client.put(
        "/api/restaurant/hours",
        json={
            "windows": [
                {"weekday": 0, "opens_at": "06:00", "closes_at": "23:00"},
                {"weekday": 1, "opens_at": "06:00", "closes_at": "23:00"},
            ]
        },
        headers=auth(token),
    )
    second = await client.put(
        "/api/restaurant/hours",
        json={"windows": [{"weekday": 0, "opens_at": "06:00", "closes_at": "23:00"}]},
        headers=auth(token),
    )
    assert [w["weekday"] for w in second.json()["hours"]] == [0]


async def test_empty_week_means_closed_all_week(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    response = await client.put("/api/restaurant/hours", json={"windows": []}, headers=auth(token))
    assert response.status_code == 200
    assert response.json()["hours"] == []


async def test_overnight_window_flagged(client, two_restaurants) -> None:
    """So a client rendering 22:00–02:00 knows the close is the next day."""
    token = two_restaurants["a_token"]
    response = await client.put(
        "/api/restaurant/hours",
        json={"windows": [{"weekday": 4, "opens_at": "22:00", "closes_at": "02:00"}]},
        headers=auth(token),
    )
    assert response.json()["hours"][0]["is_overnight"] is True


async def test_duplicate_weekday_rejected(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    response = await client.put(
        "/api/restaurant/hours",
        json={
            "windows": [
                {"weekday": 0, "opens_at": "06:00", "closes_at": "12:00"},
                {"weekday": 0, "opens_at": "14:00", "closes_at": "23:00"},
            ]
        },
        headers=auth(token),
    )
    assert response.status_code == 400


async def test_zero_length_window_rejected(client, two_restaurants) -> None:
    """Identical open and close is a typo, not a 24h day or a closure."""
    token = two_restaurants["a_token"]
    response = await client.put(
        "/api/restaurant/hours",
        json={"windows": [{"weekday": 0, "opens_at": "09:00", "closes_at": "09:00"}]},
        headers=auth(token),
    )
    assert response.status_code == 422


# --- open / closed and onboarding ----------------------------------------


async def test_accepting_orders_toggle(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    response = await client.patch(
        "/api/restaurant/accepting-orders",
        json={"is_accepting_orders": False},
        headers=auth(token),
    )
    assert response.status_code == 200
    assert response.json()["is_accepting_orders"] is False
    # Closing for the night must not look like losing approval.
    assert response.json()["approval_status"] == "approved"


async def test_onboarding_reports_what_is_missing(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    response = await client.get("/api/restaurant/onboarding", headers=auth(token))

    body = response.json()
    assert body["onboarding_complete"] is False
    assert "menu_items" in body["missing"]
    assert "opening_hours" in body["missing"]


async def test_onboarding_completes_as_the_owner_works(client, two_restaurants) -> None:
    token = two_restaurants["a_token"]
    await add_item(client, token)
    await client.put(
        "/api/restaurant/hours",
        json={
            "windows": [{"weekday": d, "opens_at": "06:00", "closes_at": "23:00"} for d in range(7)]
        },
        headers=auth(token),
    )

    response = await client.get("/api/restaurant/onboarding", headers=auth(token))
    assert response.json()["onboarding_complete"] is True
    assert response.json()["missing"] == []
