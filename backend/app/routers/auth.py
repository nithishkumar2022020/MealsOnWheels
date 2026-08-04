"""Auth routes: register and OTP login.

Thin by design — the security-relevant decisions live in app/services/auth.py so
they are testable without an HTTP layer and cannot be quietly different between
two routes.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.deps import ClientIp, DbSession
from app.schemas import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
    UserSummary,
)
from app.services import auth as auth_service
from app.services import rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbSession, ip: ClientIp) -> UserResponse:
    """Create a user account. No auth required.

    Rate limited per IP: there is no account to key on yet.
    """
    limit, window = rate_limit.REGISTER_LIMIT
    await rate_limit.enforce(rate_limit.register_key(ip), limit, window)

    user = await auth_service.register_user(db, payload)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: DbSession) -> LoginResponse:
    """Verify an OTP and return a JWT.

    Rate limited per phone rather than per IP, so one number cannot be
    brute-forced from many addresses. Best-effort: see app/services/rate_limit.py
    for why it fails open.
    """
    limit, window = rate_limit.LOGIN_LIMIT
    await rate_limit.enforce(rate_limit.login_key(payload.phone), limit, window)

    user, token, expires_in = await auth_service.login(db, payload)
    return LoginResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserSummary.model_validate(user),
    )
