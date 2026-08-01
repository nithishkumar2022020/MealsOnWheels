"""SQLAlchemy ORM models.

These mirror the files in backend/migrations/ exactly. The SQL is the source of
truth for the schema; if the two disagree, the SQL is right and this file is the
bug.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geography, Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# Booking lifecycle. Terminal states accept no further transitions.
BOOKING_STATUSES = ("pending", "confirmed", "ready", "handed_over", "cancelled")

# The only legal moves. Everything absent here is a 400, including reversals.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"ready", "cancelled"},
    "ready": {"handed_over", "cancelled"},
    "handed_over": set(),
    "cancelled": set(),
}

# Fulfilment modes. Three products sharing an order flow, not three labels.
BOOKING_TYPES = ("bus_boarding_point", "self_drive_dine", "self_drive_takeaway")

# How far before stated arrival food should be ready, per mode.
#
# Dine-in is deliberately 0: a family who booked a table has to park and walk in,
# so food plated five minutes early is food that sits and cools. A bus passenger
# with a twenty-minute halt is the opposite — the handover is the whole
# transaction and late is a total failure.
READY_BEFORE_ARRIVAL_MINUTES: dict[str, int] = {
    "bus_boarding_point": 5,
    "self_drive_takeaway": 5,
    "self_drive_dine": 0,
}

# Listing lifecycle, set by ops. Distinct from "open right now".
APPROVAL_STATUSES = ("pending", "approved", "rejected")



class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    bookings: Mapped[list[Booking]] = relationship(back_populates="user")


class Restaurant(Base):
    __tablename__ = "restaurants"
    __table_args__ = (
        CheckConstraint(
            "composite_rating >= 0 AND composite_rating <= 5",
            name="ck_restaurants_rating_range",
        ),
        CheckConstraint("rating_count >= 0", name="ck_restaurants_rating_count_nonneg"),
        CheckConstraint("avg_prep_time_minutes > 0", name="ck_restaurants_prep_time_positive"),
        CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected')",
            name="ck_restaurants_approval_status",
        ),
        Index("idx_restaurants_location", "location", postgresql_using="gist"),
        Index(
            "idx_restaurants_active",
            "is_active",
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "idx_restaurants_bookable",
            "approval_status",
            "is_accepting_orders",
            postgresql_where=text("approval_status = 'approved' AND is_accepting_orders = true"),
        ),
        Index(
            "idx_restaurants_osm_id",
            "osm_id",
            unique=True,
            postgresql_where=text("osm_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Empty for OSM-derived rows — nobody was onboarded, so there is no contact.
    phone: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    # Mean across all three rating dimensions. 0 means unrated; the API reports
    # null so clients do not render a zero-star rating for a new restaurant.
    composite_rating: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("0")
    )
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Drives the cutoff calculation AND the minimum booking lead time.
    avg_prep_time_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    # DEPRECATED — mirrors approval_status == "approved". Kept for one release so
    # a rollback does not break search; use is_bookable_now() instead.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Ops decision on the listing. Changes ~never.
    approval_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    # Owner toggle from the kitchen tablet. Changes several times a day. Kept
    # separate from approval_status because tapping "Closed" at the end of a
    # shift must not look like an unapproved listing.
    is_accepting_orders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Load-bearing: "is 07:30 UTC inside Monday 06:00-23:00" is unanswerable
    # without knowing the restaurant's own zone.
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="Asia/Kolkata")
    supported_booking_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list(BOOKING_TYPES)
    )
    # Set when promoted from an OpenStreetMap POI; NULL when onboarded manually.
    osm_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    bookings: Mapped[list[Booking]] = relationship(back_populates="restaurant")
    menu_items: Mapped[list[MenuItem]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )
    hours: Mapped[list[RestaurantHours]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )
    staff: Mapped[list[RestaurantUser]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )

    @property
    def is_from_osm(self) -> bool:
        return self.osm_id is not None

    @property
    def is_approved(self) -> bool:
        return self.approval_status == "approved"

    def supports_booking_type(self, booking_type: str) -> bool:
        return booking_type in (self.supported_booking_types or ())


class Route(Base):
    __tablename__ = "routes"
    __table_args__ = (Index("idx_routes_geometry", "geometry", postgresql_using="gist"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    origin_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dest_name: Mapped[str] = mapped_column(String(100), nullable=False)
    origin_point: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    dest_point: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    # Generated offline by OSRM at seed time; production never calls OSRM.
    geometry: Mapped[Any | None] = mapped_column(Geometry(geometry_type="LINESTRING", srid=4326))
    distance_km: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'ready', 'handed_over', 'cancelled')",
            name="ck_bookings_status",
        ),
        CheckConstraint("payment_status IN ('pending', 'paid')", name="ck_bookings_payment_status"),
        CheckConstraint("total_price >= 0", name="ck_bookings_total_nonneg"),
        CheckConstraint(
            "booking_type IN ('bus_boarding_point', 'self_drive_dine', 'self_drive_takeaway')",
            name="ck_bookings_booking_type",
        ),
        Index("idx_bookings_restaurant_status", "restaurant_id", "status"),
        Index("idx_bookings_user", "user_id"),
        Index(
            "idx_bookings_cutoff",
            "cutoff_time",
            postgresql_where=text("status IN ('pending', 'confirmed')"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id"), nullable=False
    )
    route_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("routes.id"))
    # When the traveller expects to ARRIVE — every time calculation derives
    # from this. Named booking_time originally, which read as a creation stamp.
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cutoff_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Which of the three fulfilment modes. Changes how ready_by is computed and
    # how urgently the dashboard should surface the order.
    booking_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="self_drive_takeaway"
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Unit prices resolved server-side and frozen here, so a later menu price
    # change cannot retroactively alter a placed order.
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Lifecycle stamps. updated_at only records the most recent change, so
    # without these the charter's north-star metric — ready within +/-10 min of
    # stated arrival — cannot be computed at all.
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handed_over_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped[User] = relationship(back_populates="bookings")
    restaurant: Mapped[Restaurant] = relationship(back_populates="bookings")
    rating: Mapped[Rating | None] = relationship(back_populates="booking")

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in ALLOWED_TRANSITIONS.get(self.status, set())

    @property
    def ready_by(self) -> datetime:
        """When food should be ready, which depends on the fulfilment mode.

        Dine-in resolves to the arrival time itself: a family who booked a table
        still has to park and walk in, so food plated early sits and cools.
        """
        minutes = READY_BEFORE_ARRIVAL_MINUTES.get(self.booking_type, 5)
        return self.arrival_time - timedelta(minutes=minutes)


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint("hygiene_score BETWEEN 1 AND 5", name="ck_ratings_hygiene"),
        CheckConstraint("food_quality_score BETWEEN 1 AND 5", name="ck_ratings_food_quality"),
        CheckConstraint("timeliness_score BETWEEN 1 AND 5", name="ck_ratings_timeliness"),
        Index("idx_ratings_restaurant", "restaurant_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # UNIQUE: one rating per booking, enforced by the database rather than by
    # an application check that races under concurrent submits.
    booking_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bookings.id"), nullable=False, unique=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id"), nullable=False
    )
    hygiene_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    food_quality_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    timeliness_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    booking: Mapped[Booking] = relationship(back_populates="rating")

    @property
    def composite_score(self) -> float:
        return (self.hygiene_score + self.food_quality_score + self.timeliness_score) / 3


class BusGpsEvent(Base):
    """Reserved for the Phase 3 ETA model.

    Nothing reads or writes this in MVP (ADR-0010). It exists so that turning
    the feature on later is not a migration.
    """

    __tablename__ = "bus_gps_events"
    __table_args__ = (Index("idx_gps_route_time", "route_id", "recorded_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    route_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("routes.id"))
    vehicle_id: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[Any] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RestaurantUser(Base):
    """A person who can act for a restaurant.

    Neither the frontend design nor the original backend modelled this: the
    design's restaurant login returns a `restaurant_id` without saying what
    authenticates against it, and `restaurants.phone` is a contact number, not an
    identity. One row per person means a dhaba with an owner *and* a manager
    needs no migration later.
    """

    __tablename__ = "restaurant_users"
    __table_args__ = (Index("idx_restaurant_users_restaurant", "restaurant_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id"), nullable=False
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(100))
    # Revokes access without deleting the row, so an ex-manager's history stays
    # attributable.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    restaurant: Mapped[Restaurant] = relationship(back_populates="staff")


class MenuItem(Base):
    """A dish an owner maintains.

    Replaces the hardcoded tables in `app/services/menu.py`. Moving prices from a
    Python constant to a row does **not** move the trust boundary: they are still
    resolved server-side and frozen onto the booking line at order time, and a
    client still cannot propose one.
    """

    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_menu_items_price_nonneg"),
        CheckConstraint(
            "prep_time_minutes IS NULL OR prep_time_minutes > 0",
            name="ck_menu_items_prep_positive",
        ),
        Index(
            "idx_menu_items_restaurant",
            "restaurant_id",
            "display_order",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "idx_menu_items_unique_live_name",
            "restaurant_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    # NULL means "use the restaurant's avg_prep_time_minutes".
    prep_time_minutes: Mapped[int | None] = mapped_column(Integer)
    # Today's stock, separate from deleted_at. "Out of paneer" and "we stopped
    # selling this" are different actions with different reversibility.
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    image_url: Mapped[str | None] = mapped_column(Text)
    # The owner's ordering — alphabetical would put Beverage before Main.
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    restaurant: Mapped[Restaurant] = relationship(back_populates="menu_items")

    @property
    def is_live(self) -> bool:
        return self.deleted_at is None

    @property
    def is_orderable(self) -> bool:
        """Live and in stock. Unavailable items are still shown, greyed out."""
        return self.deleted_at is None and self.is_available


class RestaurantHours(Base):
    """Opening window for one weekday.

    An absent row means **closed**, not open-all-day: a newly approved
    restaurant that has not set hours must not silently accept 3am orders.

    `closes_at < opens_at` expresses an overnight window (22:00-02:00) rather
    than being invalid — highway dhabas routinely run past midnight.
    """

    __tablename__ = "restaurant_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_restaurant_hours_weekday"),
    )

    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id"), primary_key=True
    )
    # 0 = Monday, matching Python's datetime.weekday().
    weekday: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    opens_at: Mapped[time] = mapped_column(Time, nullable=False)
    closes_at: Mapped[time] = mapped_column(Time, nullable=False)

    restaurant: Mapped[Restaurant] = relationship(back_populates="hours")

    @property
    def is_overnight(self) -> bool:
        return self.closes_at < self.opens_at

    def covers(self, at: time) -> bool:
        """Whether a local wall-clock time falls inside this window."""
        if self.is_overnight:
            # 22:00-02:00 means "at or after 22:00, or before 02:00".
            return at >= self.opens_at or at < self.closes_at
        return self.opens_at <= at < self.closes_at
