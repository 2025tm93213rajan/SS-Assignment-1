from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class ReserveRequest(BaseModel):
    quota_id: str = Field(..., description="Target quota ID, e.g. TATKAL-12951-B1")
    quantity: int = Field(1, ge=1, le=10, description="Number of seats to reserve atomically")
    booking_id: Optional[str] = Field(None, description="Optional booking reference")

class ReserveResponse(BaseModel):
    status: str = "RESERVED"
    reservation_token: str
    quota_id: str
    quantity: int
    remaining_available: int
    version: int
    expires_at: Optional[datetime] = None

class ReleaseRequest(BaseModel):
    reservation_token: Optional[str] = Field(None, description="Unique token received during reserve")
    quota_id: Optional[str] = Field(None, description="Target quota ID if token is omitted")
    quantity: Optional[int] = Field(None, ge=1, description="Quantity to release if token is omitted")
    reason: Optional[str] = Field("Saga Compensating Rollback", description="Reason for release")

class ReleaseResponse(BaseModel):
    status: str = "RELEASED"
    quota_id: str
    released_quantity: int
    current_available: int
    message: str

class ConfirmRequest(BaseModel):
    reservation_token: str = Field(..., description="Unique token to confirm")
    booking_id: Optional[str] = None

class ConfirmResponse(BaseModel):
    status: str = "CONFIRMED"
    reservation_token: str
    quota_id: str
    quantity: int

class QuotaDetail(BaseModel):
    id: str
    tier_name: str
    total_capacity: int
    available_seats: int
    locked_seats: int
    price: float
    version: int

class EventDetail(BaseModel):
    id: str
    title: str
    category: str
    origin: Optional[str] = None
    destination: Optional[str] = None
    departure_time: Optional[datetime] = None
    quotas: List[QuotaDetail]

class ErrorResponse(BaseModel):
    status: str = "error"
    code: str
    message: str
    correlation_id: str
    service: str = "inventory-service"
    timestamp: str
    details: Optional[Dict[str, Any]] = None
