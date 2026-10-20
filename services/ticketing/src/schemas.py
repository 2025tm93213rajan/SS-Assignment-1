from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class PassengerInput(BaseModel):
    name: str = Field(..., min_length=1, description="Passenger full name")
    berth_preference: Optional[str] = Field("LOWER", description="Preferred berth/seat type")

class IssueTicketRequest(BaseModel):
    booking_id: str = Field(..., description="Unique booking ID from saga")
    quota_id: str = Field(..., description="Target quota ID")
    event_name: str = Field(..., description="Train number, concert tour or bus line")
    passengers: List[PassengerInput] = Field(..., min_length=1, description="List of passengers to issue tickets for")
    category: Optional[str] = Field("RAILWAY_TATKAL", description="Reservation mode")

class TicketDetail(BaseModel):
    ticket_id: str
    passenger_name: str
    berth_number: str
    berth_type: str
    barcode_token: str
    created_at: datetime

class IssueTicketResponse(BaseModel):
    status: str = "ISSUED"
    pnr: str
    booking_id: str
    quota_id: str
    event_name: str
    tickets: List[TicketDetail]
    created_at: datetime

class CancelTicketRequest(BaseModel):
    pnr: Optional[str] = None
    booking_id: Optional[str] = None
    reason: Optional[str] = "Saga Compensating Cancellation"

class CancelTicketResponse(BaseModel):
    status: str = "CANCELLED"
    pnr: str
    message: str
