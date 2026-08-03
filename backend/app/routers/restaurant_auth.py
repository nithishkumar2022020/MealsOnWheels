"""Restaurant staff login.

Separate router from `routers/auth.py` under `/api/restaurant/auth` so the two
actors' endpoints cannot be confused for one another in a URL, a log line, or a
rate-limit key.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.deps import DbSession
from app.schemas import RestaurantLoginRequest, RestaurantLoginResponse
from app.services import rate_limit
from app.services import restaurant_auth as staff_auth
from app.services.onboarding import onboarding_status

router = APIRouter(prefix="/api/restaurant/auth", tags=["restaurant-auth"])


@router.post("/login", response_model=RestaurantLoginResponse)
async def login(payload: RestaurantLoginRequest, db: DbSession) -> RestaurantLoginResponse:
    """Verify an OTP and return a token scoped to one restaurant.

    Succeeds while the listing is still pending or rejected: that is exactly when
    an owner needs to sign in and see why. The response carries
    `approval_status` and `onboarding_complete` so the client can show the
    checklist instead of an empty order queue.
    """
    limit, window = rate_limit.LOGIN_LIMIT
    # Keyed separately from traveller login. Sharing the key would let attempts
    # against a traveller account consume a restaurant's budget, and one number
    # can legitimately be both.
    await rate_limit.enforce(f"ratelimit:restaurant-login:{payload.phone}", limit, window)

    staff, token, expires_in = await staff_auth.login_staff(db, payload.phone, payload.otp)
    status = await onboarding_status(db, staff.restaurant)

    return RestaurantLoginResponse(
        access_token=token,
        expires_in=expires_in,
        restaurant_id=staff.restaurant_id,
        restaurant_name=staff.restaurant.name,
        staff_name=staff.name,
        phone=staff.phone,
        approval_status=staff.restaurant.approval_status,
        is_accepting_orders=staff.restaurant.is_accepting_orders,
        onboarding_complete=status.is_complete,
    )
