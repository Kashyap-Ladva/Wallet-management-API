from unittest.mock import patch
import os
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "sqlite:///./test_celery_db.db"

from app.database import engine, get_task_db, init_db
from app.models import Base, SWallet, User


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield


def test_get_task_db_creates_and_closes_session():
    """Verify get_task_db creates an active session and guarantees its closure upon exit."""
    with patch.object(Session, "close", autospec=True) as mock_close:
        with get_task_db() as db:
            assert isinstance(db, Session)

        # close() must be called to return connection to the pool
        assert mock_close.called


def test_get_task_db_rolls_back_on_exception():
    """Verify get_task_db rolls back transactions when an unhandled exception occurs."""
    with get_task_db() as db:
        user = User(
            name="Rollback Test User",
            phone="1112223334",
            email="rollback@example.com",
            currency="INR",
            password_hash="pwd",
        )
        db.add(user)
        db.flush()
        user_id = user.id
        db.commit()

    # Attempt to insert wallet but simulate task error
    with pytest.raises(RuntimeError, match="Simulated worker crash"):
        with get_task_db() as db:
            wallet = SWallet(user_id=user_id, name="Temp Wallet", currency="INR")
            db.add(wallet)
            db.flush()
            # Deliberate exception before commit
            raise RuntimeError("Simulated worker crash")

    # In a clean session, verify uncommitted wallet does not exist
    with get_task_db() as db:
        wallets = list(db.scalars(select(SWallet).where(SWallet.user_id == user_id)))
        assert len(wallets) == 0, "Uncommitted data must be rolled back on task exception"


def test_connection_leak_prevention_under_repeated_task_errors():
    """Verify repeated task failures do not leak database connections."""
    with get_task_db() as db:
        user = User(
            name="Leak Test User",
            phone="5556667778",
            email="leak_test@example.com",
            currency="INR",
            password_hash="pwd",
        )
        db.add(user)
        db.commit()

    # Run 15 failing tasks in sequence
    for i in range(15):
        try:
            with get_task_db() as db:
                db.execute(text("SELECT 1"))
                if i % 2 == 0:
                    raise ValueError(f"Forced error {i}")
                else:
                    raise RuntimeError(f"Forced failure {i}")
        except (ValueError, RuntimeError):
            pass

    # The engine pool must remain completely healthy and responsive
    with get_task_db() as db:
        res = db.execute(text("SELECT 1")).scalar()
        assert res == 1
        user_in_db = db.scalar(select(User).where(User.email == "leak_test@example.com"))
        assert user_in_db is not None
