from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import time

from app.config import settings
from app.database.mongodb import mongodb_manager
from app.db.database import create_tables
from app.api.router import api_router
from app.groq_provider.health import GroqHealthService
from app.utils.logging import setup_logging, get_logger
from app.utils.exceptions import DischargePilotException

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.LOG_DIR, exist_ok=True)

    create_tables()

    if await mongodb_manager.connect():
        await mongodb_manager.create_indexes()

    health = await GroqHealthService.check_connection(use_cache=False)
    if health["status"] == "healthy":
        logger.info("Groq initialization successful", model=health.get("model"))
    else:
        logger.error("Groq initialization failed", error=health.get("error"))

    logger.info(
        "DischargePilot AI started",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        upload_dir=str(settings.UPLOAD_DIR),
    )
    yield
    await mongodb_manager.disconnect()
    logger.info("DischargePilot AI shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agentic Clinical Discharge Summary Assistant — Phase 2: Document Intelligence Engine",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.perf_counter()
    request_id = request.headers.get("X-Request-ID", "")
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "HTTP request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
        request_id=request_id,
    )
    return response


@app.exception_handler(DischargePilotException)
async def dischargepilot_exception_handler(request: Request, exc: DischargePilotException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error, "detail": exc.detail, "code": exc.code},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", error=str(exc), path=request.url.path, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Check server logs.",
            "code": "INTERNAL_ERROR",
        },
    )


app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }
