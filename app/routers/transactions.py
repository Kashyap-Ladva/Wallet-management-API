from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models import MWallet, Transaction, User
from app.schema.transaction import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from app.services import transaction_service

router = APIRouter(tags=["transactions"])


def _ensure_owned_mini_wallet(
    db: Session,
    current_user: User,
    mini_wallet_id: int,
) -> MWallet:
    mini_wallet = db.get(MWallet, mini_wallet_id)
    if mini_wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mini wallet not found")
    if mini_wallet.super_wallet.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: you do not own this mini wallet",
        )
    return mini_wallet


def _ensure_owned_transaction(
    db: Session,
    current_user: User,
    transaction_id: int,
) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    if transaction.super_wallet.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: you do not own this transaction",
        )
    return transaction


def _effect_for(transaction_type: str, amount: Decimal) -> Decimal:
    return amount if transaction_type == "income" else -amount


@router.post(
    "/mini-wallets/{mini_wallet_id}/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    mini_wallet_id: int,
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mini_wallet = _ensure_owned_mini_wallet(db, current_user, mini_wallet_id)
    if payload.type == "expense" and mini_wallet.balance < payload.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")

    try:
        transaction = transaction_service.create_transaction(
            db,
            mini_wallet_id,
            payload.model_dump(exclude_none=True),
        )

        db.commit()
        return transaction
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

@router.get("/mini-wallets/{mini_wallet_id}/transactions", response_model=list[TransactionResponse])
def list_transactions_for_mini_wallet(
    mini_wallet_id: int,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    modeofpayment: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_owned_mini_wallet(db, current_user, mini_wallet_id)
    query = (
        db.query(Transaction)
        .filter(Transaction.mini_wallet_id == mini_wallet_id)
        .order_by(Transaction.date_created.desc(), Transaction.id.desc())
    )
    if date_from:
        query = query.filter(Transaction.date_created >= date_from)
    if date_to:
        query = query.filter(Transaction.date_created <= date_to)
    if type:
        query = query.filter(Transaction.type == type)
    if category:
        query = query.filter(Transaction.category == category)
    if modeofpayment:
        query = query.filter(Transaction.modeofpayment == modeofpayment)

    return query.offset(offset).limit(limit).all()


@router.get("/super-wallet/transactions", response_model=list[TransactionResponse])
def list_transactions_for_super_wallet(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    modeofpayment: str | None = Query(default=None),
    mini_wallet_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    super_wallet = current_user.wallet
    if super_wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Super wallet not found")

    query = db.query(Transaction).filter(Transaction.super_wallet_id == super_wallet.id)
    if date_from:
        query = query.filter(Transaction.date_created >= date_from)
    if date_to:
        query = query.filter(Transaction.date_created <= date_to)
    if type:
        query = query.filter(Transaction.type == type)
    if category:
        query = query.filter(Transaction.category == category)
    if modeofpayment:
        query = query.filter(Transaction.modeofpayment == modeofpayment)
    if mini_wallet_id:
        query = query.filter(Transaction.mini_wallet_id == mini_wallet_id)

    return query.order_by(Transaction.date_created.desc(), Transaction.id.desc()).offset(offset).limit(limit).all()


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = _ensure_owned_transaction(db, current_user, transaction_id)
    return transaction


@router.put("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = _ensure_owned_transaction(db, current_user, transaction_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return existing

    current_balance = existing.mini_wallet.balance
    old_effect = _effect_for(existing.type, existing.amount)
    projected_balance = current_balance - old_effect

    if "type" in updates or "amount" in updates:
        new_type = updates.get("type", existing.type)
        new_amount = updates.get("amount", existing.amount)
        projected_balance += _effect_for(new_type, new_amount)
        if new_type == "expense" and projected_balance < 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient balance")

    try:
        updated = transaction_service.update_transaction(
            db,
            transaction_id,
            updates,
        )

        if updated is None:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found",
            )

        db.commit()

        return updated

    except HTTPException:
        db.rollback()
        raise

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise
    


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    transaction = _ensure_owned_transaction(
        db,
        current_user,
        transaction_id,
    )

    try:
        deleted = transaction_service.delete_transaction(
            db,
            transaction_id,
        )

        if not deleted:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found",
            )

        db.commit()

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise


@router.get("/mini-wallets/{mini_wallet_id}/balance")
def get_mini_wallet_balance(
    mini_wallet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mini_wallet = _ensure_owned_mini_wallet(db, current_user, mini_wallet_id)
    return {"mini_wallet_id": mini_wallet_id, "balance": mini_wallet.balance}


@router.get("/super-wallet/balance")
def get_super_wallet_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wallet = current_user.wallet
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Super wallet not found")
    return {"super_wallet_id": wallet.id, "balance": wallet.total_balance}

