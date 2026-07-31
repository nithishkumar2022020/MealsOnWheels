"""Stage 10c tests: restaurant self-registration.

Two things must hold, and each is a security control rather than a feature:
the endpoint requires a JWT, and the row it creates is invisible until an
operator activates it. The rest of this file is input validation.
"""

from __future__ import annotations

from scripts.seed_data import SEARCH_ORIGIN_LAT, SEARCH_ORIGIN_LON

REGISTER = "/api/restaurants/register"
SEARCH = "/api/restaurants/search"
ORIGIN = {"latitude": SEARCH_ORIGIN_LAT, "longitude": SEARCH_ORIGIN_LON}

# Inside the default radius of the demo point, so an accidentally-active row
# would show up in the search assertions below.
VALID = {
    "name": "New Highway Dhaba",
    "phone": "+919888888888",
    "email": "owner@dhaba.example",
    "address": "NH-44 km 45",
    "latitude": 29.03,
    "longitude": 77.03,
    "avg_prep_time_minutes": 30,
}


async def auth_token(client, phone: str = "+919876500001") -> str:
    await client.post("/api/auth/register", json={"phone": phone, "name": "Owner"})
    response = await client.post("/api/auth/login", json={"phone": phone, "otp": "123456"})
    return response.json()["access_token"]


async def register_restaurant(client, token: str, **overrides):
    body = {**VALID, **overrides}
    return await client.post(REGISTER, json=body, headers={"Authorization": f"Bearer {token}"})


# --- Auth ------------------------------------------------------------------


async def test_register_requires_authentication(client, seeded) -> None:
    """Unauthenticated this is a search-poisoning vector.

    A spammed geospatial row would then persist in the search cache for its full
    TTL, so the write must have an accountable origin.
    """
    response = await client.post(REGISTER, json=VALID)
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


