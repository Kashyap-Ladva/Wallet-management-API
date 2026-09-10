from fastapi import FastAPI, HTTPException, status

from app.schema.wallet import WalletCreate, WalletResponse, WalletUpdate
from app.services import wallet_service

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Wallet Management API"}


@app.post(
    "/wallets",
    response_model=WalletResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_wallet(wallet: WalletCreate):
    return wallet_service.create_wallet(wallet.name, wallet.currency)


@app.get("/wallets", response_model=list[WalletResponse])
def get_wallets():
    return wallet_service.get_wallets()


@app.get("/wallets/{wallet_id}", response_model=WalletResponse)
def get_wallet(wallet_id: int):
    wallet = wallet_service.get_wallet(wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@app.put("/wallets/{wallet_id}", response_model=WalletResponse)
def update_wallet(wallet_id: int, wallet: WalletUpdate):
    updated_wallet = wallet_service.update_wallet(
        wallet_id,
        wallet.dict(exclude_unset=True),
    )
    if updated_wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return updated_wallet


@app.delete("/wallets/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wallet(wallet_id: int):
    if not wallet_service.delete_wallet(wallet_id):
        raise HTTPException(status_code=404, detail="Wallet not found")


@app.get("/health")
def health():
    return {"status": "healthy"}
