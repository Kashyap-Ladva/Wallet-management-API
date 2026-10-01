import json
import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Transaction, Wallet

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required; set it in the project root .env file.")

engine = create_engine(DATABASE_URL)


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def init_db() -> None:
    database_exists = inspect(engine).has_table("wallets")
    Base.metadata.create_all(bind=engine)

    if database_exists:
        return

    wallets = _load_json(BASE_DIR / "data" / "wallets.json")
    transactions = _load_json(BASE_DIR / "data" / "transactions.json")
    if not wallets and not transactions:
        return

    with SessionLocal.begin() as db:
        for wallet_data in wallets:
            db.add(Wallet(**wallet_data))
        for transaction_data in transactions:
            db.add(Transaction(**transaction_data))