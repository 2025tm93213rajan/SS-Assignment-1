import os
import uuid
import time
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Response, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.database import engine, Base, get_db
from src.schemas import (
    IssueTicketRequest, IssueTicketResponse, TicketDetail,
    CancelTicketRequest, CancelTicketResponse
)
from src.repository import TicketingRepository, PnrNotFoundError

logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "' + settings.SERVICE_NAME + '", "message": "%(message)s"}'
)
logger = logging.getLogger(settings.SERVICE_NAME)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing ticketing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Ticketing database tables initialized.")
    yield
    await engine.dispose()

app = FastAPI(
    title="SeatLock Ticketing Fulfillment Service",
    description="Fulfillment engine for PNR issuance, seat/berth allocation and digital ticket tokens.",
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

@app.exception_handler(PnrNotFoundError)
async def pnr_not_found_handler(request: Request, exc: PnrNotFoundError):
    corr_id = getattr(request.state, "correlation_id", "unknown")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "status": "error",
            "code": "PNR_NOT_FOUND",
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
            "message": "An unexpected error occurred in ticketing-service",
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
    "/api/v1/tickets/issue", 
    response_model=IssueTicketResponse, 
    status_code=status.HTTP_201_CREATED,
    tags=["Ticketing Fulfillment"]
)
async def issue_tickets(req: IssueTicketRequest, db: AsyncSession = Depends(get_db)):
    """Issues official PNR and allocates specific berths/seats per passenger."""
    repo = TicketingRepository(db)
    pnr_record = await repo.issue_pnr_and_tickets(
        booking_id=req.booking_id,
        quota_id=req.quota_id,
        event_name=req.event_name,
        passengers=req.passengers,
        category=req.category or "RAILWAY_TATKAL"
    )

    ticket_details = [
        TicketDetail(
            ticket_id=t.ticket_id,
            passenger_name=t.passenger_name,
            berth_number=t.berth_number,
            berth_type=t.berth_type,
            barcode_token=t.barcode_token,
            created_at=t.created_at
        )
        for t in pnr_record.tickets
    ]

    return IssueTicketResponse(
        status=pnr_record.status,
        pnr=pnr_record.pnr,
        booking_id=pnr_record.booking_id,
        quota_id=pnr_record.quota_id,
        event_name=pnr_record.event_name,
        tickets=ticket_details,
        created_at=pnr_record.created_at
    )

@app.get("/api/v1/tickets/pnr/{pnr}", response_model=IssueTicketResponse, tags=["Ticketing Fulfillment"])
async def get_by_pnr(pnr: str, db: AsyncSession = Depends(get_db)):
    """Lookup ticket fulfillment details by PNR."""
    repo = TicketingRepository(db)
    pnr_record = await repo.get_by_pnr(pnr)
    if not pnr_record:
        raise PnrNotFoundError(pnr)

    ticket_details = [
        TicketDetail(
            ticket_id=t.ticket_id,
            passenger_name=t.passenger_name,
            berth_number=t.berth_number,
            berth_type=t.berth_type,
            barcode_token=t.barcode_token,
            created_at=t.created_at
        )
        for t in pnr_record.tickets
    ]

    return IssueTicketResponse(
        status=pnr_record.status,
        pnr=pnr_record.pnr,
        booking_id=pnr_record.booking_id,
        quota_id=pnr_record.quota_id,
        event_name=pnr_record.event_name,
        tickets=ticket_details,
        created_at=pnr_record.created_at
    )

@app.get("/api/v1/tickets/booking/{booking_id}", response_model=IssueTicketResponse, tags=["Ticketing Fulfillment"])
async def get_by_booking(booking_id: str, db: AsyncSession = Depends(get_db)):
    """Lookup ticket fulfillment details by Booking reference."""
    repo = TicketingRepository(db)
    pnr_record = await repo.get_by_booking_id(booking_id)
    if not pnr_record:
        raise PnrNotFoundError(booking_id)

    ticket_details = [
        TicketDetail(
            ticket_id=t.ticket_id,
            passenger_name=t.passenger_name,
            berth_number=t.berth_number,
            berth_type=t.berth_type,
            barcode_token=t.barcode_token,
            created_at=t.created_at
        )
        for t in pnr_record.tickets
    ]

    return IssueTicketResponse(
        status=pnr_record.status,
        pnr=pnr_record.pnr,
        booking_id=pnr_record.booking_id,
        quota_id=pnr_record.quota_id,
        event_name=pnr_record.event_name,
        tickets=ticket_details,
        created_at=pnr_record.created_at
    )

@app.post("/api/v1/tickets/cancel", response_model=CancelTicketResponse, tags=["Saga Compensation"])
async def cancel_tickets(req: CancelTicketRequest, db: AsyncSession = Depends(get_db)):
    """Compensating transaction: Cancels issued PNR upon upstream saga rollback."""
    repo = TicketingRepository(db)
    pnr_record = await repo.cancel_pnr(pnr=req.pnr, booking_id=req.booking_id)
    return CancelTicketResponse(
        status="CANCELLED",
        pnr=pnr_record.pnr,
        message=f"PNR '{pnr_record.pnr}' has been successfully cancelled."
    )

@app.post("/api/v1/tickets/reset", tags=["Testing & Benchmarking"])
async def reset_tickets(db: AsyncSession = Depends(get_db)):
    """Resets all PNRs and tickets for repeatable challenge testing."""
    repo = TicketingRepository(db)
    await repo.reset_seed_data()
    return {
        "status": "RESET_COMPLETE",
        "message": "Ticketing database cleared."
    }
