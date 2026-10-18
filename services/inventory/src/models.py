from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from src.database import Base

class EventTrip(Base):
    __tablename__ = "events_trips"

    id = Column(String(64), primary_key=True)
    title = Column(String(255), nullable=False)
    category = Column(String(64), nullable=False)  # RAILWAY_TATKAL, CONCERT_EVENT, EXPRESS_BUS
    origin = Column(String(128), nullable=True)
    destination = Column(String(128), nullable=True)
    departure_time = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    quotas = relationship("Quota", back_populates="event", cascade="all, delete-orphan")


class Quota(Base):
    __tablename__ = "quotas"

    id = Column(String(64), primary_key=True)  # e.g., "TATKAL-12951-B1", "COLDPLAY-VIP-A1"
    event_id = Column(String(64), ForeignKey("events_trips.id", ondelete="CASCADE"), nullable=False)
    tier_name = Column(String(128), nullable=False)
    total_capacity = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    event = relationship("EventTrip", back_populates="quotas")
    inventory = relationship("SeatInventory", back_populates="quota", uselist=False, cascade="all, delete-orphan")


class SeatInventory(Base):
    __tablename__ = "seat_inventories"

    quota_id = Column(String(64), ForeignKey("quotas.id", ondelete="CASCADE"), primary_key=True)
    total_capacity = Column(Integer, nullable=False)
    available = Column(Integer, nullable=False)
    locked = Column(Integer, nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)  # Optimistic concurrency version
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    quota = relationship("Quota", back_populates="inventory")

    __table_args__ = (
        Index("idx_inventory_available", "quota_id", "available"),
    )


class Reservation(Base):
    __tablename__ = "reservations"

    id = Column(String(64), primary_key=True)
    reservation_token = Column(String(64), unique=True, nullable=False, index=True)
    quota_id = Column(String(64), ForeignKey("quotas.id", ondelete="CASCADE"), nullable=False)
    booking_id = Column(String(64), nullable=True, index=True)
    quantity = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="HELD")  # HELD, CONFIRMED, RELEASED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=True)
