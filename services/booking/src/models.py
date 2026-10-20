from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Numeric, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from src.database import Base

class Booking(Base):
    __tablename__ = "bookings"

    booking_id = Column(String(64), primary_key=True, index=True)
    quota_id = Column(String(64), nullable=False, index=True)
    event_name = Column(String(128), nullable=False)
    category = Column(String(32), nullable=False, default="RAILWAY_TATKAL")
    passenger_count = Column(Integer, nullable=False, default=1)
    total_amount = Column(Numeric(10, 2), nullable=False)
    
    # States: PENDING, RESERVED, PAID, TICKETED, CONFIRMED, FAILED_INVENTORY, FAILED_PAYMENT, FAILED_TICKETING, FAILED_COMPENSATED, CANCELLED
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    
    # Downstream foreign identifiers
    reservation_id = Column(String(64), nullable=True)
    payment_id = Column(String(64), nullable=True)
    pnr = Column(String(32), nullable=True, index=True)
    
    # Customer Info
    customer_name = Column(String(128), nullable=False)
    customer_email = Column(String(128), nullable=False)
    customer_phone = Column(String(32), nullable=False)
    
    # Compensation / Failure details
    compensation_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc), 
        nullable=False
    )

    steps = relationship("SagaStepLog", back_populates="booking", cascade="all, delete-orphan", order_by="SagaStepLog.timestamp")

class SagaStepLog(Base):
    __tablename__ = "saga_step_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(String(64), ForeignKey("bookings.booking_id", ondelete="CASCADE"), nullable=False, index=True)
    step_name = Column(String(64), nullable=False) # e.g. INVENTORY_RESERVE, PAYMENT_CHARGE, TICKETING_ISSUE, NOTIFICATION_PUBLISH, COMPENSATION_INVENTORY_RELEASE
    status = Column(String(32), nullable=False)    # SUCCESS, FAILED, COMPENSATED
    request_payload = Column(Text, nullable=True)
    response_payload = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    booking = relationship("Booking", back_populates="steps")
