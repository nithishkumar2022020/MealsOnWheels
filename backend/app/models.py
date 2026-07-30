"""SQLAlchemy ORM models.

These mirror backend/migrations/001_create_tables.sql exactly. The SQL file is
the source of truth for the schema; if the two disagree, the SQL is right and
this file is the bug.
"""

from __future__ import annotations

from datetime import datetime
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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
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
        Index("idx_restaurants_location", "location", postgresql_using="gist"),
        Index(
            "idx_restaurants_active",
            "is_active",
            postgresql_where=text("is_active = true"),
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
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    @property
    def is_from_osm(self) -> bool:
        return self.osm_id is not None


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
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # Unit prices resolved server-side and frozen here, so a later menu price
    # change cannot retroactively alter a placed order.
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
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
