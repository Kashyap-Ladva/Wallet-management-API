from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import logging

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.database import SessionLocal, get_task_db
from app.models import Budget, MWallet, Notification, SWallet, Transaction, User

logger = logging.getLogger("app.jobs.daily_summary")


def generate_daily_summary_for_user(
    db: Session,
    user: User,
    target_date: date,
) -> bool:
    """
    Generate a daily financial summary for a single user.
    Returns True if a notification was generated, False if already exists (deduplicated).
    """
    dedupe_key = f"daily-summary:{target_date.isoformat()}"
    existing = db.scalar(
        select(Notification.id).where(
            Notification.user_id == user.id,
            Notification.dedupe_key == dedupe_key,
        )
    )
    if existing is not None:
        return False

    start = datetime.combine(target_date, time.min)
    end = start + timedelta(days=1)
    month_start = datetime(target_date.year, target_date.month, 1)
    if target_date.month == 12:
        next_month = datetime(target_date.year + 1, 1, 1)
    else:
        next_month = datetime(target_date.year, target_date.month + 1, 1)

    wallet_transactions = db.execute(
        select(Transaction, MWallet.name)
        .join(MWallet, MWallet.id == Transaction.mini_wallet_id)
        .join(SWallet, SWallet.id == Transaction.super_wallet_id)
        .where(
            SWallet.user_id == user.id,
            Transaction.date_created >= start,
            Transaction.date_created < end,
        )
        .order_by(Transaction.date_created, Transaction.id)
    ).all()

    income = Decimal("0.00")
    expense = Decimal("0.00")
    categories: dict[str, Decimal] = {}
    wallets: dict[str, dict[str, Decimal]] = {}
    for transaction, wallet_name in wallet_transactions:
        bucket = wallets.setdefault(
            wallet_name,
            {"income": Decimal("0.00"), "expense": Decimal("0.00")},
        )
        if transaction.type == "income":
            income += transaction.amount
            bucket["income"] += transaction.amount
        else:
            expense += transaction.amount
            bucket["expense"] += transaction.amount
            categories[transaction.category] = (
                categories.get(transaction.category, Decimal("0.00"))
                + transaction.amount
            )

    month_transactions = list(
        db.scalars(
            select(Transaction).where(
                Transaction.super_wallet_id.in_(
                    select(SWallet.id).where(SWallet.user_id == user.id)
                ),
                Transaction.type == "expense",
                Transaction.date_created >= month_start,
                Transaction.date_created < next_month,
            )
        )
    )
    budgets = list(
        db.scalars(
            select(Budget)
            .join(SWallet, SWallet.id == Budget.super_wallet_id)
            .where(SWallet.user_id == user.id)
            .order_by(Budget.id)
        )
    )
    budget_status = []
    for budget in budgets:
        relevant_start, relevant_end = (
            (start, end) if budget.period == "daily" else (month_start, next_month)
        )
        candidates = (
            wallet_transactions
            if budget.period == "daily"
            else [(transaction, "") for transaction in month_transactions]
        )
        spent = sum(
            (
                transaction.amount
                for transaction, _ in candidates
                if transaction.type == "expense"
                and transaction.date_created >= relevant_start
                and transaction.date_created < relevant_end
                and (
                    budget.category is None
                    or transaction.category == budget.category
                )
                and transaction.super_wallet_id == budget.super_wallet_id
            ),
            Decimal("0.00"),
        )
        budget_status.append(
            {
                "budget_id": budget.id,
                "name": budget.name,
                "target": str(budget.amount),
                "spent": str(spent),
                "remaining": str(budget.amount - spent),
                "exceeded": spent > budget.amount,
            }
        )

    wallet_breakdown = []
    for name, totals in sorted(wallets.items()):
        wallet_breakdown.append(
            {
                "mini_wallet": name,
                "income": str(totals["income"]),
                "expense": str(totals["expense"]),
                "net": str(totals["income"] - totals["expense"]),
            }
        )
    category_breakdown = [
        {"category": name, "expense": str(total)}
        for name, total in sorted(categories.items())
    ]
    payload = {
        "date": target_date.isoformat(),
        "income": str(income),
        "expense": str(expense),
        "net": str(income - expense),
        "categories": category_breakdown,
        "mini_wallets": wallet_breakdown,
        "budgets": budget_status,
    }
    db.add(
        Notification(
            user_id=user.id,
            kind="daily_summary",
            dedupe_key=dedupe_key,
            message=(
                f"Daily summary for {target_date.isoformat()}: "
                f"income {income}, expenses {expense}, net {income - expense}."
            ),
            payload=payload,
        )
    )
    return True


def generate_daily_summaries(
    db: Session,
    summary_date: date | None = None,
) -> int:
    target_date = summary_date or datetime.now(timezone.utc).date()
    users = list(db.scalars(select(User).order_by(User.id)))
    generated = 0

    for user in users:
        try:
            with db.begin_nested():
                if generate_daily_summary_for_user(db, user, target_date):
                    generated += 1
            db.commit()
        except Exception as exc:
            logger.error("Error generating daily summary for user %d: %s", user.id, exc)
            db.rollback()
            continue

    return generated


def run_daily_summary_job() -> int:
    with get_task_db() as db:
        return generate_daily_summaries(db)


@celery_app.task(
    name="app.jobs.daily_summary.generate_daily_summaries_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
    retry_jitter=True,
)
def generate_daily_summaries_task(self, target_date_str: str | None = None) -> dict:
    """
    Celery task to generate daily financial summaries for all users.
    Idempotent and protected against transient database connection failures.
    """
    target_date = date.fromisoformat(target_date_str) if target_date_str else None
    with get_task_db() as db:
        count = generate_daily_summaries(db, target_date)
        resolved_date = target_date or datetime.now(timezone.utc).date()
        return {
            "status": "SUCCESS",
            "summaries_generated": count,
            "target_date": resolved_date.isoformat(),
        }


@celery_app.task(
    name="app.jobs.daily_summary.generate_user_daily_summary_task",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(OperationalError, DBAPIError),
    retry_backoff=True,
)
def generate_user_daily_summary_task(self, user_id: int, target_date_str: str | None = None) -> dict:
    """
    Celery task to generate a daily summary for a specific user on-demand.
    """
    target_date = (
        date.fromisoformat(target_date_str)
        if target_date_str
        else datetime.now(timezone.utc).date()
    )
    with get_task_db() as db:
        user = db.get(User, user_id)
        if not user:
            return {"status": "FAILED", "reason": "User not found", "user_id": user_id}
        generated = generate_daily_summary_for_user(db, user, target_date)
        db.commit()
        return {
            "status": "SUCCESS",
            "generated": generated,
            "user_id": user_id,
            "target_date": target_date.isoformat(),
        }
