import json
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Transaction, Wallet

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR.parent / "wallets.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


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
    database_exists = DATABASE_PATH.exists()
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