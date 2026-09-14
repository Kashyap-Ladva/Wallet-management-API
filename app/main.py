from fastapi import FastAPI

from app.routers.transactions import router as transaction_router
from app.routers.wallets import router as wallet_router

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Wallet Management API"}


app.include_router(wallet_router)
app.include_router(transaction_router)


@app.get("/health")
def health():
    return {"status": "healthy"}
