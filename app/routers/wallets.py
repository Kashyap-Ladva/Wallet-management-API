from fastapi import APIRouter, HTTPException, status

from app.schema.wallet import WalletCreate, WalletResponse, WalletUpdate
from app.services import wallet_service

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.post("", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
def create_wallet(wallet: WalletCreate):
    return wallet_service.create_wallet(wallet.name, wallet.currency)


@router.get("", response_model=list[WalletResponse])
def get_wallets():
    return wallet_service.get_wallets()


@router.get("/{wallet_id}", response_model=WalletResponse)
def get_wallet(wallet_id: int):
    wallet = wallet_service.get_wallet(wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.put("/{wallet_id}", response_model=WalletResponse)
def update_wallet(wallet_id: int, wallet: WalletUpdate):
    updated_wallet = wallet_service.update_wallet(
        wallet_id,
        wallet.dict(exclude_unset=True),
    )
    if updated_wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return updated_wallet


@router.delete("/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wallet(wallet_id: int):
    if not wallet_service.delete_wallet(wallet_id):
        raise HTTPException(status_code=404, detail="Wallet not found")
