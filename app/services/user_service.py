from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User


def get_user_by_email(db: Session, email: str) -> User | None:
    normalized = email.strip().lower()
    return db.query(User).filter(User.email == normalized).first()


def get_user_by_phone(db: Session, phone: str) -> User | None:
    normalized = phone.strip()
    return db.query(User).filter(User.phone == normalized).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def create_user(db: Session, data) -> User:
    user = User(
        name=data.name.strip(),
        phone=data.phone.strip(),
        email=data.email.strip().lower(),
        currency=data.currency.strip(),
        password_hash=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, updates: dict) -> User:
    for field, value in updates.items():
        if value is None:
            continue
        if field == "email" and str(value).strip():
            setattr(user, field, str(value).strip().lower())
        elif field in {"name", "phone", "currency"} and str(value).strip():
            setattr(user, field, str(value).strip())
    db.commit()
    db.refresh(user)
    return user
