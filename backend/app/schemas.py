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

from datetime import datetime, time
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)

# Imported rather than duplicated: the tuple is also the source of the
# database CHECK constraint, and two lists of the same three strings drift.
from app.models import BOOKING_TYPES

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
    # Included rather than filtered out: the client greys a sold-out dish. A
    # traveller who cannot find a dish they know assumes the app is broken.
    is_available: bool = True


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
    # Discoverable and bookable are different things. An OSM-promoted POI is
    # listed so a thin corridor does not look empty, but nobody onboarded it, so
    # it has no menu and no agreed prices and cannot take an order yet.
    is_bookable: bool
    # Machine-readable why-not, so the client can say "Opens at 6am" rather than
    # a generic "unavailable". None when is_bookable is true.
    unbookable_reason: str | None = None
    supported_booking_types: list[str] = Field(default_factory=list)


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


# --- Owner-managed menus --------------------------------------------------


class MenuItemCreate(RequestModel):
    name: str = Field(min_length=1, max_length=200)
    price: Decimal = Field(ge=0, le=Decimal("99999.99"), decimal_places=2)
    category: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=1000)
    # None means "use the restaurant's avg_prep_time_minutes" — the column is
    # nullable for exactly this, so an owner need not repeat the default per dish.
    prep_time_minutes: int | None = Field(default=None, ge=1, le=240)
    image_url: str | None = Field(default=None, max_length=2000)
    is_available: bool = True
    # Omitted means "append". An owner adding a dish should not have to know how
    # many they already have.
    display_order: int | None = Field(default=None, ge=0)


class MenuItemUpdate(RequestModel):
    """Every field optional — a PATCH-shaped body on a PUT route.

    `exclude_unset` in the service distinguishes "not sent" from "sent as null",
    so clearing a description is possible and leaving it alone is the default.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    price: Decimal | None = Field(default=None, ge=0, le=Decimal("99999.99"), decimal_places=2)
    category: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=1000)
    prep_time_minutes: int | None = Field(default=None, ge=1, le=240)
    image_url: str | None = Field(default=None, max_length=2000)
    is_available: bool | None = None
    display_order: int | None = Field(default=None, ge=0)


class AvailabilityUpdate(RequestModel):
    is_available: bool


class OwnerMenuItemResponse(ResponseModel):
    """The owner's view — everything, including soft state the traveller never sees."""

    id: int
    name: str
    description: str | None = None
    price: Decimal
    category: str
    prep_time_minutes: int | None = None
    is_available: bool
    image_url: str | None = None
    display_order: int


class OwnerMenuResponse(ResponseModel):
    items: list[OwnerMenuItemResponse]
    total_count: int


# --- Owner-managed hours --------------------------------------------------


class HoursWindow(RequestModel):
    # 0 = Monday, matching Python's datetime.weekday().
    weekday: int = Field(ge=0, le=6)
    opens_at: time
    closes_at: time

    @model_validator(mode="after")
    def _reject_zero_length(self) -> HoursWindow:
        # closes_at < opens_at is a legitimate overnight window (22:00-02:00);
        # equal is not — it describes a restaurant open for no time at all, which
        # is almost certainly a typo for "closed" (omit the day) or 24h.
        if self.opens_at == self.closes_at:
            raise ValueError(
                "opens_at and closes_at are identical. Omit the day to mark it closed."
            )
        return self


class HoursReplaceRequest(RequestModel):
    """The full weekly pattern. Omitted days are closed.

    An empty list is valid and means closed all week — which is why this replaces
    rather than merges.
    """

    windows: list[HoursWindow] = Field(default_factory=list, max_length=7)


class HoursWindowResponse(ResponseModel):
    weekday: int
    opens_at: time
    closes_at: time
    # Surfaced so a client rendering "22:00 – 02:00" knows the close belongs to
    # the following day rather than showing an apparently backwards range.
    is_overnight: bool


class HoursResponse(ResponseModel):
    hours: list[HoursWindowResponse]
    timezone: str


class AcceptingOrdersUpdate(RequestModel):
    is_accepting_orders: bool


class OnboardingResponse(ResponseModel):
    """What the owner still owes before the listing can go live.

    `approval_status` sits alongside deliberately: the checklist answers "is the
    ball in my court", and without the operator's decision next to it the owner
    cannot tell "I am done, waiting on review" from "I am done and live".
    """

    approval_status: str
    is_accepting_orders: bool
    onboarding_complete: bool
    missing: list[str]


# --- Bookings -------------------------------------------------------------


class BookingItemRequest(RequestModel):
    """One line of an order.

    **There is no `price` field, and that is the point.** `extra="forbid"` turns
    a client-sent price into a 422 rather than silently ignoring it — being
    ignored is the failure mode that lets a caller believe they set the price.
    The server resolves every unit price from `menu_items`.
    """

    name: str = Field(min_length=1, max_length=200)
    qty: int = Field(ge=1, le=99)


class BookingCreateRequest(RequestModel):
    restaurant_id: int = Field(ge=1)
    arrival_time: datetime
    # Required, never defaulted: it decides when food should be ready, and
    # guessing wrong means a bus passenger's order is plated for a sit-down.
    booking_type: str
    items: list[BookingItemRequest] = Field(min_length=1, max_length=50)
    route_id: int | None = Field(default=None, ge=1)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("booking_type")
    @classmethod
    def _known_booking_type(cls, v: str) -> str:
        if v not in BOOKING_TYPES:
            raise ValueError(f"booking_type must be one of {', '.join(BOOKING_TYPES)}")
        return v

    @field_validator("arrival_time")
    @classmethod
    def _timezone_aware(cls, v: datetime) -> datetime:
        # A naive datetime silently means "server local time" somewhere down the
        # stack, and every calculation here is UTC. Reject rather than assume.
        if v.tzinfo is None:
            raise ValueError(
                "arrival_time must include a timezone offset " "(e.g. 2026-08-05T07:30:00Z)"
            )
        return v


class BookingItemResponse(ResponseModel):
    name: str
    qty: int
    # The resolved unit price, frozen at order time. Echoed so the client can
    # render a priced order without holding an authoritative copy of the menu.
    price: Decimal
    # Plain integer, not a foreign key: a soft-deleted dish must not break a
    # historical order (docs/16_FUNCTIONAL_PRODUCT_DATA.md §3.1).
    menu_item_id: int | None = None


class BookingResponse(ResponseModel):
    id: int
    restaurant_id: int
    restaurant_name: str
    route_id: int | None = None
    booking_type: str
    status: str
    arrival_time: datetime
    cutoff_time: datetime
    # When the kitchen should have it plated. Differs from arrival by mode.
    ready_by: datetime
    items: list[BookingItemResponse]
    total_price: Decimal
    notes: str | None = None
    payment_status: str
    confirmed_at: datetime | None = None
    ready_at: datetime | None = None
    handed_over_at: datetime | None = None
    created_at: datetime


class BookingSummary(ResponseModel):
    """List view. Deliberately lighter than the detail response."""

    id: int
    restaurant_id: int
    restaurant_name: str
    booking_type: str
    status: str
    arrival_time: datetime
    cutoff_time: datetime
    total_price: Decimal
    # Pre-formatted for a list row ("2× Paneer Paratha, 1× Lassi") so the client
    # does not ship rendering logic to summarise an array it never displays.
    items_summary: str
    created_at: datetime


class BookingListResponse(ResponseModel):
    bookings: list[BookingSummary]
    total_count: int


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
