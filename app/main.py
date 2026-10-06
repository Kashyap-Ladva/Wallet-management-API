from fastapi import FastAPI

from app.database import init_db
from app.routers.analytics import router as analytics_router
from app.routers.auth import router as auth_router
from app.routers.budgets import router as budgets_router
from app.routers.mini_wallets import router as mini_wallet_router
from app.routers.super_wallet import router as super_wallet_router
from app.routers.transactions import router as transaction_router
from app.routers.users import router as users_router

app = FastAPI(title="Wallet Management API")
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


@app.get("/health")
def health():
    return {"status": "healthy"}
