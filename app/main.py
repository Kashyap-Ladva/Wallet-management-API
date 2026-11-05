from contextlib import asynccontextmanager
import logging
import os
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.redis import check_redis_health, close_redis, init_redis
from app.database import get_db, init_db
from app.routers.analytics import router as analytics_router
from app.routers.auth import router as auth_router
from app.routers.budgets import router as budgets_router
from app.routers.debts import router as debts_router
from app.routers.imports import router as imports_router
from app.routers.investments import router as investments_router
from app.routers.mini_wallets import router as mini_wallet_router
from app.routers.notifications import router as notifications_router
from app.routers.recurring_payments import router as recurring_payments_router
from app.routers.savings import router as savings_router
from app.routers.super_wallet import router as super_wallet_router
from app.routers.tasks import router as tasks_router
from app.routers.transactions import router as transaction_router
from app.routers.users import router as users_router

# Configure structured logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s:%(message)s",
)
logger = logging.getLogger("app.api")


class CeleryBeatSchedulerState:
    """Compatibility proxy indicating Celery Beat is responsible for scheduled tasks."""
    running = True

    def shutdown(self, wait: bool = False) -> None:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler_enabled = os.getenv("SCHEDULER_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    if scheduler_enabled:
        app.state.scheduler = CeleryBeatSchedulerState()
        app.state.scheduler_running = True
        logger.info("Background job scheduling handled by Celery Beat")
    else:
        app.state.scheduler = None
        app.state.scheduler_running = False
        logger.info("Background job scheduler disabled by configuration")

    # Initialize Redis connection pool
    await init_redis(app)

    try:
        yield
    finally:
        await close_redis(app)


app = FastAPI(title="Wallet Management API", lifespan=lifespan)
init_db()


class SecurityAndObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid4().hex
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "Unhandled error processing request: %s %s [%.2fms] req_id=%s",
                request.method,
                request.url.path,
                duration_ms,
                request_id,
            )
            response = JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                },
            )

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "%s %s -> %d (%.2fms) req_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response


app.add_middleware(SecurityAndObservabilityMiddleware)


@app.get("/")
def home():
    return {"message": "Wallet Management API"}


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(super_wallet_router)
app.include_router(mini_wallet_router)
app.include_router(transaction_router)
app.include_router(analytics_router)
app.include_router(budgets_router)
app.include_router(imports_router)
app.include_router(savings_router)
app.include_router(investments_router)
app.include_router(debts_router)
app.include_router(recurring_payments_router)
app.include_router(notifications_router)
app.include_router(tasks_router)


@app.get("/health", tags=["system"])
async def health(db: Session = Depends(get_db)):
    redis_status = await check_redis_health()
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "degraded",
                "database": "unavailable",
                "redis": redis_status,
                "detail": str(exc),
            },
        )
    return {
        "status": "healthy",
        "database": db_status,
        "redis": redis_status,
        "scheduler": "running"
        if getattr(app.state, "scheduler_running", False)
        else "disabled",
    }


@app.get("/ready", tags=["system"])
async def readiness(db: Session = Depends(get_db)):
    redis_status = await check_redis_health()
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "unavailable",
                "redis": redis_status,
                "detail": str(exc),
            },
        )
    return {
        "status": "ready",
        "database": db_status,
        "redis": redis_status,
    }
