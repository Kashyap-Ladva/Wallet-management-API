from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Budget, MWallet, Notification, SWallet, Transaction, User


def generate_daily_summaries(
    db: Session,
    summary_date: date | None = None,
) -> int:
    target_date = summary_date or datetime.now(timezone.utc).date()
    start = datetime.combine(target_date, time.min)
    end = start + timedelta(days=1)
    month_start = datetime(target_date.year, target_date.month, 1)
    if target_date.month == 12:
        next_month = datetime(target_date.year + 1, 1, 1)
    else:
        next_month = datetime(target_date.year, target_date.month + 1, 1)

    users = list(db.scalars(select(User).order_by(User.id)))
    generated = 0
    for user in users:
        dedupe_key = f"daily-summary:{target_date.isoformat()}"
        existing = db.scalar(
            select(Notification.id).where(
                Notification.user_id == user.id,
                Notification.dedupe_key == dedupe_key,
            )
        )
        if existing is not None:
            continue

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
        generated += 1

    db.commit()
    return generated


def run_daily_summary_job() -> int:
    from app.database import SessionLocal

    with SessionLocal() as db:
        return generate_daily_summaries(db)
