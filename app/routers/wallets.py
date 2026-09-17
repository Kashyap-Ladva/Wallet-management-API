from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schema.wallet import WalletCreate, WalletResponse, WalletUpdate
from app.services import wallet_service

router = APIRouter(prefix="/wallets", tags=["wallets"])


@router.post("", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
def create_wallet(wallet: WalletCreate, db: Session = Depends(get_db)):
    return wallet_service.create_wallet(db, wallet.name, wallet.currency)


@router.get("", response_model=list[WalletResponse])
def get_wallets(db: Session = Depends(get_db)):
    return wallet_service.get_wallets(db)


@router.get("/{wallet_id}", response_model=WalletResponse)
def get_wallet(wallet_id: int, db: Session = Depends(get_db)):
    wallet = wallet_service.get_wallet(db, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.put("/{wallet_id}", response_model=WalletResponse)
def update_wallet(wallet_id: int, wallet: WalletUpdate, db: Session = Depends(get_db)):
    updated_wallet = wallet_service.update_wallet(
        db,
        wallet_id,
        wallet.model_dump(exclude_unset=True),
    )
    if updated_wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return updated_wallet


@router.delete("/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wallet(wallet_id: int, db: Session = Depends(get_db)):
    if not wallet_service.delete_wallet(db, wallet_id):
        raise HTTPException(status_code=404, detail="Wallet not found")