async def test_register_rejects_invalid_token(client, seeded) -> None:
    response = await client.post(
        REGISTER, json=VALID, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


async def test_register_succeeds_with_token(client, seeded) -> None:
    token = await auth_token(client)

    response = await register_restaurant(client, token)
    assert response.status_code == 201

    body = response.json()
    assert body["name"] == "New Highway Dhaba"
    assert isinstance(body["id"], int)
    assert body["lat"] == 29.03
    assert body["lon"] == 77.03


# --- Inactive until reviewed ------------------------------------------------


async def test_registered_restaurant_is_inactive(client, seeded) -> None:
    """Surfaced in the response so the caller knows it is pending, not live."""
    token = await auth_token(client)
    body = (await register_restaurant(client, token)).json()
    assert body["is_active"] is False


async def test_registered_restaurant_absent_from_search(client, seeded) -> None:
    """The control that makes self-registration safe.

    The coordinates are inside the default radius, so if `is_active` were true
    this row would appear.
    """
    token = await auth_token(client)
    before = (await client.get(SEARCH, params=ORIGIN)).json()["total_count"]

    await register_restaurant(client, token)

    after = (await client.get(SEARCH, params=ORIGIN)).json()
    assert after["total_count"] == before
    assert all(r["name"] != "New Highway Dhaba" for r in after["restaurants"])


async def test_registered_restaurant_detail_is_404(client, seeded) -> None:
    """Not readable by guessing the id it was just told."""
    token = await auth_token(client)
    created = (await register_restaurant(client, token)).json()

    response = await client.get(f"/api/restaurants/{created['id']}")
    assert response.status_code == 404


async def test_registered_restaurant_appears_once_activated(client, seeded, db_exec) -> None:
    """An operator flips the flag directly until the approval UI lands."""
    token = await auth_token(client)
    created = (await register_restaurant(client, token)).json()

    db_exec(f"UPDATE restaurants SET is_active = true WHERE id = {created['id']}")

    body = (await client.get(SEARCH, params=ORIGIN)).json()
    assert any(r["name"] == "New Highway Dhaba" for r in body["restaurants"])


async def test_caller_cannot_set_is_active(client, seeded) -> None:
    """No field for it, and extra="forbid" refuses one that is sent anyway."""
    token = await auth_token(client)

    response = await register_restaurant(client, token, is_active=True)
    assert response.status_code == 422


async def test_caller_cannot_set_rating(client, seeded) -> None:
    """A self-registered restaurant cannot arrive pre-rated."""
    token = await auth_token(client)

    response = await register_restaurant(client, token, composite_rating=5)
    assert response.status_code == 422


# --- Validation -------------------------------------------------------------


async def test_register_rejects_non_e164_phone(client, seeded) -> None:
    token = await auth_token(client)
    response = await register_restaurant(client, token, phone="9888888888")
    assert response.status_code == 422


async def test_register_normalises_phone(client, seeded) -> None:
    token = await auth_token(client)
    response = await register_restaurant(client, token, phone="+91 98888-88888")
    assert response.status_code == 201
    assert response.json()["phone"] == "+919888888888"


async def test_register_rejects_out_of_range_coordinates(client, seeded) -> None:
    token = await auth_token(client)
    assert (await register_restaurant(client, token, latitude=91.0)).status_code == 422
    assert (await register_restaurant(client, token, longitude=181.0)).status_code == 422


async def test_register_rejects_nonpositive_prep_time(client, seeded) -> None:
    """avg_prep_time_minutes also sets the minimum booking lead time.

    Zero would let a booking be placed for the current instant, and the database
    CHECK constraint requires it positive regardless.
    """
    token = await auth_token(client)
    assert (await register_restaurant(client, token, avg_prep_time_minutes=0)).status_code == 422


async def test_register_defaults_prep_time(client, seeded) -> None:
    token = await auth_token(client)
    body = {k: v for k, v in VALID.items() if k != "avg_prep_time_minutes"}

    response = await client.post(REGISTER, json=body, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 201
    assert response.json()["avg_prep_time_minutes"] == 30


async def test_register_rejects_blank_name(client, seeded) -> None:
    token = await auth_token(client)
    assert (await register_restaurant(client, token, name="x")).status_code == 422


async def test_register_allows_omitted_optional_fields(client, seeded) -> None:
    token = await auth_token(client)
    response = await client.post(
        REGISTER,
        json={
            "name": "Minimal Dhaba",
            "phone": "+919888888889",
            "latitude": 29.03,
            "longitude": 77.03,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["address"] is None


# --- Rate limiting ----------------------------------------------------------


async def test_register_rate_limited_per_user(client, seeded, monkeypatch) -> None:
    """5 per hour per user (docs/10_SECURITY.md §9). The 6th is a 429."""
    counters: dict[str, int] = {}

    async def fake_incr(key: str, ttl_seconds: int) -> int:
        counters[key] = counters.get(key, 0) + 1
        return counters[key]

    from app.services import rate_limit

    monkeypatch.setattr(rate_limit.cache, "incr_with_expiry", fake_incr)

    token = await auth_token(client)
    for i in range(5):
        response = await register_restaurant(client, token, phone=f"+91988888800{i}")
        assert response.status_code == 201, response.text

    response = await register_restaurant(client, token, phone="+919888888099")
    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"


async def test_register_limit_is_per_user_not_global(client, seeded, monkeypatch) -> None:
    """One user exhausting the limit must not block another."""
    counters: dict[str, int] = {}

    async def fake_incr(key: str, ttl_seconds: int) -> int:
        counters[key] = counters.get(key, 0) + 1
        return counters[key]

    from app.services import rate_limit

    monkeypatch.setattr(rate_limit.cache, "incr_with_expiry", fake_incr)

    first = await auth_token(client, phone="+919876500011")
    for i in range(5):
        await register_restaurant(client, first, phone=f"+91988888810{i}")
    assert (await register_restaurant(client, first, phone="+919888888198")).status_code == 429

    second = await auth_token(client, phone="+919876500012")
    assert (await register_restaurant(client, second, phone="+919888888199")).status_code == 201
