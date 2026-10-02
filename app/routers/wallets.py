from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schema.super_wallet import SWalletCreate, SWalletResponse, SWalletUpdate
from app.services import wallet_service

router = APIRouter(prefix="/wallets", tags=["legacy-wallets"])


@router.post("", response_model=SWalletResponse, status_code=status.HTTP_201_CREATED)
def create_wallet(
    wallet: SWalletCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return wallet_service.create_super_wallet(db, current_user.id, wallet.name, wallet.currency)


@router.get("", response_model=list[SWalletResponse])
def get_wallets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return wallet_service.get_wallets_for_user(db, current_user.id)


@router.get("/{wallet_id}", response_model=SWalletResponse)
def get_wallet(
    wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wallet = wallet_service.get_super_wallet_by_id(db, current_user.id, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return wallet


@router.put("/{wallet_id}", response_model=SWalletResponse)
def update_wallet(
    wallet_id: int,
    wallet: SWalletUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated_wallet = wallet_service.update_super_wallet(
        db,
        current_user.id,
        wallet_id,
        wallet.model_dump(exclude_unset=True),
    )
    if updated_wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return updated_wallet


@router.delete("/{wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_wallet(
    wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not wallet_service.delete_super_wallet(db, current_user.id, wallet_id):
        raise HTTPException(status_code=404, detail="Wallet not found")
