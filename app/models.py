from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
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

    