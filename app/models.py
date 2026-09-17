from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String, nullable=False)
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="wallet",
        cascade="all, delete-orphan",
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    wallet: Mapped[Wallet] = relationship(back_populates="transactions")