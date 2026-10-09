from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Investment


def _get_investment(
    db: Session,
    user_id: int,
    investment_id: int,
) -> Investment | None:
    return db.scalar(
        select(Investment).where(
            Investment.id == investment_id,
            Investment.user_id == user_id,
        )
    )


def create_investment(db: Session, user_id: int, payload: dict) -> Investment:
    investment = Investment(user_id=user_id, **payload)
    db.add(investment)
    db.commit()
    db.refresh(investment)
    return investment


def list_investments(db: Session, user_id: int) -> list[Investment]:
    return list(
        db.scalars(
            select(Investment)
            .where(Investment.user_id == user_id)
            .order_by(Investment.date.desc(), Investment.id.desc())
        )
    )


def get_investment(
    db: Session,
    user_id: int,
    investment_id: int,
) -> Investment | None:
    return _get_investment(db, user_id, investment_id)


def update_investment(
    db: Session,
    user_id: int,
    investment_id: int,
    updates: dict,
) -> Investment | None:
    investment = _get_investment(db, user_id, investment_id)
    if investment is None:
        return None
    for field, value in updates.items():
        if value is None and field != "notes":
            continue
        if field in {"name", "investment_type"}:
            value = value.strip()
        setattr(investment, field, value)
    db.commit()
    db.refresh(investment)
    return investment


def delete_investment(db: Session, user_id: int, investment_id: int) -> bool:
    investment = _get_investment(db, user_id, investment_id)
    if investment is None:
        return False
    db.delete(investment)
    db.commit()
    return True
