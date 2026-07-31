"""Pydantic request and response models.

Two rules apply to everything in this file.

**Requests forbid unknown fields.** `extra="forbid"` is what makes the Stage 11
promise real: a client that sends a `price` on a booking line gets a 422, rather
than having it silently ignored and being left to believe the server honoured it.
Ignoring an unexpected field is the failure mode that lets a caller think it set
a price.

**Responses are explicit.** A raw SQLAlchemy model is never returned, so adding a
column cannot accidentally publish it.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# E.164: leading +, no leading zero on the country code, 7–15 digits total.
PHONE_PATTERN = r"^\+[1-9]\d{6,14}$"

# Separators people actually type. Removed before the pattern is applied, so
# "+91 98765-43210" is accepted and stored identically to "+919876543210"
# rather than becoming a second row for the same person.
_PHONE_SEPARATORS = str.maketrans({" ": None, "-": None, "(": None, ")": None, ".": None})


def normalise_phone(value: object) -> object:
    """Reduce a typed phone to canonical E.164. Non-strings pass through."""
    if not isinstance(value, str):
        return value
    return value.strip().translate(_PHONE_SEPARATORS)


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth -----------------------------------------------------------------


class RegisterRequest(RequestModel):
    phone: str = Field(pattern=PHONE_PATTERN, max_length=20)
    name: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None

    _normalise = field_validator("phone", mode="before")(normalise_phone)

    @field_validator("name")
    @classmethod
    def _blank_name_is_absent(cls, v: str | None) -> str | None:
        # "   " has already been stripped to "" by str_strip_whitespace; storing
        # it would make `name` present-but-empty, which every reader then has to
        # special-case alongside NULL.
        return v or None


class LoginRequest(RequestModel):
    phone: str = Field(pattern=PHONE_PATTERN, max_length=20)
    # Not `int`: OTPs are digit strings and a leading zero is significant.
    otp: str = Field(pattern=r"^\d{4,8}$")

    _normalise = field_validator("phone", mode="before")(normalise_phone)


class UserResponse(ResponseModel):
    id: int
    phone: str
    name: str | None = None
    email: str | None = None
    created_at: datetime


class UserSummary(ResponseModel):
    """Trimmed user, embedded in the login response."""

    id: int
    phone: str
    name: str | None = None


class LoginResponse(ResponseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserSummary


# --- Routes ---------------------------------------------------------------


class RouteResponse(ResponseModel):
    """A route with its endpoints flattened to scalar lat/lon.

    The database stores `origin_point` / `dest_point` as GEOGRAPHY(POINT, 4326);
    the API flattens both so clients never parse WKB (docs/05_API_SPEC.md §5.1).

    `geometry` is deliberately absent. The polyline is internal — corridor search
    uses it server-side (Stage 16) and sending it would put a payload orders of
    magnitude larger than the rest of the response on every list request.
    """

    id: int
    name: str
    origin_name: str
    dest_name: str
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float
    distance_km: int | None = None


class RouteListResponse(ResponseModel):
    routes: list[RouteResponse]
    total_count: int
