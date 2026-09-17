from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schema.transaction import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
)
from app.services import transaction_service, wallet_service

router = APIRouter(tags=["transactions"])


@router.post(
    "/wallets/{wallet_id}/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    wallet_id: int,
    transaction: TransactionCreate,
    db: Session = Depends(get_db),
):
    wallet = wallet_service.get_wallet(db, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    if transaction.type == "expense" and transaction.amount > wallet.balance:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    new_balance = (
        wallet.balance + transaction.amount
        if transaction.type == "income"
        else wallet.balance - transaction.amount
    )
    wallet_service.update_wallet(db, wallet_id, {"balance": new_balance})
    return transaction_service.create_transaction(
        db,
        wallet_id,
        transaction.amount,
        transaction.type,
        transaction.category,
        transaction.description,
    )


@router.get("/wallets/{wallet_id}/transactions", response_model=list[TransactionResponse])
def get_transactions(wallet_id: int, db: Session = Depends(get_db)):
    if wallet_service.get_wallet(db, wallet_id) is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return transaction_service.get_wallet_transactions(db, wallet_id)


@router.get("/transactions/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = transaction_service.get_transaction(db, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.put("/transactions/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    transaction: TransactionUpdate,
    db: Session = Depends(get_db),
):
    existing = transaction_service.get_transaction(db, transaction_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    wallet = wallet_service.get_wallet(db, existing.wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    updates = transaction.model_dump(exclude_unset=True)
    previous_amount = existing.amount
    previous_type = existing.type

    if previous_type == "income":
        wallet.balance -= previous_amount
    else:
        wallet.balance += previous_amount

    if updates.get("type") is not None or updates.get("amount") is not None:
        new_type = updates.get("type", previous_type)
        new_amount = updates.get("amount", previous_amount)
        if new_type == "income":
            wallet.balance += new_amount
        else:
            wallet.balance -= new_amount
            if wallet.balance < 0:
                raise HTTPException(status_code=400, detail="Insufficient balance")

    updated_transaction = transaction_service.update_transaction(db, transaction_id, updates)
    if updated_transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    wallet_service.update_wallet(db, existing.wallet_id, {"balance": wallet.balance})
    return updated_transaction


@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = transaction_service.get_transaction(db, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    wallet = wallet_service.get_wallet(db, transaction.wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    if transaction.type == "income":
        wallet.balance -= transaction.amount
    else:
        wallet.balance += transaction.amount

    wallet_service.update_wallet(db, transaction.wallet_id, {"balance": wallet.balance})
    if not transaction_service.delete_transaction(db, transaction_id):
        raise HTTPException(status_code=404, detail="Transaction not found")


@router.get("/wallets/{wallet_id}/balance")
def get_balance(wallet_id: int, db: Session = Depends(get_db)):
    wallet = wallet_service.get_wallet(db, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return {"wallet_id": wallet_id, "balance": wallet.balance}


@router.get("/wallets/{wallet_id}/summary")
def get_summary(wallet_id: int, db: Session = Depends(get_db)):
    wallet = wallet_service.get_wallet(db, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    transactions = transaction_service.get_wallet_transactions(db, wallet_id)
    total_income = sum(item.amount for item in transactions if item.type == "income")
    total_expense = sum(item.amount for item in transactions if item.type == "expense")
    return {
        "wallet_id": wallet_id,
        "balance": wallet.balance,
        "total_income": total_income,
        "total_expense": total_expense,
    }


@router.get("/wallets/{wallet_id}/expenses/category")
def get_category_expenses(wallet_id: int, db: Session = Depends(get_db)):
    wallet = wallet_service.get_wallet(db, wallet_id)
    if wallet is None:
        raise HTTPException(status_code=404, detail="Wallet not found")

    aggregated = {}
    for item in transaction_service.get_wallet_transactions(db, wallet_id):
        if item.type == "expense":
            category = item.category
            aggregated[category] = aggregated.get(category, 0) + item.amount
    return aggregated
