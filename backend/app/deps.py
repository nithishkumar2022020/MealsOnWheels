"""Shared FastAPI dependencies.

`get_current_user` and `get_current_staff` are the only places a JWT becomes an
actor. Handlers receive a loaded row, never a token or a raw claim, so no handler
can forget to check that the subject still exists.

The two are deliberately separate functions rather than one parameterised by
actor type. A single dependency would make "which actor is this endpoint for" a
value passed at the call site, and the failure mode of getting that wrong is
silent: a restaurant endpoint that accepts traveller tokens looks identical in
review to one that does not.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.security import (
    ACTOR_RESTAURANT,
    ACTOR_TRAVELLER,
    TokenExpired,
    TokenInvalid,
    decode_token,
)
from app.db import get_db
from app.errors import unauthorized
from app.models import RestaurantUser, User


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise unauthorized("Missing Authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthorized("Authorization header must be 'Bearer <token>'")

    return token.strip()


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Resolve `Authorization: Bearer <jwt>` to the traveller it names.

    Expired token -> 401 TOKEN_EXPIRED, so a client can tell "log in again" apart
    from "this request was never going to work". Everything else, including a
    valid token for a deleted user and a well-formed restaurant token, is an
    indistinguishable 401 UNAUTHORIZED — a caller probing tokens learns nothing
    about which accounts exist or what kind they hold.
    """
    token = _bearer_token(authorization)

    try:
        claims = decode_token(token, expected_actor=ACTOR_TRAVELLER)
    except TokenExpired:
        raise unauthorized("Token has expired", code="TOKEN_EXPIRED") from None
    except TokenInvalid:
        raise unauthorized("Invalid token") from None

    user = await db.get(User, claims.subject_id)
    if user is None:
        raise unauthorized("Invalid token")

    return user


async def get_current_staff(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> RestaurantUser:
    """Resolve a token to the member of restaurant staff it names.

    The returned row carries `restaurant_id`, and **that** is what every
    restaurant endpoint scopes on — never a query parameter, and never the `rid`
    claim. Reading it from the freshly loaded row means a staff member who has
    been moved between outlets, or deactivated, cannot keep acting on a token
    issued before the change.

    The restaurant is eager-loaded because every caller needs it, and a lazy load
    on an async session raises rather than quietly issuing a second query.
    """
    token = _bearer_token(authorization)

    try:
        claims = decode_token(token, expected_actor=ACTOR_RESTAURANT)
    except TokenExpired:
        raise unauthorized("Token has expired", code="TOKEN_EXPIRED") from None
    except TokenInvalid:
        raise unauthorized("Invalid token") from None

    staff = await db.get(
        RestaurantUser,
        claims.subject_id,
        options=[joinedload(RestaurantUser.restaurant)],
    )
    if staff is None or not staff.is_active:
        # Deactivating staff revokes access immediately rather than at token
        # expiry, which is the point of having the flag.
        raise unauthorized("Invalid token")

    return staff


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentStaff = Annotated[RestaurantUser, Depends(get_current_staff)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


def client_ip(request: Request) -> str:
    """Best-effort caller IP for IP-keyed rate limits.

    `X-Forwarded-For` is trusted only because Render terminates TLS and appends
    the real client. It is spoofable in general, which is why it keys a
    best-effort rate limit and nothing that grants access.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


ClientIp = Annotated[str, Depends(client_ip)]
