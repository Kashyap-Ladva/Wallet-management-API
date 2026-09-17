from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction


def create_transaction(
    db: Session,
    wallet_id: int,
    amount: float,
    transaction_type: str,
    category: str,
    description: str | None,
) -> Transaction:
    transaction = Transaction(
        wallet_id=wallet_id,
        amount=amount,
        type=transaction_type,
        category=category,
        description=description,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def get_wallet_transactions(db: Session, wallet_id: int) -> list[Transaction]:
    statement = select(Transaction).where(Transaction.wallet_id == wallet_id).order_by(Transaction.id)
    return list(db.scalars(statement))


def get_transaction(db: Session, transaction_id: int) -> Transaction | None:
    return db.get(Transaction, transaction_id)


def update_transaction(db: Session, transaction_id: int, updates: dict) -> Transaction | None:
    transaction = get_transaction(db, transaction_id)
    if transaction is None:
        return None

    for field, value in updates.items():
        setattr(transaction, field, value)
    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction(db: Session, transaction_id: int) -> bool:
    transaction = get_transaction(db, transaction_id)
    if transaction is None:
        return False

    db.delete(transaction)
    db.commit()
    return True