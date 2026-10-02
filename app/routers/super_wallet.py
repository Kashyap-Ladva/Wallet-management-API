from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import User
from app.schema.super_wallet import SWalletCreate, SWalletResponse, SWalletUpdate
from app.services import wallet_service

router = APIRouter(tags=["super-wallet"])


@router.post("/super-wallet", response_model=SWalletResponse, status_code=status.HTTP_201_CREATED)
def create_super_wallet(
    payload: SWalletCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return wallet_service.create_super_wallet(
            db,
            current_user.id,
            payload.name,
            payload.currency,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/super-wallet", response_model=SWalletResponse)
def get_super_wallet(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wallet = wallet_service.get_super_wallet_for_user(db, current_user.id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Super wallet not found")
    return wallet


@router.put("/super-wallet", response_model=SWalletResponse)
def update_super_wallet(
    payload: SWalletUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wallet = wallet_service.get_super_wallet_for_user(db, current_user.id)
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Super wallet not found")

    return wallet_service.update_super_wallet(
        db,
        current_user.id,
        wallet.id,
        payload.model_dump(exclude_unset=True),
    )
