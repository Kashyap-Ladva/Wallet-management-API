from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.database import init_db
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
from app.routers.transactions import router as transaction_router
from app.routers.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler(timezone="UTC")
    from app.jobs.daily_summary import run_daily_summary_job
    from app.jobs.monthly_reminders import run_monthly_reminders_job

    scheduler.add_job(
        run_daily_summary_job,
        CronTrigger(hour=23, minute=59, timezone="UTC"),
        id="daily-summary",
        replace_existing=True,
    )
    scheduler.add_job(
        run_monthly_reminders_job,
        CronTrigger(day=1, hour=0, minute=5, timezone="UTC"),
        id="monthly-reminders",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Wallet Management API", lifespan=lifespan)
init_db()


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


@app.get("/health")
def health():
    return {"status": "healthy"}
