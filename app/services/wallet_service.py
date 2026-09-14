import json
from pathlib import Path

FILE_PATH = Path(__file__).resolve().parent.parent / "data" / "wallets.json"


def ensure_file():
    if not FILE_PATH.exists():
        FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with FILE_PATH.open("w", encoding="utf-8") as file:
            json.dump([], file)


def read_wallets():
    ensure_file()
    with FILE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_wallets(wallets):
    with FILE_PATH.open("w", encoding="utf-8") as file:
        json.dump(wallets, file, indent=4)


def create_wallet(name: str, currency: str):
    wallets = read_wallets()
    wallet = {
        "id": max((item["id"] for item in wallets), default=0) + 1,
        "name": name,
        "currency": currency,
        "balance": 0,
    }
    wallets.append(wallet)
    save_wallets(wallets)
    return wallet


def get_wallets():
    return read_wallets()


def get_wallet(wallet_id: int):
    return next(
        (wallet for wallet in read_wallets() if wallet["id"] == wallet_id),
        None,
    )


def update_wallet(wallet_id: int, updates: dict):
    wallets = read_wallets()
    wallet = next(
        (wallet for wallet in wallets if wallet["id"] == wallet_id),
        None,
    )
    if wallet is None:
        return None

    wallet.update(updates)
    save_wallets(wallets)
    return wallet


def delete_wallet(wallet_id: int):
    wallets = read_wallets()
    wallet = next(
        (wallet for wallet in wallets if wallet["id"] == wallet_id),
        None,
    )
    if wallet is None:
        return False

    wallets.remove(wallet)
    save_wallets(wallets)
    return True
