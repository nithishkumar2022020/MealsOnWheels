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
from decimal import Decimal

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


# --- Restaurants ----------------------------------------------------------


class MenuItemResponse(ResponseModel):
    name: str
    # Decimal, not float: these are the prices Stage 11 sums into a NUMERIC
    # column that money is owed against.
    price: Decimal
    category: str


class RestaurantSearchResult(ResponseModel):
    id: int
    name: str
    lat: float
    lon: float
    distance_km: float
    # None, not 0, when nobody has rated it — an unrated restaurant, not a
    # zero-star one (docs/05_API_SPEC.md §6.1).
    composite_rating: Decimal | None = None
    avg_prep_time_minutes: int
    address: str | None = None
    # "local" for onboarded rows, "osm" for promoted POIs. Derived from whether
    # osm_id IS NULL, not stored separately.
    source: str


class RestaurantSearchResponse(ResponseModel):
    restaurants: list[RestaurantSearchResult]
    total_count: int
    cached: bool


class RestaurantDetailResponse(ResponseModel):
    id: int
    name: str
    phone: str
    address: str | None = None
    composite_rating: Decimal | None = None
    rating_count: int
    avg_prep_time_minutes: int
    menu: list[MenuItemResponse]


class RestaurantLoginRequest(RequestModel):
    phone: str = Field(pattern=PHONE_PATTERN, max_length=20)
    otp: str = Field(pattern=r"^\d{4,8}$")

    _normalise = field_validator("phone", mode="before")(normalise_phone)


class RestaurantLoginResponse(ResponseModel):
    """Token plus just enough context to render the dashboard header.

    `approval_status` and `onboarding_complete` are here because login succeeds
    while a listing is still pending — the client needs to know to show the
    onboarding checklist rather than an empty order queue, and "no orders" and
    "not live yet" look identical without it.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    restaurant_id: int
    restaurant_name: str
    staff_name: str | None = None
    phone: str
    approval_status: str
    is_accepting_orders: bool
    onboarding_complete: bool


class RestaurantRegisterRequest(RequestModel):
    name: str = Field(min_length=2, max_length=200)
    phone: str = Field(pattern=PHONE_PATTERN, max_length=20)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=500)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    avg_prep_time_minutes: int = Field(default=30, ge=1, le=240)

    _normalise = field_validator("phone", mode="before")(normalise_phone)


class RestaurantRegisterResponse(ResponseModel):
    id: int
    name: str
    phone: str
    address: str | None = None
    lat: float
    lon: float
    avg_prep_time_minutes: int
    # Always false on creation. Surfaced so the caller learns its submission is
    # pending review rather than assuming it is live and searchable.
    is_active: bool
