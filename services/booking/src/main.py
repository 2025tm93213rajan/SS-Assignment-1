import os
import uuid
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, Request, Response, Depends, status, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import engine, Base, get_db
from src.models import Booking, SagaStepLog
from src.schemas import (
    CreateBookingRequest, BookingResponse, CancelBookingResponse
)
from src.saga import SagaOrchestrator, SagaExecutionError
from src.amqp import event_publisher

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "' + settings.SERVICE_NAME + '", "message": "%(message)s"}'
)
logger = logging.getLogger(settings.SERVICE_NAME)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing booking database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Booking database tables initialized.")
    await event_publisher.connect()
    yield
    await event_publisher.close()
    await engine.dispose()

app = FastAPI(
    title="SeatLock Booking & Saga Orchestration Service",
    description="Distributed Saga Orchestrator managing multi-phase ticket reservation transactions with automated compensating rollbacks (BR4).",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID") or f"corr-{uuid.uuid4().hex[:12]}"
    request.state.correlation_id = corr_id
    start_time = time.time()
    
    response: Response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    response.headers["X-Correlation-ID"] = corr_id
    
    logger.info(
        f"method={request.method} path={request.url.path} status={response.status_code} "
        f"duration_ms={duration_ms} correlation_id={corr_id}"
    )
    return response

@app.get("/health", tags=["Observability"])
async def health_check():
    db_healthy = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1;"))
    except Exception:
        db_healthy = False

    return {
        "status": "UP" if db_healthy else "DEGRADED",
        "service": settings.SERVICE_NAME,
        "database": "connected" if db_healthy else "disconnected",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.SERVICE_NAME,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }

@app.post(
    "/api/v1/bookings", 
    response_model=BookingResponse, 
    status_code=status.HTTP_201_CREATED,
    tags=["Saga Orchestration"]
)
async def create_booking(
    request: CreateBookingRequest, 
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Executes the distributed reservation Saga:
    1. Holds inventory in inventory_db (BR1, BR2)
    2. Executes idempotent card charge in payment_db (BR3)
       - If payment fails, triggers compensation: releases held inventory (BR4)
    3. Issues official PNR and berths in ticketing_db
    4. Publishes booking.confirmed AMQP event to RabbitMQ
    5. Confirms booking
    """
    corr_id = getattr(req.state, "correlation_id", f"corr-{uuid.uuid4().hex[:12]}")
    orchestrator = SagaOrchestrator()
    try:
        booking = await orchestrator.execute_booking_saga(request, db, corr_id)
        return booking
    except SagaExecutionError as e:
        # Load steps for error response
        stmt = select(Booking).where(Booking.booking_id == e.booking.booking_id).options(selectinload(Booking.steps))
        res = await db.execute(stmt)
        failed_booking = res.scalar_one_or_none() or e.booking

        return JSONResponse(
            status_code=e.status_code if e.status_code in [400, 402, 404, 409, 422, 500, 502, 503, 504] else 400,
            content={
                "status": "FAILED",
                "error": e.message,
                "booking": {
                    "booking_id": failed_booking.booking_id,
                    "status": failed_booking.status,
                    "quota_id": failed_booking.quota_id,
                    "total_amount": float(failed_booking.total_amount),
                    "compensation_reason": failed_booking.compensation_reason,
                    "reservation_id": failed_booking.reservation_id,
                    "payment_id": failed_booking.payment_id,
                    "pnr": failed_booking.pnr,
                    "steps": [
                        {
                            "step_name": s.step_name,
                            "status": s.status,
                            "error_message": s.error_message,
                            "timestamp": s.timestamp.isoformat()
                        } for s in getattr(failed_booking, "steps", [])
                    ]
                },
                "correlation_id": corr_id,
                "service": settings.SERVICE_NAME
            }
        )

@app.get(
    "/api/v1/bookings/{booking_id}", 
    response_model=BookingResponse,
    tags=["Saga Orchestration"]
)
async def get_booking_by_id(
    booking_id: str, 
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Booking).where(Booking.booking_id == booking_id).options(selectinload(Booking.steps))
    res = await db.execute(stmt)
    booking = res.scalar_one_or_none()
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Booking '{booking_id}' not found."
        )
    return booking

@app.get(
    "/api/v1/bookings", 
    response_model=List[BookingResponse],
    tags=["Saga Orchestration"]
)
async def list_bookings(
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Booking).options(selectinload(Booking.steps)).order_by(Booking.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    return res.scalars().all()

@app.post(
    "/api/v1/bookings/{booking_id}/cancel", 
    response_model=CancelBookingResponse,
    tags=["Saga Orchestration"]
)
async def cancel_booking(
    booking_id: str, 
    req: Request,
    db: AsyncSession = Depends(get_db)
):
    corr_id = getattr(req.state, "correlation_id", f"corr-{uuid.uuid4().hex[:12]}")
    orchestrator = SagaOrchestrator()
    booking, steps = await orchestrator.cancel_booking(booking_id, db, corr_id)
    if not booking:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Booking '{booking_id}' not found."
        )
    return CancelBookingResponse(
        booking_id=booking.booking_id,
        status="CANCELLED",
        message="Booking cancelled and compensation completed.",
        compensation_steps=steps
    )

@app.post("/api/v1/bookings/reset", tags=["Testing & Benchmarking"])
async def reset_bookings(db: AsyncSession = Depends(get_db)):
    await db.execute(delete(SagaStepLog))
    await db.execute(delete(Booking))
    await db.commit()
    return {"status": "RESET_COMPLETE", "message": "All bookings and saga traces cleared."}
