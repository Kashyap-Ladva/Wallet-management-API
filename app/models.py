from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    wallet: Mapped["SWallet | None"] = relationship(back_populates="user")
    savings_goals: Mapped[list["SavingsGoal"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    investments: Mapped[list["Investment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    debts: Mapped[list["Debt"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    recurring_payments: Mapped[list["RecurringPayment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class SWallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    modeofpayment: Mapped[str] = mapped_column(String, nullable=False, default="wallet")
    user: Mapped[User] = relationship(back_populates="wallet")
    mini_wallets: Mapped[list["MWallet"]] = relationship(
        back_populates="super_wallet",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="super_wallet",
        foreign_keys="Transaction.super_wallet_id",
        cascade="all, delete-orphan",
    )
    budgets: Mapped[list["Budget"]] = relationship(
        back_populates="super_wallet",
        cascade="all, delete-orphan",
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    @property
    def total_balance(self) -> Decimal:
        return sum((wallet.balance for wallet in self.mini_wallets), Decimal("0.00"))


class MWallet(Base):
    __tablename__ = "mini_wallets"
    
    
    __table_args__ = (
        UniqueConstraint("super_wallet_id", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    super_wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    modeofpayment: Mapped[str] = mapped_column(String, nullable=False)
    super_wallet: Mapped[SWallet] = relationship(back_populates="mini_wallets")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="mini_wallet",
        foreign_keys="Transaction.mini_wallet_id",
        cascade="all, delete-orphan",
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    @property
    def balance(self) -> Decimal:
        return sum(
            (
                transaction.amount
                if transaction.type == "income"
                else -transaction.amount
                for transaction in self.transactions
            ),
            Decimal("0.00"),
        )


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    super_wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    period: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    super_wallet: Mapped[SWallet] = relationship(back_populates="budgets")
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "type IN ('income', 'expense')",
            name="ck_transactions_type_valid",
        ),
        ForeignKeyConstraint(
            ["super_wallet_id", "mini_wallet_id"],
            ["mini_wallets.super_wallet_id", "mini_wallets.id"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mini_wallet_id: Mapped[int] = mapped_column(
        ForeignKey("mini_wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    super_wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    modeofpayment: Mapped[str] = mapped_column(String, nullable=False)
    proof: Mapped[str | None] = mapped_column(String, nullable=True)
    mini_wallet: Mapped[MWallet] = relationship(
        back_populates="transactions",
        foreign_keys=[mini_wallet_id],
    )
    super_wallet: Mapped[SWallet] = relationship(
        back_populates="transactions",
        foreign_keys=[super_wallet_id],
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class SavingsGoal(Base):
    __tablename__ = "savings_goals"
    __table_args__ = (
        CheckConstraint("target_amount > 0", name="ck_savings_target_positive"),
        CheckConstraint("current_amount >= 0", name="ck_savings_current_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    target_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("0.00")
    )
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    user: Mapped[User] = relationship(back_populates="savings_goals")
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class Investment(Base):
    __tablename__ = "investments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_investments_amount_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    investment_type: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user: Mapped[User] = relationship(back_populates="investments")
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class Debt(Base):
    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_debts_amount_positive"),
        CheckConstraint(
            "remaining_amount >= 0 AND remaining_amount <= amount",
            name="ck_debts_remaining_range",
        ),
        CheckConstraint(
            "direction IN ('lent', 'borrowed')",
            name="ck_debts_direction_valid",
        ),
        CheckConstraint(
            "status IN ('pending', 'partially_paid', 'settled')",
            name="ck_debts_status_valid",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    person: Mapped[str] = mapped_column(String, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    remaining_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    user: Mapped[User] = relationship(back_populates="debts")
    repayments: Mapped[list["DebtRepayment"]] = relationship(
        back_populates="debt",
        cascade="all, delete-orphan",
    )
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class DebtRepayment(Base):
    __tablename__ = "debt_repayments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_debt_repayments_amount_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    debt_id: Mapped[int] = mapped_column(
        ForeignKey("debts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    debt: Mapped[Debt] = relationship(back_populates="repayments")


class RecurringPayment(Base):
    __tablename__ = "recurring_payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_recurring_amount_positive"),
        CheckConstraint(
            "due_day BETWEEN 1 AND 31",
            name="ck_recurring_due_day_valid",
        ),
        CheckConstraint(
            "frequency = 'monthly'",
            name="ck_recurring_frequency_monthly",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    due_day: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[str] = mapped_column(String, nullable=False, default="monthly")
    active: Mapped[bool] = mapped_column(nullable=False, default=True)
    user: Mapped[User] = relationship(back_populates="recurring_payments")
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "dedupe_key",
            name="uq_notifications_user_dedupe_key",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String, nullable=False)
    recurring_payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_payments.id", ondelete="CASCADE"),
        nullable=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    date_created: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    