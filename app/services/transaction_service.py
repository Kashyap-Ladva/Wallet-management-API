from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MWallet, Transaction


def transaction_effect(transaction_type: str, amount: Decimal) -> Decimal:
    return amount if transaction_type == "income" else -amount


def create_transaction(
    db: Session,
    mini_wallet_id: int,
    payload: dict,
) -> Transaction:
    mini_wallet = db.get(MWallet, mini_wallet_id)
    if mini_wallet is None:
        raise ValueError("Mini wallet not found")

    transaction = Transaction(
        mini_wallet_id=mini_wallet_id,
        super_wallet_id=mini_wallet.super_wallet_id,
        amount=payload["amount"],
        type=payload["type"],
        category=(payload.get("category") or "").strip(),
        description=payload.get("description"),
        modeofpayment=(payload.get("modeofpayment") or "").strip(),
        proof=payload.get("proof"),
        date_created=payload.get("date_created") or datetime.utcnow(),
    )
    db.add(transaction)
    db.flush()
    db.refresh(transaction)
    return transaction


def get_mini_wallet_transactions(db: Session, mini_wallet_id: int) -> list[Transaction]:
    statement = (
        select(Transaction)
        .where(Transaction.mini_wallet_id == mini_wallet_id)
        .order_by(Transaction.date_created.desc(), Transaction.id.desc())
    )
    return list(db.scalars(statement))


def get_super_wallet_transactions(db: Session, super_wallet_id: int) -> list[Transaction]:
    statement = (
        select(Transaction)
        .where(Transaction.super_wallet_id == super_wallet_id)
        .order_by(Transaction.date_created.desc(), Transaction.id.desc())
    )
    return list(db.scalars(statement))


def get_transaction(db: Session, transaction_id: int) -> Transaction | None:
    return db.get(Transaction, transaction_id)


def update_transaction(db: Session, transaction_id: int, updates: dict) -> Transaction | None:
    transaction = get_transaction(db, transaction_id)
    if transaction is None:
        return None

    for field, value in updates.items():
        if value is None:
            continue
        setattr(transaction, field, value)
    db.flush()
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, transaction_id: int) -> bool:
    transaction = get_transaction(db, transaction_id)
    if transaction is None:
        return False

    db.delete(transaction)
    db.flush()
    return True