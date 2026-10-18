import os
import uuid
import time
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

SERVICE_NAME = os.getenv("SERVICE_NAME", "booking-service")
PORT = int(os.getenv("PORT", 8001))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "' + SERVICE_NAME + '", "message": "%(message)s"}'
)
logger = logging.getLogger(SERVICE_NAME)

app = FastAPI(
    title="SeatLock Booking Service",
    description="Saga orchestrator coordinating distributed reservations across Inventory, Payment, Ticketing & Notifications.",
    version="1.0.0",
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

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    corr_id = getattr(request.state, "correlation_id", "unknown")
    logger.error(f"Unhandled error: {str(exc)} correlation_id={corr_id}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred in booking-service",
            "correlation_id": corr_id,
            "service": SERVICE_NAME,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

@app.get("/health", tags=["Observability"])
async def health_check():
    return {
        "status": "UP",
        "service": SERVICE_NAME,
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/", tags=["Root"])
async def root():
    return {
        "service": SERVICE_NAME,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }
