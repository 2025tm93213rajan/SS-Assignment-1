from datetime import datetime
from typing import List, Optional, Any
from pydantic import BaseModel, Field

class PassengerInfo(BaseModel):
    name: str = Field(..., min_length=1, description="Full passenger name")
    berth_preference: Optional[str] = Field("LOWER", description="Berth/Seat preference (LOWER, MIDDLE, UPPER, VIP)")

class PaymentInfo(BaseModel):
    payment_method: Optional[str] = Field("CARD", description="Payment instrument")
    card_number: Optional[str] = Field("4000-0000-0000-0001", description="Test card number (ends in 0002 to simulate decline)")
    force_failure: Optional[bool] = Field(False, description="Simulate payment gateway failure for saga rollback")
    delay_ms: Optional[int] = Field(0, description="Injected chaos latency")

class CreateBookingRequest(BaseModel):
    quota_id: str = Field(..., description="Target inventory quota identifier")
    event_name: str = Field(..., description="Train number, concert tour, or bus route name")
    category: Optional[str] = Field("RAILWAY_TATKAL", description="Booking domain category")
    passengers: List[PassengerInfo] = Field(..., min_length=1, description="List of passengers")
    total_amount: float = Field(..., gt=0, description="Total reservation price in INR")
    customer_name: str = Field(..., min_length=1)
    customer_email: str = Field(..., min_length=3)
    customer_phone: str = Field(..., min_length=8)
    payment: Optional[PaymentInfo] = Field(default_factory=PaymentInfo)
    idempotency_key: Optional[str] = Field(None, description="Optional client idempotency key")

class SagaStepDetail(BaseModel):
    step_name: str
    status: str
    error_message: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

class BookingResponse(BaseModel):
    booking_id: str
    quota_id: str
    event_name: str
    category: str
    passenger_count: int
    total_amount: float
    status: str
    reservation_id: Optional[str] = None
    payment_id: Optional[str] = None
    pnr: Optional[str] = None
    customer_name: str
    customer_email: str
    customer_phone: str
    compensation_reason: Optional[str] = None
    steps: List[SagaStepDetail] = []
    created_at: datetime

    class Config:
        from_attributes = True

class CancelBookingResponse(BaseModel):
    booking_id: str
    status: str
    message: str
    compensation_steps: List[str]
