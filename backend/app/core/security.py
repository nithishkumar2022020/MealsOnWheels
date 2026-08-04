"""JWT creation and decoding.

HS256 with the claims fixed by docs/10_SECURITY.md section 3.2: `sub`, `phone`,
`iat`, `exp`, plus `typ` and — for restaurant staff — `rid`. Extra claims are not
free, since anything in a JWT is readable by the client, so the token carries an
identifier and the identity it was issued for and the database supplies the rest.

**`typ` is a security boundary, not a label.** Two actors now authenticate against
the same secret: travellers and restaurant staff. Without an actor claim, a
traveller's token and a staff token are byte-indistinguishable once decoded — both
are "a signed integer and a phone number". A traveller whose `id` happened to
match a `restaurant_users.id` could then present their own perfectly valid token
to a restaurant endpoint and be accepted as staff. The two ID spaces are
independent sequences, so that collision is not unlikely; it is the common case
for low IDs.

Every decode therefore states which actor it expects, and a mismatch is rejected
before the subject is looked up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import ExpiredSignatureError, JWTError, jwt

from app.config import get_settings

ALGORITHM = "HS256"

# Actor types. The value goes in the `typ` claim.
ACTOR_TRAVELLER = "traveller"
ACTOR_RESTAURANT = "restaurant"


class TokenExpired(Exception):
    """Signature was valid but `exp` has passed — distinct from malformed."""


class TokenInvalid(Exception):
    """Malformed, wrongly signed, missing a claim, or issued for another actor."""


@dataclass(frozen=True)
class TokenClaims:
    subject_id: int
    phone: str
    actor: str
    # Present only for restaurant staff. Convenience for the client and for
    # logging — authorization is always derived from the freshly loaded row, not
    # from this, so a staff member moved between outlets cannot act on a stale
    # token.
    restaurant_id: int | None = None


def _encode(claims: dict[str, object]) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_in = settings.JWT_EXPIRE_HOURS * 3600
    payload = {
        **claims,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM), expires_in


def create_access_token(user_id: int, phone: str) -> tuple[str, int]:
    """Token for a traveller. Returns `(token, expires_in_seconds)`.

    `expires_in` is returned alongside rather than left for the client to derive
    from `exp`: the login response advertises it, and a client should not have to
    decode a token it is only meant to carry.
    """
    return _encode(
        {
            # String, not int. python-jose rejects a non-string `sub` on decode,
            # so an int here produces tokens that cannot be read back.
            "sub": str(user_id),
            "phone": phone,
            "typ": ACTOR_TRAVELLER,
        }
    )


def create_restaurant_access_token(
    restaurant_user_id: int, phone: str, restaurant_id: int
) -> tuple[str, int]:
    """Token for a member of restaurant staff.

    `sub` is the `restaurant_users.id`, not the restaurant — a token identifies a
    person, and two people at one dhaba need distinguishable tokens for the audit
    trail to mean anything.
    """
    return _encode(
        {
            "sub": str(restaurant_user_id),
            "phone": phone,
            "typ": ACTOR_RESTAURANT,
            "rid": restaurant_id,
        }
    )


def decode_token(token: str, *, expected_actor: str) -> TokenClaims:
    """Verify and unpack a token issued for `expected_actor`.

    `expected_actor` is required rather than defaulted. A default would make the
    safe call and the dangerous call look identical at the call site, and the
    dangerous one is the one that gets written by accident.

    Raises TokenExpired or TokenInvalid; the caller maps those to the two distinct
    401 codes the API contract promises.
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
    actor = payload.get("typ")

    if not subject or not phone or not actor:
        # A correctly signed token missing claims means the signing key is shared
        # with something that is not this application.
        raise TokenInvalid()

    if actor != expected_actor:
        # A traveller token presented to a restaurant endpoint, or the reverse.
        # Indistinguishable from any other 401 to the caller: telling them the
        # token was valid but for the wrong role confirms the token is real.
        raise TokenInvalid()

    try:
        subject_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise TokenInvalid() from exc

    restaurant_id: int | None = None
    if actor == ACTOR_RESTAURANT:
        raw_rid = payload.get("rid")
        try:
            restaurant_id = int(raw_rid)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise TokenInvalid() from exc

    return TokenClaims(
        subject_id=subject_id,
        phone=phone,
        actor=actor,
        restaurant_id=restaurant_id,
    )
