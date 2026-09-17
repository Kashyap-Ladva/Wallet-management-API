from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Wallet


def create_wallet(db: Session, name: str, currency: str) -> Wallet:
    wallet = Wallet(name=name, currency=currency, balance=0)
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


def get_wallets(db: Session) -> list[Wallet]:
    return list(db.scalars(select(Wallet).order_by(Wallet.id)))


def get_wallet(db: Session, wallet_id: int) -> Wallet | None:
    return db.get(Wallet, wallet_id)


def update_wallet(db: Session, wallet_id: int, updates: dict) -> Wallet | None:
    wallet = get_wallet(db, wallet_id)
    if wallet is None:
        return None

    for field, value in updates.items():
        setattr(wallet, field, value)
    db.commit()
    db.refresh(wallet)
    return wallet


def delete_wallet(db: Session, wallet_id: int) -> bool:
    wallet = get_wallet(db, wallet_id)
    if wallet is None:
        return False

    db.delete(wallet)
    db.commit()
    return True