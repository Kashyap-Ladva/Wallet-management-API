from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MWallet, SWallet


def create_super_wallet(db: Session, user_id: int, name: str, currency: str) -> SWallet:
    existing = db.query(SWallet).filter(SWallet.user_id == user_id).first()
    if existing is not None:
        raise ValueError("User already has a super wallet")

    wallet = SWallet(
        user_id=user_id,
        name=name.strip(),
        currency=currency.strip(),
        modeofpayment="wallet",
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    return wallet


def get_super_wallet_for_user(db: Session, user_id: int) -> SWallet | None:
    return db.query(SWallet).filter(SWallet.user_id == user_id).first()


def get_wallets_for_user(db: Session, user_id: int) -> list[SWallet]:
    return list(db.scalars(select(SWallet).where(SWallet.user_id == user_id).order_by(SWallet.id)))


def get_super_wallet_by_id(db: Session, user_id: int, wallet_id: int) -> SWallet | None:
    wallet = db.get(SWallet, wallet_id)
    if wallet is None or wallet.user_id != user_id:
        return None
    return wallet


def update_super_wallet(
    db: Session,
    user_id: int,
    wallet_id: int,
    updates: dict,
) -> SWallet | None:
    wallet = get_super_wallet_by_id(db, user_id, wallet_id)
    if wallet is None:
        return None

    for field, value in updates.items():
        if value is None:
            continue
        if field in {"name", "currency"}:
            setattr(wallet, field, str(value).strip())
    db.commit()
    db.refresh(wallet)
    return wallet


def delete_super_wallet(db: Session, user_id: int, wallet_id: int) -> bool:
    wallet = get_super_wallet_by_id(db, user_id, wallet_id)
    if wallet is None:
        return False

    db.delete(wallet)
    db.commit()
    return True


def create_mini_wallet(db: Session, user_id: int, name: str, modeofpayment: str) -> MWallet:
    super_wallet = get_super_wallet_for_user(db, user_id)
    if super_wallet is None:
        raise ValueError("Super wallet not found")

    mini_wallet = MWallet(
        super_wallet_id=super_wallet.id,
        name=name.strip(),
        modeofpayment=modeofpayment.strip(),
    )
    db.add(mini_wallet)
    db.commit()
    db.refresh(mini_wallet)
    return mini_wallet


def get_mini_wallets_for_user(db: Session, user_id: int) -> list[MWallet]:
    super_wallet = get_super_wallet_for_user(db, user_id)
    if super_wallet is None:
        return []
    return list(
        db.scalars(
            select(MWallet)
            .where(MWallet.super_wallet_id == super_wallet.id)
            .order_by(MWallet.id)
        )
    )


def get_mini_wallet_by_id(db: Session, user_id: int, mini_wallet_id: int) -> MWallet | None:
    mini_wallet = db.get(MWallet, mini_wallet_id)
    if mini_wallet is None:
        return None
    if mini_wallet.super_wallet.user_id != user_id:
        return None
    return mini_wallet


def update_mini_wallet(
    db: Session,
    user_id: int,
    mini_wallet_id: int,
    updates: dict,
) -> MWallet | None:
    mini_wallet = get_mini_wallet_by_id(db, user_id, mini_wallet_id)
    if mini_wallet is None:
        return None

    for field, value in updates.items():
        if value is None:
            continue
        if field in {"name", "modeofpayment"}:
            setattr(mini_wallet, field, str(value).strip())
    db.commit()
    db.refresh(mini_wallet)
    return mini_wallet


def delete_mini_wallet(db: Session, user_id: int, mini_wallet_id: int) -> bool:
    mini_wallet = get_mini_wallet_by_id(db, user_id, mini_wallet_id)
    if mini_wallet is None:
        return False

    db.delete(mini_wallet)
    db.commit()
    return True


def create_wallet(db: Session, name: str, currency: str) -> SWallet:
    return create_super_wallet(db, 1, name, currency)


def get_wallets(db: Session) -> list[SWallet]:
    return list(db.scalars(select(SWallet).order_by(SWallet.id)))


def get_wallet(db: Session, wallet_id: int) -> SWallet | None:
    return db.get(SWallet, wallet_id)


def update_wallet(db: Session, wallet_id: int, updates: dict) -> SWallet | None:
    wallet = get_wallet(db, wallet_id)
    if wallet is None:
        return None
    for field, value in updates.items():
        if value is None:
            continue
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