import json
from pathlib import Path

FILE_PATH = Path(__file__).resolve().parent.parent / "data" / "transactions.json"


def ensure_file():
    if not FILE_PATH.exists():
        FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with FILE_PATH.open("w", encoding="utf-8") as file:
            json.dump([], file)


def read_transactions():
    ensure_file()
    with FILE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_transactions(transactions):
    with FILE_PATH.open("w", encoding="utf-8") as file:
        json.dump(transactions, file, indent=4)


def create_transaction(wallet_id: int, amount: float, transaction_type: str, category: str, description: str | None):
    transactions = read_transactions()
    transaction = {
        "id": max((item["id"] for item in transactions), default=0) + 1,
        "wallet_id": wallet_id,
        "amount": amount,
        "type": transaction_type,
        "category": category,
        "description": description,
    }
    transactions.append(transaction)
    save_transactions(transactions)
    return transaction


def get_wallet_transactions(wallet_id: int):
    return [transaction for transaction in read_transactions() if transaction["wallet_id"] == wallet_id]


def get_transaction(transaction_id: int):
    return next(
        (transaction for transaction in read_transactions() if transaction["id"] == transaction_id),
        None,
    )


def update_transaction(transaction_id: int, updates: dict):
    transactions = read_transactions()
    transaction = next(
        (transaction for transaction in transactions if transaction["id"] == transaction_id),
        None,
    )
    if transaction is None:
        return None

    transaction.update(updates)
    save_transactions(transactions)
    return transaction


def delete_transaction(transaction_id: int):
    transactions = read_transactions()
    transaction = next(
        (transaction for transaction in transactions if transaction["id"] == transaction_id),
        None,
    )
    if transaction is None:
        return False

    transactions.remove(transaction)
    save_transactions(transactions)
    return True
