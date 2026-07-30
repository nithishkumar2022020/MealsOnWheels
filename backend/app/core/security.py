"""JWT creation and decoding.

HS256 with the claims fixed by docs/10_SECURITY.md section 3.2: `sub`, `phone`,
`iat`, `exp` and nothing else. Extra claims are not free — anything put in a JWT
is readable by the client, so the token carries an identifier and the identity
it was issued for, and the database supplies the rest.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import ExpiredSignatureError, JWTError, jwt

from app.config import get_settings

ALGORITHM = "HS256"


class TokenExpired(Exception):
    """Signature was valid but `exp` has passed — distinct from malformed."""


class TokenInvalid(Exception):
    """Malformed, wrongly signed, or missing a required claim."""


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    phone: str


def create_access_token(user_id: int, phone: str) -> tuple[str, int]:
    """Return `(token, expires_in_seconds)`.

    `expires_in` is returned alongside rather than left for the client to derive
    from `exp`: the login response advertises it, and a client should not have
    to decode a token it is only meant to carry.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    expires_in = settings.JWT_EXPIRE_HOURS * 3600
    claims = {
        # String, not int. python-jose rejects a non-string `sub` on decode,
        # so an int here produces tokens that cannot be read back.
        "sub": str(user_id),
        "phone": phone,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    token = jwt.encode(claims, settings.JWT_SECRET, algorithm=ALGORITHM)
    return token, expires_in


def decode_token(token: str) -> TokenClaims:
    """Verify and unpack a token.

    Raises TokenExpired or TokenInvalid; the caller maps those to the two
    distinct 401 codes the API contract promises.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except ExpiredSignatureError as exc:
        raise TokenExpired() from exc
    except JWTError as exc:
        raise TokenInvalid() from exc

    subject = payload.get("sub")
    phone = payload.get("phone")
    if not subject or not phone:
        # A correctly signed token that is missing claims means the signing key
        # is shared with something that is not this application.
        raise TokenInvalid()

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise TokenInvalid() from exc

    return TokenClaims(user_id=user_id, phone=phone)
