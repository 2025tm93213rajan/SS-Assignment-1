from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from src.database import Base

class PnrRecord(Base):
    __tablename__ = "pnr_records"

    pnr = Column(String(32), primary_key=True)
    booking_id = Column(String(64), nullable=False, index=True)
    quota_id = Column(String(64), nullable=False, index=True)
    event_name = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="ISSUED")  # ISSUED, CANCELLED
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tickets = relationship(
        "IssuedTicket", 
        back_populates="pnr_record", 
        cascade="all, delete-orphan",
        order_by="IssuedTicket.created_at"
    )


class IssuedTicket(Base):
    __tablename__ = "issued_tickets"

    ticket_id = Column(String(64), primary_key=True)
    pnr = Column(String(32), ForeignKey("pnr_records.pnr", ondelete="CASCADE"), nullable=False)
    passenger_name = Column(String(128), nullable=False)
    berth_number = Column(String(32), nullable=False)
    berth_type = Column(String(32), nullable=False)  # LOWER, MIDDLE, UPPER, WINDOW, AISLE, VIP_ARENA
    barcode_token = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    pnr_record = relationship("PnrRecord", back_populates="tickets")

    __table_args__ = (
        Index("idx_pnr_ticket", "pnr", "ticket_id"),
    )
