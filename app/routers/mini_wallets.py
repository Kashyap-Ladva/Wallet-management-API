from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schema.mini_wallet import MWalletCreate, MWalletResponse, MWalletUpdate
from app.services import wallet_service

router = APIRouter(tags=["mini-wallets"])


@router.post("/super-wallet/mini-wallets", response_model=MWalletResponse, status_code=status.HTTP_201_CREATED)
def create_mini_wallet(
    payload: MWalletCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return wallet_service.create_mini_wallet(
            db,
            current_user.id,
            payload.name,
            payload.modeofpayment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/super-wallet/mini-wallets", response_model=list[MWalletResponse])
def get_mini_wallets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return wallet_service.get_mini_wallets_for_user(db, current_user.id)


@router.get("/mini-wallets/{mini_wallet_id}", response_model=MWalletResponse)
def get_mini_wallet(
    mini_wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mini_wallet = db.get(wallet_service.MWallet, mini_wallet_id)
    if mini_wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mini wallet not found")
    if mini_wallet.super_wallet.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: you do not own this mini wallet",
        )
    return mini_wallet


@router.put("/mini-wallets/{mini_wallet_id}", response_model=MWalletResponse)
def update_mini_wallet(
    mini_wallet_id: int,
    payload: MWalletUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mini_wallet = db.get(wallet_service.MWallet, mini_wallet_id)
    if mini_wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mini wallet not found")
    if mini_wallet.super_wallet.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: you do not own this mini wallet",
        )

    updated = wallet_service.update_mini_wallet(
        db,
        current_user.id,
        mini_wallet_id,
        payload.model_dump(exclude_unset=True),
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mini wallet not found")
    return updated


@router.delete("/mini-wallets/{mini_wallet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mini_wallet(
    mini_wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mini_wallet = db.get(wallet_service.MWallet, mini_wallet_id)
    if mini_wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mini wallet not found")
    if mini_wallet.super_wallet.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: you do not own this mini wallet",
        )
    if not wallet_service.delete_mini_wallet(db, current_user.id, mini_wallet_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mini wallet not found")
