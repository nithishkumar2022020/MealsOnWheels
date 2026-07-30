"""Registration and OTP login.

The three behaviours here are Stage 4 security decisions
(docs/14_BUILD_PLAN.md section 4). Each one silently re-opens a hole if it drifts:

1. **Login never creates a user.** An unknown phone is a 404, not an implicit
   insert. Auto-register plus a constant OTP let anybody mint a 24-hour token for
   any phone number, including a real person's — that is account creation under
   someone else's identity, not a weak password.
2. **The stub OTP gates on `settings.otp_stub_allowed` and nothing else.** No
   SMS provider in production means 503, never a fallback to a value everybody
   knows.
3. **Duplicate registration is 409**, checked against the already-normalised
   phone so two spellings of one number cannot both be stored.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import create_access_token
from app.errors import conflict, not_found, service_unavailable, unauthorized
from app.logging_config import mask_phone
from app.models import User
from app.schemas import LoginRequest, RegisterRequest

logger = logging.getLogger(__name__)

# Development-only constant. Reachable only when settings.otp_stub_allowed is
# true, which is false whenever ENVIRONMENT == production.
STUB_OTP = "123456"


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    result = await db.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    """Create a user, or raise 409 if the phone is already taken."""
    existing = await get_user_by_phone(db, payload.phone)
    if existing is not None:
        raise conflict(
            "This phone number is already registered. Log in instead.",
            code="PHONE_ALREADY_REGISTERED",
        )

    user = User(
        phone=payload.phone,
        name=payload.name,
        email=str(payload.email) if payload.email else None,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # Lost the race against a concurrent registration of the same number.
        # The unique index is the real guard; the check above only produces a
        # nicer message in the common case.
        await db.rollback()
        raise conflict(
            "This phone number is already registered. Log in instead.",
            code="PHONE_ALREADY_REGISTERED",
        ) from None

    await db.refresh(user)
    logger.info(
        "user registered",
        extra={"extra_fields": {"event": "user_registered", "phone": mask_phone(user.phone)}},
    )
    return user


def verify_otp(phone: str, otp: str) -> None:
    """Check an OTP, or raise.

    Production has no SMS provider, so there is no OTP to verify against and the
    endpoint is a 503. It must never reach the comparison below.
    """
    settings = get_settings()

    if not settings.otp_stub_allowed:
        logger.warning(
            "login attempted with no OTP provider configured",
            extra={"extra_fields": {"event": "otp_unavailable", "phone": mask_phone(phone)}},
        )
        raise service_unavailable(
            "OTP delivery is not available. SMS verification is not yet configured."
        )

    if otp != STUB_OTP:
        raise unauthorized("Incorrect OTP", code="INVALID_OTP")


async def login(db: AsyncSession, payload: LoginRequest) -> tuple[User, str, int]:
    """Verify the OTP for an existing user and issue a token.

    Order matters: the OTP is checked before the phone is looked up, so a caller
    without a valid OTP cannot use the 404/401 split to enumerate which numbers
    are registered.
    """
    verify_otp(payload.phone, payload.otp)

    user = await get_user_by_phone(db, payload.phone)
    if user is None:
        raise not_found(
            "No account exists for this phone number. Register first.",
            code="USER_NOT_FOUND",
        )

    token, expires_in = create_access_token(user_id=user.id, phone=user.phone)
    logger.info(
        "login succeeded",
        extra={"extra_fields": {"event": "login", "phone": mask_phone(user.phone)}},
    )
    return user, token, expires_in
