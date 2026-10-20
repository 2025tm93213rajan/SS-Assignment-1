import json
import uuid
import logging
from typing import Dict, Any, Tuple
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.config import settings
from src.models import Booking, SagaStepLog
from src.schemas import CreateBookingRequest
from src.amqp import event_publisher

logger = logging.getLogger(settings.SERVICE_NAME)

class SagaExecutionError(Exception):
    def __init__(self, message: str, booking: Booking, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.booking = booking
        self.status_code = status_code

class SagaOrchestrator:
    def __init__(self, http_client: httpx.AsyncClient = None):
        self._client = http_client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client:
            return self._client
        return httpx.AsyncClient(timeout=10.0)

    async def _log_step(
        self, 
        db: AsyncSession, 
        booking_id: str, 
        step_name: str, 
        status: str, 
        req_payload: Any = None, 
        res_payload: Any = None, 
        error_msg: str = None
    ):
        step = SagaStepLog(
            booking_id=booking_id,
            step_name=step_name,
            status=status,
            request_payload=json.dumps(req_payload) if req_payload else None,
            response_payload=json.dumps(res_payload) if res_payload else None,
            error_message=error_msg
        )
        db.add(step)
        await db.commit()

    async def execute_booking_saga(
        self, 
        request: CreateBookingRequest, 
        db: AsyncSession, 
        correlation_id: str
    ) -> Booking:
        booking_id = f"book-{uuid.uuid4().hex[:12]}"
        client = await self._get_client()

        # Initial Booking Record in PENDING state
        booking = Booking(
            booking_id=booking_id,
            quota_id=request.quota_id,
            event_name=request.event_name,
            category=request.category or "RAILWAY_TATKAL",
            passenger_count=len(request.passengers),
            total_amount=request.total_amount,
            status="PENDING",
            customer_name=request.customer_name,
            customer_email=request.customer_email,
            customer_phone=request.customer_phone
        )
        db.add(booking)
        await db.commit()
        await db.refresh(booking)

        logger.info(f"Saga started for booking {booking_id} correlation_id={correlation_id}")

        # ----------------------------------------------------------------------
        # STEP 1: INVENTORY RESERVATION (BR1, BR2)
        # ----------------------------------------------------------------------
        inv_payload = {
            "quota_id": request.quota_id,
            "quantity": len(request.passengers),
            "booking_id": booking_id
        }
        try:
            inv_res = await client.post(
                f"{settings.INVENTORY_SERVICE_URL}/api/v1/inventory/reserve",
                json=inv_payload,
                headers={"X-Correlation-ID": correlation_id}
            )
            inv_data = inv_res.json() if inv_res.content else {}

            if inv_res.status_code != 201:
                error_msg = inv_data.get("message", f"Inventory reservation failed with status {inv_res.status_code}")
                await self._log_step(db, booking_id, "INVENTORY_RESERVE", "FAILED", inv_payload, inv_data, error_msg)
                booking.status = "FAILED_INVENTORY"
                booking.compensation_reason = error_msg
                await db.commit()
                await db.refresh(booking)
                raise SagaExecutionError(error_msg, booking, status_code=inv_res.status_code)

            reservation_id = inv_data.get("reservation_token") or inv_data.get("reservation_id")
            booking.reservation_id = reservation_id
            booking.status = "RESERVED"
            await db.commit()
            await self._log_step(db, booking_id, "INVENTORY_RESERVE", "SUCCESS", inv_payload, inv_data)
            logger.info(f"Saga Step 1 [INVENTORY_RESERVE] succeeded: reservation_id={reservation_id}")

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            error_msg = f"Inventory service unreachable: {str(exc)}"
            await self._log_step(db, booking_id, "INVENTORY_RESERVE", "FAILED", inv_payload, None, error_msg)
            booking.status = "FAILED_INVENTORY"
            booking.compensation_reason = error_msg
            await db.commit()
            await db.refresh(booking)
            raise SagaExecutionError(error_msg, booking, status_code=503)

        # ----------------------------------------------------------------------
        # STEP 2: PAYMENT CHARGE (BR3 Idempotent Payment)
        # ----------------------------------------------------------------------
        pay_idempotency_key = request.idempotency_key or f"book-{booking_id}-pay"
        pay_info = request.payment
        pay_payload = {
            "booking_id": booking_id,
            "amount": float(request.total_amount),
            "currency": "INR",
            "payment_method": pay_info.payment_method if pay_info else "CARD",
            "card_number": pay_info.card_number if pay_info else "4000-0000-0000-0001",
            "force_failure": pay_info.force_failure if pay_info else False,
            "delay_ms": pay_info.delay_ms if pay_info else 0
        }

        try:
            pay_res = await client.post(
                f"{settings.PAYMENT_SERVICE_URL}/api/v1/payments/charge",
                json=pay_payload,
                headers={
                    "Idempotency-Key": pay_idempotency_key,
                    "X-Correlation-ID": correlation_id
                }
            )
            pay_data = pay_res.json() if pay_res.content else {}

            if pay_res.status_code != 201:
                # PAYMENT FAILED -> INITIATE SAGA COMPENSATION (BR4)
                error_msg = pay_data.get("message", f"Payment declined with HTTP {pay_res.status_code}")
                await self._log_step(db, booking_id, "PAYMENT_CHARGE", "FAILED", pay_payload, pay_data, error_msg)
                
                # TRIGGER COMPENSATING ACTION: Release held inventory
                logger.warning(f"Saga Step 2 [PAYMENT_CHARGE] failed. Triggering compensation on inventory...")
                comp_payload = {
                    "reservation_token": booking.reservation_id,
                    "quota_id": booking.quota_id,
                    "quantity": booking.passenger_count,
                    "reason": f"Saga compensation: payment failed for booking {booking_id}"
                }
                comp_res = await client.post(
                    f"{settings.INVENTORY_SERVICE_URL}/api/v1/inventory/release",
                    json=comp_payload,
                    headers={"X-Correlation-ID": correlation_id}
                )
                comp_data = comp_res.json() if comp_res.content else {}
                await self._log_step(db, booking_id, "COMPENSATION_INVENTORY_RELEASE", "COMPENSATED", comp_payload, comp_data)

                booking.status = "FAILED_COMPENSATED"
                booking.compensation_reason = f"Payment declined ({error_msg}). Reserved inventory seats released."
                await db.commit()
                await db.refresh(booking)
                raise SagaExecutionError(booking.compensation_reason, booking, status_code=pay_res.status_code)

            payment_id = pay_data.get("payment_id")
            booking.payment_id = payment_id
            booking.status = "PAID"
            await db.commit()
            await self._log_step(db, booking_id, "PAYMENT_CHARGE", "SUCCESS", pay_payload, pay_data)
            logger.info(f"Saga Step 2 [PAYMENT_CHARGE] succeeded: payment_id={payment_id}")

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            # Payment Network/Timeout Exception -> Trigger Compensation
            error_msg = f"Payment service network error: {str(exc)}"
            await self._log_step(db, booking_id, "PAYMENT_CHARGE", "FAILED", pay_payload, None, error_msg)
            
            # Compensating inventory release
            comp_payload = {
                "reservation_token": booking.reservation_id,
                "quota_id": booking.quota_id,
                "quantity": booking.passenger_count,
                "reason": "Saga compensation: payment timeout"
            }
            await client.post(
                f"{settings.INVENTORY_SERVICE_URL}/api/v1/inventory/release",
                json=comp_payload,
                headers={"X-Correlation-ID": correlation_id}
            )
            await self._log_step(db, booking_id, "COMPENSATION_INVENTORY_RELEASE", "COMPENSATED", comp_payload, None)
            
            booking.status = "FAILED_COMPENSATED"
            booking.compensation_reason = f"Payment connection failed. Held inventory seats released."
            await db.commit()
            await db.refresh(booking)
            raise SagaExecutionError(booking.compensation_reason, booking, status_code=504)

        # ----------------------------------------------------------------------
        # STEP 3: TICKETING FULFILLMENT (PNR & Berth Issuance)
        # ----------------------------------------------------------------------
        tkt_payload = {
            "booking_id": booking_id,
            "quota_id": request.quota_id,
            "event_name": request.event_name,
            "category": request.category or "RAILWAY_TATKAL",
            "passengers": [
                {"name": p.name, "berth_preference": p.berth_preference or "LOWER"} 
                for p in request.passengers
            ]
        }

        try:
            tkt_res = await client.post(
                f"{settings.TICKETING_SERVICE_URL}/api/v1/tickets/issue",
                json=tkt_payload,
                headers={"X-Correlation-ID": correlation_id}
            )
            tkt_data = tkt_res.json() if tkt_res.content else {}

            if tkt_res.status_code != 201:
                # TICKETING FAILED -> TRIGGER SAGA COMPENSATION (BR4)
                error_msg = tkt_data.get("message", f"Ticket issuance failed with HTTP {tkt_res.status_code}")
                await self._log_step(db, booking_id, "TICKETING_ISSUE", "FAILED", tkt_payload, tkt_data, error_msg)

                # Compensate inventory
                comp_payload = {
                    "reservation_token": booking.reservation_id,
                    "quota_id": booking.quota_id,
                    "quantity": booking.passenger_count,
                    "reason": "Saga compensation: ticketing failed"
                }
                await client.post(
                    f"{settings.INVENTORY_SERVICE_URL}/api/v1/inventory/release",
                    json=comp_payload,
                    headers={"X-Correlation-ID": correlation_id}
                )
                await self._log_step(db, booking_id, "COMPENSATION_INVENTORY_RELEASE", "COMPENSATED", comp_payload, None)

                booking.status = "FAILED_COMPENSATED"
                booking.compensation_reason = f"Ticket issuance failed ({error_msg}). Inventory released."
                await db.commit()
                await db.refresh(booking)
                raise SagaExecutionError(booking.compensation_reason, booking, status_code=tkt_res.status_code)

            pnr = tkt_data.get("pnr")
            booking.pnr = pnr
            booking.status = "TICKETED"
            await db.commit()
            await self._log_step(db, booking_id, "TICKETING_ISSUE", "SUCCESS", tkt_payload, tkt_data)
            logger.info(f"Saga Step 3 [TICKETING_ISSUE] succeeded: pnr={pnr}")

        except (httpx.RequestError, httpx.TimeoutException) as exc:
            error_msg = f"Ticketing service network error: {str(exc)}"
            await self._log_step(db, booking_id, "TICKETING_ISSUE", "FAILED", tkt_payload, None, error_msg)
            
            comp_payload = {
                "reservation_token": booking.reservation_id,
                "quota_id": booking.quota_id,
                "quantity": booking.passenger_count,
                "reason": "Saga compensation: ticketing timeout"
            }
            await client.post(
                f"{settings.INVENTORY_SERVICE_URL}/api/v1/inventory/release",
                json=comp_payload,
                headers={"X-Correlation-ID": correlation_id}
            )
            await self._log_step(db, booking_id, "COMPENSATION_INVENTORY_RELEASE", "COMPENSATED", comp_payload, None)
            
            booking.status = "FAILED_COMPENSATED"
            booking.compensation_reason = "Ticketing service timeout. Inventory released."
            await db.commit()
            await db.refresh(booking)
            raise SagaExecutionError(booking.compensation_reason, booking, status_code=504)

        # ----------------------------------------------------------------------
        # STEP 4: ASYNC EVENT PUBLICATION (RabbitMQ AMQP)
        # ----------------------------------------------------------------------
        event_data = {
            "event_id": f"evt-{uuid.uuid4().hex[:16]}",
            "booking_id": booking_id,
            "quota_id": request.quota_id,
            "event_name": request.event_name,
            "category": request.category or "RAILWAY_TATKAL",
            "pnr": booking.pnr,
            "customer_phone": request.customer_phone,
            "customer_email": request.customer_email,
            "amount": float(request.total_amount),
            "correlation_id": correlation_id
        }

        pub_ok = await event_publisher.publish("booking.confirmed", event_data, correlation_id)
        await self._log_step(
            db, booking_id, "EVENT_PUBLISH", 
            "SUCCESS" if pub_ok else "DEGRADED", 
            event_data, 
            {"published": pub_ok}
        )

        # ----------------------------------------------------------------------
        # STEP 5: FINAL SAGA CONFIRMATION
        # ----------------------------------------------------------------------
        booking.status = "CONFIRMED"
        await db.commit()
        
        # Load steps relation
        stmt = select(Booking).where(Booking.booking_id == booking_id).options(selectinload(Booking.steps))
        res = await db.execute(stmt)
        confirmed_booking = res.scalar_one()

        logger.info(f"Saga successfully finished for booking {booking_id}, PNR={booking.pnr}")
        return confirmed_booking

    async def cancel_booking(self, booking_id: str, db: AsyncSession, correlation_id: str) -> Tuple[Booking, list]:
        stmt = select(Booking).where(Booking.booking_id == booking_id).options(selectinload(Booking.steps))
        res = await db.execute(stmt)
        booking = res.scalar_one_or_none()
        if not booking:
            return None, []

        client = await self._get_client()
        compensation_steps = []

        # Cancel ticket if PNR exists
        if booking.pnr:
            try:
                await client.post(
                    f"{settings.TICKETING_SERVICE_URL}/api/v1/tickets/cancel",
                    json={"pnr": booking.pnr, "reason": "User requested cancellation"},
                    headers={"X-Correlation-ID": correlation_id}
                )
                compensation_steps.append(f"Ticket PNR {booking.pnr} cancelled")
            except Exception as e:
                logger.error(f"Error cancelling ticket: {str(e)}")

        # Release inventory if reservation exists
        if booking.reservation_id:
            try:
                comp_payload = {
                    "reservation_token": booking.reservation_id,
                    "quota_id": booking.quota_id,
                    "quantity": booking.passenger_count,
                    "reason": "User cancellation"
                }
                await client.post(
                    f"{settings.INVENTORY_SERVICE_URL}/api/v1/inventory/release",
                    json=comp_payload,
                    headers={"X-Correlation-ID": correlation_id}
                )
                compensation_steps.append(f"Inventory reservation {booking.reservation_id} released")
            except Exception as e:
                logger.error(f"Error releasing inventory: {str(e)}")

        booking.status = "CANCELLED"
        booking.compensation_reason = "Cancelled by user. Compensating release executed."
        await db.commit()
        await db.refresh(booking)

        await self._log_step(
            db, booking_id, "USER_CANCELLATION", "COMPENSATED", 
            {"compensation_steps": compensation_steps}
        )

        return booking, compensation_steps
