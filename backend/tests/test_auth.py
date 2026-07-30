"""Stage 8 tests: register, login, JWT, profile.

The cases that matter most are the negative ones. Register-success passing tells
you little; login refusing to create a user, and the stub OTP being refused when
it is not allowed, are the two behaviours whose absence is a security hole rather
than a bug.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.config import get_settings
from app.core.security import ALGORITHM, create_access_token

PHONE = "+919876543210"
STUB_OTP = "123456"


async def register(client, phone: str = PHONE, **extra):
    body = {"phone": phone, "name": "Priya Sharma", **extra}
    return await client.post("/api/auth/register", json=body)


async def login(client, phone: str = PHONE, otp: str = STUB_OTP):
    return await client.post("/api/auth/login", json={"phone": phone, "otp": otp})


async def token_for(client, phone: str = PHONE) -> str:
    await register(client, phone)
    response = await login(client, phone)
    return response.json()["access_token"]


# --- Register -------------------------------------------------------------


async def test_register_creates_user(client) -> None:
    response = await register(client, email="priya@example.com")
    assert response.status_code == 201

    body = response.json()
    assert body["phone"] == PHONE
    assert body["name"] == "Priya Sharma"
    assert body["email"] == "priya@example.com"
    assert isinstance(body["id"], int)
    assert body["created_at"]


async def test_register_duplicate_phone_conflicts(client) -> None:
    assert (await register(client)).status_code == 201

    response = await register(client)
    assert response.status_code == 409
    assert response.json()["code"] == "PHONE_ALREADY_REGISTERED"


async def test_register_normalises_phone_before_uniqueness_check(client) -> None:
    """Two spellings of one number must collide, not create two accounts.

    Without normalisation the unique index is on the literal string, so
    " +91 98765-43210 " and "+919876543210" are different rows for the same
    person — and then login for that number is ambiguous.
    """
    assert (await register(client, phone=PHONE)).status_code == 201

    response = await register(client, phone=" +91 98765-43210 ")
    assert response.status_code == 409
    assert response.json()["code"] == "PHONE_ALREADY_REGISTERED"


async def test_register_rejects_non_e164_phone(client) -> None:
    response = await register(client, phone="9876543210")  # no country code
    assert response.status_code == 422
    assert response.json()["code"] == "UNPROCESSABLE_ENTITY"


async def test_register_rejects_unknown_field(client) -> None:
    """extra="forbid" is what makes the Stage 11 price promise true.

    A field the server does not model must be refused, not ignored — otherwise a
    client can believe it set something it did not.
    """
    response = await client.post(
        "/api/auth/register",
        json={"phone": PHONE, "name": "Priya", "is_admin": True},
    )
    assert response.status_code == 422


async def test_register_blank_name_stored_as_null(client) -> None:
    response = await register(client, name="   ")
    assert response.status_code == 201
    assert response.json()["name"] is None


# --- Login ----------------------------------------------------------------


async def test_login_with_stub_otp_returns_token(client) -> None:
    await register(client)

    response = await login(client)
    assert response.status_code == 200

    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().JWT_EXPIRE_HOURS * 3600
    assert body["user"]["phone"] == PHONE
    # The summary is trimmed on purpose: no email, no timestamps.
    assert set(body["user"]) == {"id", "phone", "name"}

    claims = jwt.decode(body["access_token"], get_settings().JWT_SECRET, algorithms=[ALGORITHM])
    assert claims["sub"] == str(body["user"]["id"])
    assert claims["phone"] == PHONE
    # Exactly the documented claim set — a JWT is readable by its bearer, so
    # anything extra here is published, not stored.
    assert set(claims) == {"sub", "phone", "iat", "exp"}


async def test_login_wrong_otp_rejected(client) -> None:
    await register(client)

    response = await login(client, otp="000000")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_OTP"


async def test_login_unknown_phone_does_not_create_user(client) -> None:
    """The load-bearing test of this stage.

    Auto-registering on login, combined with a constant OTP, let anyone mint a
    24-hour token for any phone number — including a real person's. The 404 is
    the control.
    """
    response = await login(client, phone="+919000000001")
    assert response.status_code == 404
    assert response.json()["code"] == "USER_NOT_FOUND"
    assert "access_token" not in response.json()

    # And nothing was inserted as a side effect: registering now succeeds.
    assert (await register(client, phone="+919000000001")).status_code == 201


async def test_login_rejects_stub_when_not_allowed(client, monkeypatch) -> None:
    """With the stub disallowed and no SMS provider, login is 503.

    Never a fall-through to accepting 123456 — that is the production posture,
    exercised here by flipping the single flag it keys on.
    """
    await register(client)

    settings = get_settings()
    monkeypatch.setattr(type(settings), "otp_stub_allowed", property(lambda self: False))

    response = await login(client)
    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"


async def test_login_checks_otp_before_phone_existence(client, monkeypatch) -> None:
    """A caller without a valid OTP cannot enumerate registered numbers.

    Unknown phone + wrong OTP must answer 401, the same as a known phone with a
    wrong OTP — not 404, which would confirm the number is not registered.
    """
    response = await login(client, phone="+919000000009", otp="000000")
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_OTP"


async def test_login_rejects_malformed_otp(client) -> None:
    await register(client)

    response = await login(client, otp="abcdef")
    assert response.status_code == 422


# --- Profile --------------------------------------------------------------


async def test_profile_with_valid_token(client) -> None:
    token = await token_for(client)

    response = await client.get("/api/user/profile", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["phone"] == PHONE


async def test_profile_without_token_unauthorised(client) -> None:
    response = await client.get("/api/user/profile")
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


async def test_profile_with_malformed_header_unauthorised(client) -> None:
    token = await token_for(client)

    for header in (token, f"Basic {token}", "Bearer", "Bearer    "):
        response = await client.get("/api/user/profile", headers={"Authorization": header})
        assert response.status_code == 401, header
        assert response.json()["code"] == "UNAUTHORIZED"


async def test_profile_with_expired_token(client) -> None:
    """Expiry is distinguishable from invalid, so a client knows to re-login."""
    await register(client)
    settings = get_settings()
    past = datetime.now(UTC) - timedelta(hours=1)
    expired = jwt.encode(
        {
            "sub": "1",
            "phone": PHONE,
            "iat": int((past - timedelta(hours=24)).timestamp()),
            "exp": int(past.timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=ALGORITHM,
    )

    response = await client.get("/api/user/profile", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_EXPIRED"


async def test_profile_with_foreign_signature_rejected(client) -> None:
    """A token signed with another key is invalid, not merely unknown."""
    forged = jwt.encode(
        {"sub": "1", "phone": PHONE, "iat": 0, "exp": 9999999999},
        "a-different-secret-entirely-not-ours",
        algorithm=ALGORITHM,
    )

    response = await client.get("/api/user/profile", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


async def test_profile_for_deleted_user_rejected(client) -> None:
    """A validly signed token for a row that no longer exists is still a 401.

    Not a 500 from a None user, and not distinguishable from a bad signature —
    probing tokens must not reveal which users exist.
    """
    token, _ = create_access_token(user_id=999_999, phone=PHONE)

    response = await client.get("/api/user/profile", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


# --- Token unit tests -----------------------------------------------------


def test_token_roundtrip() -> None:
    from app.core.security import decode_token

    token, expires_in = create_access_token(user_id=42, phone=PHONE)
    claims = decode_token(token)

    assert claims.user_id == 42
    assert claims.phone == PHONE
    assert expires_in == get_settings().JWT_EXPIRE_HOURS * 3600


def test_decode_rejects_token_missing_claims() -> None:
    """A correctly signed token without our claims is invalid, not accepted."""
    from app.core.security import TokenInvalid, decode_token

    token = jwt.encode({"exp": 9999999999}, get_settings().JWT_SECRET, algorithm=ALGORITHM)
    with pytest.raises(TokenInvalid):
        decode_token(token)


# --- Rate limiting --------------------------------------------------------


async def test_rate_limit_fails_open_without_cache(client) -> None:
    """Eleven logins succeed when Redis is absent, by design.

    The limit is 10/hour/phone, but failing closed would turn a cache outage into
    an auth outage. Tests run with REDIS_URL unset, so this asserts the
    documented fail-open behaviour rather than the limit itself.
    """
    await register(client)

    for _ in range(11):
        assert (await login(client)).status_code == 200


async def test_rate_limit_enforced_when_counter_available(client, monkeypatch) -> None:
    """With a working counter, the 11th login is a 429 carrying Retry-After."""
    counters: dict[str, int] = {}

    async def fake_incr(key: str, ttl_seconds: int) -> int:
        counters[key] = counters.get(key, 0) + 1
        return counters[key]

    from app.services import rate_limit

    monkeypatch.setattr(rate_limit.cache, "incr_with_expiry", fake_incr)

    await register(client)
    for _ in range(10):
        assert (await login(client)).status_code == 200

    response = await login(client)
    assert response.status_code == 429
    assert response.json()["code"] == "RATE_LIMITED"
    assert response.headers["Retry-After"] == "3600"
