import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

os.environ["DATABASE_URL"] = "sqlite:///./test_wallet_refactor.db"

from openpyxl import Workbook
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def reset_db():
    from app.database import engine, init_db
    from app.models import Base

    Base.metadata.drop_all(bind=engine)
    init_db()


def create_user(email: str = "testuser@example.com", name: str = "Test User") -> str:
    res = client.post(
        "/auth/register",
        json={
            "name": name,
            "phone": str(3000000000 + abs(hash(email)) % 1000000000),
            "email": email,
            "currency": "INR",
            "password": "Password123!",
        },
    )
    assert res.status_code == 201, res.text
    login = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_super_wallet(token: str, name: str = "Primary Wallet") -> int:
    res = client.post(
        "/super-wallet",
        headers=auth(token),
        json={"name": name, "currency": "INR"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def make_workbook(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            "amount",
            "type",
            "category",
            "date_created",
            "modeofpayment",
            "description",
            "proof",
        ]
    )
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def upload_file(content: bytes) -> dict:
    return {
        "file": (
            "transactions.xlsx",
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }


# 1. Creating a CASH transaction automatically creates the CASH mini-wallet if needed.
def test_1_cash_transaction_creates_cash_mini_wallet():
    reset_db()
    token = create_user("u1@example.com")
    create_super_wallet(token)

    # Verify no mini-wallets initially exist
    minis_before = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    assert len(minis_before) == 0

    res = client.post(
        "/super-wallet/transactions",
        headers=auth(token),
        json={
            "amount": "1500.00",
            "type": "income",
            "category": "Salary",
            "modeofpayment": "CASH",
            "description": "First Cash Income",
        },
    )
    assert res.status_code == 201, res.text
    tx = res.json()
    assert tx["modeofpayment"] == "CASH"

    minis_after = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    assert len(minis_after) == 1
    assert minis_after[0]["modeofpayment"] == "CASH"
    assert minis_after[0]["name"] == "CASH"
    assert tx["mini_wallet_id"] == minis_after[0]["id"]
    assert minis_after[0]["balance"] == "1500.00"


# 2. A second CASH transaction reuses the existing mini-wallet.
def test_2_second_cash_transaction_reuses_existing_mini_wallet():
    reset_db()
    token = create_user("u2@example.com")
    create_super_wallet(token)

    # First transaction
    res1 = client.post(
        "/transactions",
        headers=auth(token),
        json={
            "amount": "2000.00",
            "type": "income",
            "category": "Salary",
            "modeofpayment": "CASH",
        },
    )
    assert res1.status_code == 201
    mini_id_1 = res1.json()["mini_wallet_id"]

    # Second transaction
    res2 = client.post(
        "/transactions",
        headers=auth(token),
        json={
            "amount": "500.00",
            "type": "expense",
            "category": "Food",
            "modeofpayment": "CASH",
        },
    )
    assert res2.status_code == 201
    mini_id_2 = res2.json()["mini_wallet_id"]

    assert mini_id_1 == mini_id_2
    minis = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    assert len(minis) == 1
    assert minis[0]["balance"] == "1500.00"


# 3. cash, CASH, and ' CASH ' do not create duplicate mini-wallets.
def test_3_normalization_prevents_duplicate_mini_wallets():
    reset_db()
    token = create_user("u3@example.com")
    create_super_wallet(token)

    modes = ["cash", "CASH", "  CASH  ", " Cash "]
    mini_ids = []
    for mode in modes:
        res = client.post(
            "/transactions",
            headers=auth(token),
            json={
                "amount": "100.00",
                "type": "income",
                "category": "Misc",
                "modeofpayment": mode,
            },
        )
        assert res.status_code == 201, res.text
        mini_ids.append(res.json()["mini_wallet_id"])

    # All must have resolved to the exact same mini-wallet ID
    assert len(set(mini_ids)) == 1
    minis = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    assert len(minis) == 1
    assert minis[0]["modeofpayment"] == "CASH"
    assert minis[0]["balance"] == "400.00"


# 4. UPI and CARD transactions create separate mini-wallets.
def test_4_upi_and_card_create_separate_mini_wallets():
    reset_db()
    token = create_user("u4@example.com")
    create_super_wallet(token)

    res_upi = client.post(
        "/transactions",
        headers=auth(token),
        json={
            "amount": "500.00",
            "type": "income",
            "category": "Gift",
            "modeofpayment": "UPI",
        },
    )
    assert res_upi.status_code == 201
    upi_mini_id = res_upi.json()["mini_wallet_id"]

    res_card = client.post(
        "/transactions",
        headers=auth(token),
        json={
            "amount": "1000.00",
            "type": "income",
            "category": "Bonus",
            "modeofpayment": "CARD",
        },
    )
    assert res_card.status_code == 201
    card_mini_id = res_card.json()["mini_wallet_id"]

    assert upi_mini_id != card_mini_id

    minis = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    assert len(minis) == 2
    modes = {m["modeofpayment"]: m["balance"] for m in minis}
    assert modes["UPI"] == "500.00"
    assert modes["CARD"] == "1000.00"


# 5. The same payment method under a different super-wallet creates a separate mini-wallet.
def test_5_separate_mini_wallets_across_different_super_wallets():
    reset_db()
    token_a = create_user("alice5@example.com", "Alice")
    token_b = create_user("bob5@example.com", "Bob")

    sw_a = create_super_wallet(token_a, "Alice Super")
    sw_b = create_super_wallet(token_b, "Bob Super")

    res_a = client.post(
        "/transactions",
        headers=auth(token_a),
        json={"amount": "100.00", "type": "income", "category": "General", "modeofpayment": "UPI"},
    )
    res_b = client.post(
        "/transactions",
        headers=auth(token_b),
        json={"amount": "200.00", "type": "income", "category": "General", "modeofpayment": "UPI"},
    )

    mini_a = res_a.json()["mini_wallet_id"]
    mini_b = res_b.json()["mini_wallet_id"]

    assert mini_a != mini_b
    assert res_a.json()["super_wallet_id"] == sw_a
    assert res_b.json()["super_wallet_id"] == sw_b

    # Alice cannot access Bob's mini-wallet
    bob_check = client.get(f"/mini-wallets/{mini_b}", headers=auth(token_a))
    assert bob_check.status_code == 403


# 6. Excel rows with different payment methods receive the correct mini-wallet IDs.
def test_6_excel_rows_with_different_payment_methods():
    reset_db()
    token = create_user("u6@example.com")
    create_super_wallet(token)

    content = make_workbook(
        [
            [1000, "income", "salary", date(2026, 10, 1), "cash", "Cash salary", None],
            [2000, "income", "bonus", date(2026, 10, 2), "upi", "UPI bonus", None],
            [3000, "income", "dividends", date(2026, 10, 3), "card", "Card div", None],
            [400, "expense", "groceries", date(2026, 10, 4), "cash", "Cash food", None],
        ]
    )

    preview = client.post(
        "/imports/excel/preview",
        headers=auth(token),
        files=upload_file(content),
    )
    assert preview.status_code == 200, preview.text
    pjson = preview.json()
    assert pjson["valid"] is True
    assert len(pjson["rows"]) == 4

    # Preview displays mini_wallet_name for each row
    assert pjson["rows"][0]["mini_wallet_name"] == "CASH"
    assert pjson["rows"][1]["mini_wallet_name"] == "UPI"
    assert pjson["rows"][2]["mini_wallet_name"] == "CARD"
    assert pjson["rows"][3]["mini_wallet_name"] == "CASH"

    confirm = client.post(
        "/imports/excel/confirm",
        headers=auth(token),
        data={"preview_sha256": pjson["file_sha256"]},
        files=upload_file(content),
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["imported_count"] == 4

    minis = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    assert len(minis) == 3
    balances = {m["modeofpayment"]: m["balance"] for m in minis}
    assert balances["CASH"] == "600.00"   # 1000 - 400
    assert balances["UPI"] == "2000.00"
    assert balances["CARD"] == "3000.00"


# 7. Repeated Excel imports do not create duplicate mini-wallets.
def test_7_repeated_excel_imports_do_not_create_duplicate_mini_wallets():
    reset_db()
    token = create_user("u7@example.com")
    create_super_wallet(token)

    content = make_workbook(
        [
            [1000, "income", "salary", date(2026, 10, 1), "cash", "First Batch", None],
            [500, "income", "freelance", date(2026, 10, 2), "upi", "First Batch", None],
        ]
    )

    prev1 = client.post("/imports/excel/preview", headers=auth(token), files=upload_file(content)).json()
    client.post(
        "/imports/excel/confirm",
        headers=auth(token),
        data={"preview_sha256": prev1["file_sha256"]},
        files=upload_file(content),
    )

    minis_run1 = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    assert len(minis_run1) == 2

    # Second import of another batch with the same payment methods
    content2 = make_workbook(
        [
            [200, "income", "cashback", date(2026, 10, 3), "CASH", "Second Batch", None],
            [300, "income", "interest", date(2026, 10, 4), "upi", "Second Batch", None],
        ]
    )
    prev2 = client.post("/imports/excel/preview", headers=auth(token), files=upload_file(content2)).json()
    client.post(
        "/imports/excel/confirm",
        headers=auth(token),
        data={"preview_sha256": prev2["file_sha256"]},
        files=upload_file(content2),
    )

    minis_run2 = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    assert len(minis_run2) == 2
    balances = {m["modeofpayment"]: m["balance"] for m in minis_run2}
    assert balances["CASH"] == "1200.00"
    assert balances["UPI"] == "800.00"


# 8. Missing or invalid payment methods produce clear validation errors.
def test_8_missing_or_invalid_payment_methods_produce_errors():
    reset_db()
    token = create_user("u8@example.com")
    create_super_wallet(token)

    # Missing modeofpayment
    res_missing = client.post(
        "/transactions",
        headers=auth(token),
        json={"amount": "100.00", "type": "income", "category": "General"},
    )
    assert res_missing.status_code == 422

    # Empty string modeofpayment
    res_empty = client.post(
        "/transactions",
        headers=auth(token),
        json={"amount": "100.00", "type": "income", "category": "General", "modeofpayment": "   "},
    )
    assert res_empty.status_code == 422

    # Excel file with missing modeofpayment in row
    bad_excel = make_workbook(
        [
            [100, "income", "food", date(2026, 10, 1), "", "Missing mode", None],
        ]
    )
    prev = client.post("/imports/excel/preview", headers=auth(token), files=upload_file(bad_excel))
    assert prev.status_code == 200
    assert prev.json()["valid"] is False
    assert any("modeofpayment is required" in err for err in prev.json()["errors"][0]["errors"])


# 9. A user cannot create transactions against another user's super-wallet or mini-wallet.
def test_9_cross_user_isolation():
    reset_db()
    token_a = create_user("alice9@example.com")
    token_b = create_user("bob9@example.com")

    sw_a = create_super_wallet(token_a)
    create_super_wallet(token_b)

    # Alice creates a mini-wallet
    mini_a = client.post(
        "/super-wallet/mini-wallets",
        headers=auth(token_a),
        json={"name": "Alice Cash", "modeofpayment": "cash"},
    ).json()["id"]

    # Bob attempts to post transaction directly into Alice's mini-wallet -> 403
    bob_tx = client.post(
        f"/mini-wallets/{mini_a}/transactions",
        headers=auth(token_b),
        json={"amount": "500.00", "type": "income", "category": "Hack", "modeofpayment": "cash"},
    )
    assert bob_tx.status_code == 403

    # Bob attempts to import Excel into Alice's mini-wallet -> 403
    content = make_workbook([[100, "income", "test", date(2026, 10, 1), "cash", "Hack", None]])
    bob_prev = client.post(
        "/imports/excel/preview",
        headers=auth(token_b),
        data={"mini_wallet_id": str(mini_a)},
        files=upload_file(content),
    )
    assert bob_prev.status_code == 403

    # Bob attempts to import Excel into Alice's super-wallet -> 403
    bob_prev_sw = client.post(
        "/imports/excel/preview",
        headers=auth(token_b),
        data={"super_wallet_id": str(sw_a)},
        files=upload_file(content),
    )
    assert bob_prev_sw.status_code == 403


# 10. Failed Excel confirmation leaves no partial transactions or orphaned mini-wallets.
def test_10_failed_excel_leaves_no_orphaned_mini_wallets_or_partial_transactions():
    reset_db()
    token = create_user("u10@example.com")
    create_super_wallet(token)

    # File with row 1 creating METRO CARD, but row 2 overspending METRO CARD
    content = make_workbook(
        [
            [500, "income", "transit", date(2026, 10, 1), "metro card", "Fund transit", None],
            [1500, "expense", "transit", date(2026, 10, 2), "metro card", "Overspend", None],
        ]
    )

    prev = client.post("/imports/excel/preview", headers=auth(token), files=upload_file(content)).json()
    assert prev["valid"] is False

    # Force call confirm anyway
    confirm = client.post(
        "/imports/excel/confirm",
        headers=auth(token),
        data={"preview_sha256": prev["file_sha256"]},
        files=upload_file(content),
    )
    assert confirm.status_code == 422

    # Verify no mini-wallet was left behind
    minis = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    assert len(minis) == 0

    # Verify no transactions were created
    txs = client.get("/super-wallet/transactions", headers=auth(token)).json()
    assert len(txs) == 0


# 11. Concurrent requests cannot create duplicate mini-wallets for the same super-wallet and payment method.
def test_11_concurrent_requests_prevent_duplicate_mini_wallets():
    reset_db()
    token = create_user("u11@example.com")
    create_super_wallet(token)

    def send_tx(amount: int):
        return client.post(
            "/transactions",
            headers=auth(token),
            json={
                "amount": f"{amount}.00",
                "type": "income",
                "category": "Salary",
                "modeofpayment": "UPI",
            },
        )

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(send_tx, 100 + i) for i in range(10)]
        results = [f.result() for f in futures]

    for r in results:
        assert r.status_code == 201, r.text

    minis = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    assert len(minis) == 1
    assert minis[0]["modeofpayment"] == "UPI"
    assert minis[0]["balance"] == "1045.00"


# 12. Existing transaction update, delete, balance, and financial-integrity tests continue to pass.
def test_12_transaction_update_delete_and_balance_integrity():
    reset_db()
    token = create_user("u12@example.com")
    create_super_wallet(token)

    # 1. Add CASH income 1000
    tx1 = client.post(
        "/transactions",
        headers=auth(token),
        json={"amount": "1000.00", "type": "income", "category": "Gift", "modeofpayment": "CASH"},
    ).json()

    # 2. Add BANK income 2000
    tx2 = client.post(
        "/transactions",
        headers=auth(token),
        json={"amount": "2000.00", "type": "income", "category": "Salary", "modeofpayment": "BANK"},
    ).json()

    # 3. Add BANK expense 500
    tx3 = client.post(
        "/transactions",
        headers=auth(token),
        json={"amount": "500.00", "type": "expense", "category": "Rent", "modeofpayment": "BANK"},
    ).json()

    # Check super-wallet balance = 1000 + 2000 - 500 = 2500
    sw_bal = client.get("/super-wallet/balance", headers=auth(token)).json()["balance"]
    assert sw_bal == "2500.00"

    # 4. Update tx3 modeofpayment from BANK to CASH (expense 500 moves to CASH)
    # CASH balance was 1000, now becomes 1000 - 500 = 500. BANK balance was 1500, now becomes 2000.
    upd = client.put(
        f"/transactions/{tx3['id']}",
        headers=auth(token),
        json={"modeofpayment": "CASH"},
    )
    assert upd.status_code == 200, upd.text

    minis = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    balances = {m["modeofpayment"]: m["balance"] for m in minis}
    assert balances["CASH"] == "500.00"
    assert balances["BANK"] == "2000.00"

    # 5. Overspending check: try to update expense to 1100 in CASH (available is 1000 total income) -> 400
    over_upd = client.put(
        f"/transactions/{tx3['id']}",
        headers=auth(token),
        json={"amount": "1100.00"},
    )
    assert over_upd.status_code == 400

    # 6. Delete expense tx3 -> CASH balance restored to 1000.00
    del_res = client.delete(f"/transactions/{tx3['id']}", headers=auth(token))
    assert del_res.status_code == 204

    minis_after_del = client.get("/super-wallet/mini-wallets", headers=auth(token)).json()
    balances_after = {m["modeofpayment"]: m["balance"] for m in minis_after_del}
    assert balances_after["CASH"] == "1000.00"
    assert balances_after["BANK"] == "2000.00"


# 13. Super-wallet creation and update work without a payment-method field.
def test_13_super_wallet_crud_without_payment_method():
    reset_db()
    token = create_user("u13@example.com")

    # Creating super-wallet works without modeofpayment
    res = client.post(
        "/super-wallet",
        headers=auth(token),
        json={"name": "My Wallet", "currency": "USD"},
    )
    assert res.status_code == 201
    assert "modeofpayment" not in res.json()
    sw_id = res.json()["id"]

    # Updating super-wallet works
    upd = client.put(
        "/super-wallet",
        headers=auth(token),
        json={"name": "My Updated Wallet"},
    )
    assert upd.status_code == 200
    assert "modeofpayment" not in upd.json()
    assert upd.json()["name"] == "My Updated Wallet"

    # Creating with modeofpayment should be rejected (extra fields forbidden)
    rej_create = client.post(
        "/super-wallet",
        headers=auth(token),
        json={"name": "Second", "currency": "USD", "modeofpayment": "wallet"},
    )
    assert rej_create.status_code == 422

    # Updating with modeofpayment should be rejected
    rej_upd = client.put(
        "/super-wallet",
        headers=auth(token),
        json={"modeofpayment": "wallet"},
    )
    assert rej_upd.status_code == 422


# 14. Existing database records remain accessible after the migration.
def test_14_existing_database_records_accessible_after_migration():
    from app.database import engine
    from app.migrations.migrate import run_migrations
    from sqlalchemy import text

    # Pre-populate SQLite with old-style schema
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS transactions"))
        conn.execute(text("DROP TABLE IF EXISTS mini_wallets"))
        conn.execute(text("DROP TABLE IF EXISTS wallets"))
        conn.execute(text("DROP TABLE IF EXISTS users"))

        conn.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, name VARCHAR, phone VARCHAR, "
                "email VARCHAR UNIQUE, currency VARCHAR, password_hash VARCHAR, date_created TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE wallets (id INTEGER PRIMARY KEY, user_id INTEGER, name VARCHAR, "
                "currency VARCHAR, modeofpayment VARCHAR, date_created TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE mini_wallets (id INTEGER PRIMARY KEY, super_wallet_id INTEGER, "
                "name VARCHAR, modeofpayment VARCHAR, date_created TIMESTAMP)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE transactions (id INTEGER PRIMARY KEY, mini_wallet_id INTEGER, "
                "super_wallet_id INTEGER, amount NUMERIC, type VARCHAR, category VARCHAR, "
                "description VARCHAR, modeofpayment VARCHAR, proof VARCHAR, date_created TIMESTAMP)"
            )
        )

        conn.execute(
            text(
                "INSERT INTO users VALUES (1, 'Legacy User', '1234567890', 'legacy@example.com', 'INR', 'hash', '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO wallets VALUES (1, 1, 'Legacy Super Wallet', 'INR', 'wallet', '2026-01-01')"
            )
        )
        # Legacy mini-wallets: one un-normalized 'cash ', and transactions dumped into it with 'UPI'
        conn.execute(
            text(
                "INSERT INTO mini_wallets VALUES (1, 1, 'Cash', 'cash ', '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO transactions VALUES (1, 1, 1, 5000.00, 'income', 'Salary', 'Pay', 'cash', NULL, '2026-01-01')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO transactions VALUES (2, 1, 1, 1500.00, 'income', 'Freelance', 'Work', 'upi', NULL, '2026-01-02')"
            )
        )

    # Run migration
    run_migrations(engine)

    # Verify via SQL
    with engine.begin() as conn:
        # wallets table should not have modeofpayment if supported
        minis = conn.execute(text("SELECT id, name, modeofpayment FROM mini_wallets ORDER BY id")).fetchall()
        # Should now have 2 mini-wallets: CASH and UPI
        assert len(minis) == 2
        assert minis[0][2] == "CASH"
        assert minis[1][2] == "UPI"

        # Transactions should be remapped
        txs = conn.execute(text("SELECT id, mini_wallet_id, modeofpayment FROM transactions ORDER BY id")).fetchall()
        assert txs[0][1] == minis[0][0]  # cash tx points to cash mini
        assert txs[0][2] == "CASH"
        assert txs[1][1] == minis[1][0]  # upi tx points to upi mini
        assert txs[1][2] == "UPI"
