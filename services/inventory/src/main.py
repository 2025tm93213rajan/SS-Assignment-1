import os
import uuid
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Response, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import engine, Base, get_db
from src.schemas import (
    ReserveRequest, ReserveResponse,
    ReleaseRequest, ReleaseResponse,
    ConfirmRequest, ConfirmResponse,
    EventDetail, QuotaDetail, ErrorResponse
)
from src.repository import (
    InventoryRepository, 
    InsufficientInventoryError, 
    QuotaNotFoundError, 
    ReservationNotFoundError
)

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "' + settings.SERVICE_NAME + '", "message": "%(message)s"}'
)
logger = logging.getLogger(settings.SERVICE_NAME)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables and seed initial inventory
    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Check if seed data exists; if not, seed initial items
    async with AsyncSession(engine) as session:
        repo = InventoryRepository(session)
        events = await repo.get_all_events_with_quotas()
        if not events:
            logger.info("Seeding initial inventory items (Tatkal, Concert, Bus)...")
            await repo.reset_seed_data()
            logger.info("Database seeding complete.")
    
    yield
    await engine.dispose()

app = FastAPI(
    title="SeatLock Inventory Service",
    description="High-concurrency seat, berth & ticket quota inventory engine with atomic conditional updates.",
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

@app.exception_handler(InsufficientInventoryError)
async def insufficient_inventory_handler(request: Request, exc: InsufficientInventoryError):
    corr_id = getattr(request.state, "correlation_id", "unknown")
    logger.warning(f"BR1 Violation Prevented: {str(exc)} correlation_id={corr_id}")
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "status": "error",
            "code": "INSUFFICIENT_INVENTORY",
            "message": str(exc),
            "correlation_id": corr_id,
            "service": settings.SERVICE_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "quota_id": exc.quota_id,
                "requested": exc.requested,
                "available": exc.available
            }
        }
    )

@app.exception_handler(QuotaNotFoundError)
async def quota_not_found_handler(request: Request, exc: QuotaNotFoundError):
    corr_id = getattr(request.state, "correlation_id", "unknown")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "status": "error",
            "code": "QUOTA_NOT_FOUND",
            "message": str(exc),
            "correlation_id": corr_id,
            "service": settings.SERVICE_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

@app.exception_handler(ReservationNotFoundError)
async def reservation_not_found_handler(request: Request, exc: ReservationNotFoundError):
    corr_id = getattr(request.state, "correlation_id", "unknown")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "status": "error",
            "code": "RESERVATION_NOT_FOUND",
            "message": str(exc),
            "correlation_id": corr_id,
            "service": settings.SERVICE_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    corr_id = getattr(request.state, "correlation_id", "unknown")
    logger.error(f"Unhandled error: {str(exc)} correlation_id={corr_id}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred in inventory-service",
            "correlation_id": corr_id,
            "service": settings.SERVICE_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

@app.get("/health", tags=["Observability"])
async def health_check():
    db_healthy = True
    try:
        async with engine.connect() as conn:
            await conn.execute("SELECT 1;")
    except Exception:
        db_healthy = False

    return {
        "status": "UP" if db_healthy else "DEGRADED",
        "service": settings.SERVICE_NAME,
        "database": "connected" if db_healthy else "disconnected",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/v1/inventory/items", response_model=list[EventDetail], tags=["Inventory"])
async def list_items(db: AsyncSession = Depends(get_db)):
    """List all events/trains/buses with quotas and live real-time available seat counts."""
    repo = InventoryRepository(db)
    items = await repo.get_all_events_with_quotas()
    return items

@app.get("/api/v1/inventory/quotas/{quota_id}", response_model=QuotaDetail, tags=["Inventory"])
async def get_quota(quota_id: str, db: AsyncSession = Depends(get_db)):
    """Get real-time seat inventory for a specific quota."""
    repo = InventoryRepository(db)
    quota = await repo.get_quota_inventory(quota_id)
    if not quota:
        raise QuotaNotFoundError(quota_id)
    return quota

@app.post(
    "/api/v1/inventory/reserve", 
    response_model=ReserveResponse, 
    status_code=status.HTTP_201_CREATED,
    tags=["Inventory", "Concurrency Engine"]
)
async def reserve_seats(req: ReserveRequest, db: AsyncSession = Depends(get_db)):
    """
    Enforces BR1 & BR2:
    Atomic seat allocation at the PostgreSQL database level.
    Guarantees exactly N reservations succeed and zero over-allocation under high concurrency.
    """
    repo = InventoryRepository(db)
    reservation, inv_state = await repo.reserve_seats_atomic(
        quota_id=req.quota_id,
        quantity=req.quantity,
        booking_id=req.booking_id
    )
    return ReserveResponse(
        status="RESERVED",
        reservation_token=reservation.reservation_token,
        quota_id=reservation.quota_id,
        quantity=reservation.quantity,
        remaining_available=inv_state["remaining_available"],
        version=inv_state["version"],
        expires_at=reservation.expires_at
    )

@app.post("/api/v1/inventory/release", response_model=ReleaseResponse, tags=["Inventory", "Saga Compensation"])
async def release_seats(req: ReleaseRequest, db: AsyncSession = Depends(get_db)):
    """
    Saga Compensating Action:
    Restores held seats back into the inventory pool atomically upon payment or ticketing failure.
    """
    repo = InventoryRepository(db)
    result = await repo.release_seats_compensating(
        reservation_token=req.reservation_token,
        quota_id=req.quota_id,
        quantity=req.quantity
    )
    return ReleaseResponse(
        status="RELEASED",
        quota_id=result["quota_id"],
        released_quantity=result["released_quantity"],
        current_available=result["current_available"],
        message=result["message"]
    )

@app.post("/api/v1/inventory/confirm", response_model=ConfirmResponse, tags=["Inventory"])
async def confirm_seats(req: ConfirmRequest, db: AsyncSession = Depends(get_db)):
    """Finalizes reservation status from HELD to CONFIRMED."""
    repo = InventoryRepository(db)
    reservation = await repo.confirm_reservation(req.reservation_token)
    return ConfirmResponse(
        status="CONFIRMED",
        reservation_token=reservation.reservation_token,
        quota_id=reservation.quota_id,
        quantity=reservation.quantity
    )

@app.post("/api/v1/inventory/reset", tags=["Testing & Benchmarking"])
async def reset_inventory(db: AsyncSession = Depends(get_db)):
    """Resets seed inventory to capacity 5 for reproducible challenge and demo runs."""
    repo = InventoryRepository(db)
    await repo.reset_seed_data()
    return {
        "status": "RESET_COMPLETE",
        "message": "All quotas (Tatkal, Concert, Bus) reset to capacity 5."
    }
