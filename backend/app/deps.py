"""Shared FastAPI dependencies.

`get_current_user` is the only place a JWT is turned into a user. Handlers
receive a `User` row, never a token or a raw claim, so no handler can forget to
check that the subject still exists.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenExpired, TokenInvalid, decode_token
from app.db import get_db
from app.errors import unauthorized
from app.models import User


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Resolve `Authorization: Bearer <jwt>` to the user row it names.

    Expired token -> 401 TOKEN_EXPIRED, so a client can tell "log in again"
    apart from "this request was never going to work". Everything else,
    including a valid token for a deleted user, is an indistinguishable 401
    UNAUTHORIZED — a caller probing tokens learns nothing about which users
    exist.
    """
    if not authorization:
        raise unauthorized("Missing Authorization header")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise unauthorized("Authorization header must be 'Bearer <token>'")

    try:
        claims = decode_token(token.strip())
    except TokenExpired:
        raise unauthorized("Token has expired", code="TOKEN_EXPIRED") from None
    except TokenInvalid:
        raise unauthorized("Invalid token") from None

    user = await db.get(User, claims.user_id)
    if user is None:
        raise unauthorized("Invalid token")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
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
