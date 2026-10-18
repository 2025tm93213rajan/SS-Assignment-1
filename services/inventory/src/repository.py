import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import EventTrip, Quota, SeatInventory, Reservation

class InsufficientInventoryError(Exception):
    def __init__(self, quota_id: str, requested: int, available: int):
        self.quota_id = quota_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient inventory for quota '{quota_id}'. "
            f"Requested {requested}, but only {available} available."
        )

class QuotaNotFoundError(Exception):
    def __init__(self, quota_id: str):
        self.quota_id = quota_id
        super().__init__(f"Quota '{quota_id}' does not exist.")

class ReservationNotFoundError(Exception):
    def __init__(self, token: str):
        self.token = token
        super().__init__(f"Reservation with token '{token}' not found.")

class InventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_events_with_quotas(self) -> List[Dict[str, Any]]:
        query = text("""
            SELECT 
                e.id AS event_id, e.title, e.category, e.origin, e.destination, e.departure_time,
                q.id AS quota_id, q.tier_name, q.total_capacity, q.price,
                i.available, i.locked, i.version
            FROM events_trips e
            JOIN quotas q ON q.event_id = e.id
            JOIN seat_inventories i ON i.quota_id = q.id
            ORDER BY e.category, e.title, q.tier_name;
        """)
        result = await self.session.execute(query)
        rows = result.fetchall()

        events_map: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            eid = row.event_id
            if eid not in events_map:
                events_map[eid] = {
                    "id": eid,
                    "title": row.title,
                    "category": row.category,
                    "origin": row.origin,
                    "destination": row.destination,
                    "departure_time": row.departure_time,
                    "quotas": []
                }
            events_map[eid]["quotas"].append({
                "id": row.quota_id,
                "tier_name": row.tier_name,
                "total_capacity": row.total_capacity,
                "available_seats": row.available,
                "locked_seats": row.locked,
                "price": float(row.price),
                "version": row.version
            })

        return list(events_map.values())

    async def get_quota_inventory(self, quota_id: str) -> Optional[Dict[str, Any]]:
        query = text("""
            SELECT 
                q.id AS quota_id, q.tier_name, q.total_capacity, q.price,
                i.available, i.locked, i.version
            FROM quotas q
            JOIN seat_inventories i ON i.quota_id = q.id
            WHERE q.id = :quota_id;
        """)
        result = await self.session.execute(query, {"quota_id": quota_id})
        row = result.fetchone()
        if not row:
            return None
        return {
            "id": row.quota_id,
            "tier_name": row.tier_name,
            "total_capacity": row.total_capacity,
            "available_seats": row.available,
            "locked_seats": row.locked,
            "price": float(row.price),
            "version": row.version
        }

    async def reserve_seats_atomic(
        self, 
        quota_id: str, 
        quantity: int, 
        booking_id: Optional[str] = None,
        hold_seconds: int = 300
    ) -> Tuple[Reservation, Dict[str, Any]]:
        """
        Enforces BR1 (Zero Over-allocation) & BR2 (Atomic Conditional Update).
        Executes atomic decrement at database engine level.
        Never performs read-then-write in application code.
        """
        atomic_update_sql = text("""
            UPDATE seat_inventories
            SET 
                available = available - :qty,
                locked = locked + :qty,
                version = version + 1,
                updated_at = NOW()
            WHERE quota_id = :quota_id AND available >= :qty
            RETURNING quota_id, total_capacity, available, locked, version;
        """)

        result = await self.session.execute(atomic_update_sql, {"quota_id": quota_id, "qty": quantity})
        updated_row = result.fetchone()

        if not updated_row:
            # Atomic update failed. Check reason to provide rich diagnostic error
            check_sql = text("SELECT available, total_capacity FROM seat_inventories WHERE quota_id = :quota_id;")
            check_res = await self.session.execute(check_sql, {"quota_id": quota_id})
            inv = check_res.fetchone()

            if not inv:
                raise QuotaNotFoundError(quota_id)
            else:
                # BR1 Violation prevented: available < quantity
                raise InsufficientInventoryError(
                    quota_id=quota_id, 
                    requested=quantity, 
                    available=inv.available
                )

        # Create reservation record
        res_token = f"tok-{uuid.uuid4().hex[:16]}"
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=hold_seconds)
        reservation = Reservation(
            id=f"res-{uuid.uuid4().hex[:12]}",
            reservation_token=res_token,
            quota_id=quota_id,
            booking_id=booking_id,
            quantity=quantity,
            status="HELD",
            expires_at=expires_at
        )
        self.session.add(reservation)
        await self.session.commit()

        inventory_state = {
            "quota_id": updated_row.quota_id,
            "remaining_available": updated_row.available,
            "locked": updated_row.locked,
            "version": updated_row.version
        }
        return reservation, inventory_state

    async def release_seats_compensating(
        self, 
        reservation_token: Optional[str] = None,
        quota_id: Optional[str] = None,
        quantity: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes compensating action (Saga rollback).
        Releases held seats back to the inventory pool atomically.
        """
        target_quota_id = quota_id
        qty_to_release = quantity

        if reservation_token:
            query = select(Reservation).where(Reservation.reservation_token == reservation_token)
            res = await self.session.execute(query)
            reservation = res.scalar_one_or_none()
            if not reservation:
                raise ReservationNotFoundError(reservation_token)

            if reservation.status == "RELEASED":
                # Idempotent release check
                inv_state = await self.get_quota_inventory(reservation.quota_id)
                return {
                    "quota_id": reservation.quota_id,
                    "released_quantity": reservation.quantity,
                    "current_available": inv_state["available_seats"] if inv_state else 0,
                    "message": "Reservation was already released (idempotent)."
                }

            target_quota_id = reservation.quota_id
            qty_to_release = reservation.quantity
            reservation.status = "RELEASED"

        if not target_quota_id or not qty_to_release:
            raise ValueError("Either valid reservation_token or quota_id and quantity must be provided.")

        atomic_restore_sql = text("""
            UPDATE seat_inventories
            SET 
                available = LEAST(available + :qty, total_capacity),
                locked = GREATEST(locked - :qty, 0),
                version = version + 1,
                updated_at = NOW()
            WHERE quota_id = :quota_id
            RETURNING quota_id, available, locked, version;
        """)

        result = await self.session.execute(atomic_restore_sql, {"quota_id": target_quota_id, "qty": qty_to_release})
        row = result.fetchone()
        if not row:
            raise QuotaNotFoundError(target_quota_id)

        await self.session.commit()

        return {
            "quota_id": target_quota_id,
            "released_quantity": qty_to_release,
            "current_available": row.available,
            "message": f"Successfully released {qty_to_release} seats back to quota {target_quota_id}."
        }

    async def confirm_reservation(self, reservation_token: str) -> Reservation:
        query = select(Reservation).where(Reservation.reservation_token == reservation_token)
        res = await self.session.execute(query)
        reservation = res.scalar_one_or_none()
        if not reservation:
            raise ReservationNotFoundError(reservation_token)

        reservation.status = "CONFIRMED"
        await self.session.commit()
        return reservation

    async def reset_seed_data(self) -> None:
        """Resets all quotas to initial demonstration state with capacity 5 for challenge repeatability."""
        await self.session.execute(text("TRUNCATE TABLE reservations, seat_inventories, quotas, events_trips CASCADE;"))

        # 1. Event 1: IRCTC Railway Tatkal (Train #12951 Mumbai Tejas Rajdhani Express)
        e1 = EventTrip(
            id="TRAIN-12951",
            title="Mumbai Tejas Rajdhani Express (Train #12951)",
            category="RAILWAY_TATKAL",
            origin="Mumbai Central (MMCT)",
            destination="New Delhi (NDLS)",
            departure_time=datetime.now(timezone.utc) + timedelta(days=1)
        )
        q1 = Quota(id="TATKAL-12951-B1", event_id="TRAIN-12951", tier_name="AC 3-Tier Tatkal Quota", total_capacity=5, price=2850.00)
        inv1 = SeatInventory(quota_id="TATKAL-12951-B1", total_capacity=5, available=5, locked=0, version=1)

        # 2. Event 2: Concert Flash-Sale (Coldplay Music of the Spheres)
        e2 = EventTrip(
            id="COLDPLAY-2026",
            title="Coldplay: Music of the Spheres Stadium Tour",
            category="CONCERT_EVENT",
            origin="DY Patil Stadium",
            destination="Mumbai",
            departure_time=datetime.now(timezone.utc) + timedelta(days=30)
        )
        q2 = Quota(id="COLDPLAY-VIP-A1", event_id="COLDPLAY-2026", tier_name="VIP Front Arena Pass", total_capacity=5, price=12500.00)
        inv2 = SeatInventory(quota_id="COLDPLAY-VIP-A1", total_capacity=5, available=5, locked=0, version=1)

        # 3. Event 3: Intercity Express Bus (Volvo Multi-Axle Sleeper)
        e3 = EventTrip(
            id="BUS-VOLVO-99",
            title="Intercity Volvo B11R Multi-Axle Luxury Sleeper",
            category="EXPRESS_BUS",
            origin="Bengaluru (Majestic)",
            destination="Hyderabad (Gachibowli)",
            departure_time=datetime.now(timezone.utc) + timedelta(days=2)
        )
        q3 = Quota(id="VOLVO-EXP-99", event_id="BUS-VOLVO-99", tier_name="Upper Single Sleeper Berths", total_capacity=5, price=1800.00)
        inv3 = SeatInventory(quota_id="VOLVO-EXP-99", total_capacity=5, available=5, locked=0, version=1)

        self.session.add_all([e1, e2, e3, q1, q2, q3, inv1, inv2, inv3])
        await self.session.commit()
