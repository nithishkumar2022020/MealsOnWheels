"""Restaurant staff login.

Mirrors `services/auth.py` — same OTP gate, same no-implicit-creation rule, same
enumeration-resistant ordering — but resolves a `restaurant_users` row instead of
a `users` row.

**Approval status does not gate login.** An owner whose listing is still pending,
or has been rejected, must be able to sign in: that is precisely when they need
to see why they are not live and fix it (docs/16_FUNCTIONAL_PRODUCT_DATA.md
section 4.1, the onboarding checklist). Approval gates *taking orders*, which is
enforced where orders are taken, not at the door.

Staff are created by an operator during onboarding. There is no self-service
registration here on purpose — anyone able to create their own staff row could
attach themselves to an existing restaurant and read its order queue.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import create_restaurant_access_token
from app.errors import not_found, unauthorized
from app.logging_config import mask_phone
from app.models import RestaurantUser
from app.services.auth import verify_otp

logger = logging.getLogger(__name__)


async def get_staff_by_phone(db: AsyncSession, phone: str) -> RestaurantUser | None:
    result = await db.execute(
        select(RestaurantUser)
        .where(RestaurantUser.phone == phone)
        .options(joinedload(RestaurantUser.restaurant))
    )
    return result.unique().scalar_one_or_none()


async def login_staff(db: AsyncSession, phone: str, otp: str) -> tuple[RestaurantUser, str, int]:
    """Verify the OTP for an existing staff member and issue a scoped token.

    Order matters, as in traveller login: the OTP is checked before the phone is
    looked up, so a caller without a valid OTP cannot use the 404/401 split to
    discover which numbers belong to restaurant staff.
    """
    verify_otp(phone, otp)

    staff = await get_staff_by_phone(db, phone)
    if staff is None:
        raise not_found(
            "No restaurant account exists for this phone number. "
            "Contact support to be added to a restaurant.",
            code="STAFF_NOT_FOUND",
        )

    if not staff.is_active:
        # Deliberately not a 403: a revoked account should look the same as a
        # wrong one, or the response confirms the number is real staff.
        raise unauthorized("Invalid credentials")

    token, expires_in = create_restaurant_access_token(
        restaurant_user_id=staff.id,
        phone=staff.phone,
        restaurant_id=staff.restaurant_id,
    )
    logger.info(
        "restaurant staff login",
        extra={
            "extra_fields": {
                "event": "restaurant_login",
                "phone": mask_phone(staff.phone),
                "restaurant_id": staff.restaurant_id,
            }
        },
    )
    return staff, token, expires_in
