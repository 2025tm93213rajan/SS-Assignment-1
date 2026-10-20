import uuid
import hashlib
import random
from typing import List, Optional, Dict, Any
from sqlalchemy import select, delete, text
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import PnrRecord, IssuedTicket
from src.schemas import PassengerInput

class PnrNotFoundError(Exception):
    def __init__(self, pnr: str):
        self.pnr = pnr
        super().__init__(f"PNR record '{pnr}' not found.")

class TicketingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def issue_pnr_and_tickets(
        self,
        booking_id: str,
        quota_id: str,
        event_name: str,
        passengers: List[PassengerInput],
        category: str = "RAILWAY_TATKAL"
    ) -> PnrRecord:
        # Check if tickets were already issued for this booking_id (Idempotent fulfillment)
        query = (
            select(PnrRecord)
            .where(PnrRecord.booking_id == booking_id)
            .options(selectinload(PnrRecord.tickets))
        )
        res = await self.session.execute(query)
        existing = res.scalar_one_or_none()
        if existing:
            return existing

        # Generate unique PNR token
        prefix = "TATKAL" if "TATKAL" in quota_id else ("CONCERT" if "COLDPLAY" in quota_id else "BUS")
        pnr_token = f"PNR-{prefix}-{random.randint(100000, 999999)}"

        pnr_record = PnrRecord(
            pnr=pnr_token,
            booking_id=booking_id,
            quota_id=quota_id,
            event_name=event_name,
            status="ISSUED"
        )
        self.session.add(pnr_record)

        # Allocate specific berths / seats per passenger
        for idx, p in enumerate(passengers, start=1):
            if prefix == "TATKAL":
                berth_num = f"B1-{random.randint(10, 60)}"
                berth_type = p.berth_preference or "LOWER"
            elif prefix == "CONCERT":
                berth_num = f"VIP-ARENA-A{idx}"
                berth_type = "VIP_ARENA"
            else:
                berth_num = f"SL-{idx:02d}"
                berth_type = p.berth_preference or "WINDOW"

            raw_barcode = f"{pnr_token}:{p.name}:{berth_num}:{idx}"
            barcode_hash = hashlib.sha256(raw_barcode.encode()).hexdigest()[:24].upper()

            ticket = IssuedTicket(
                ticket_id=f"tkt-{uuid.uuid4().hex[:12]}",
                pnr=pnr_token,
                passenger_name=p.name,
                berth_number=berth_num,
                berth_type=berth_type,
                barcode_token=barcode_hash
            )
            self.session.add(ticket)

        await self.session.commit()

        # Re-fetch with eagerly loaded relationship
        query_reload = (
            select(PnrRecord)
            .where(PnrRecord.pnr == pnr_token)
            .options(selectinload(PnrRecord.tickets))
        )
        reload_res = await self.session.execute(query_reload)
        return reload_res.scalar_one()

    async def get_by_pnr(self, pnr: str) -> Optional[PnrRecord]:
        query = (
            select(PnrRecord)
            .where(PnrRecord.pnr == pnr)
            .options(selectinload(PnrRecord.tickets))
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_by_booking_id(self, booking_id: str) -> Optional[PnrRecord]:
        query = (
            select(PnrRecord)
            .where(PnrRecord.booking_id == booking_id)
            .options(selectinload(PnrRecord.tickets))
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def cancel_pnr(self, pnr: Optional[str] = None, booking_id: Optional[str] = None) -> PnrRecord:
        query = select(PnrRecord)
        if pnr:
            query = query.where(PnrRecord.pnr == pnr)
        elif booking_id:
            query = query.where(PnrRecord.booking_id == booking_id)
        else:
            raise ValueError("Either pnr or booking_id must be provided.")

        res = await self.session.execute(query)
        pnr_rec = res.scalar_one_or_none()
        if not pnr_rec:
            raise PnrNotFoundError(pnr or booking_id)

        pnr_rec.status = "CANCELLED"
        await self.session.commit()
        return pnr_rec

    async def reset_seed_data(self) -> None:
        await self.session.execute(text("TRUNCATE TABLE issued_tickets, pnr_records CASCADE;"))
        await self.session.commit()
