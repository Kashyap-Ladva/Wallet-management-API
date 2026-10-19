import logging
from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger("app.migrations")


def normalize_string(val: str | None) -> str:
    if not val or not str(val).strip():
        return "DEFAULT"
    return " ".join(str(val).strip().split()).upper()


def run_migrations(engine: Engine) -> None:
    dialect_name = engine.dialect.name
    logger.info("Running database migrations for dialect: %s", dialect_name)

    with engine.begin() as conn:
        # Check if tables exist
        if dialect_name == "postgresql":
            table_check = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name IN ('wallets', 'mini_wallets', 'transactions')"
                )
            ).fetchall()
            existing_tables = {row[0] for row in table_check}
        else:
            table_check = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name IN ('wallets', 'mini_wallets', 'transactions')"
                )
            ).fetchall()
            existing_tables = {row[0] for row in table_check}

        if "mini_wallets" not in existing_tables:
            logger.info("Tables not yet created, skipping data migration.")
            return

        # 1. Inspect all mini-wallets and normalize payment methods, deduplicating if needed
        mini_rows = conn.execute(
            text("SELECT id, super_wallet_id, name, modeofpayment FROM mini_wallets ORDER BY id ASC")
        ).fetchall()

        # Map (super_wallet_id, normalized_mode) -> primary mini_wallet_id
        super_mode_to_mini: dict[tuple[int, str], int] = {}
        remap_mini_ids: dict[int, int] = {}
        duplicates_to_delete: list[int] = []

        for m_id, sw_id, name, mode in mini_rows:
            norm_mode = normalize_string(mode)
            key = (sw_id, norm_mode)
            if key in super_mode_to_mini:
                primary_id = super_mode_to_mini[key]
                remap_mini_ids[m_id] = primary_id
                duplicates_to_delete.append(m_id)
            else:
                super_mode_to_mini[key] = m_id
                # Update normalized modeofpayment on primary mini-wallet
                conn.execute(
                    text("UPDATE mini_wallets SET modeofpayment = :mode WHERE id = :id"),
                    {"mode": norm_mode, "id": m_id},
                )

        # Remap transactions from duplicate mini-wallets
        for old_id, new_id in remap_mini_ids.items():
            conn.execute(
                text("UPDATE transactions SET mini_wallet_id = :new_id WHERE mini_wallet_id = :old_id"),
                {"new_id": new_id, "old_id": old_id},
            )

        # Delete duplicate mini-wallets
        for dup_id in duplicates_to_delete:
            conn.execute(
                text("DELETE FROM mini_wallets WHERE id = :id"),
                {"id": dup_id},
            )

        # 2. Inspect transactions and ensure each has a mini-wallet matching its normalized modeofpayment
        if "transactions" in existing_tables:
            tx_rows = conn.execute(
                text("SELECT id, super_wallet_id, mini_wallet_id, modeofpayment FROM transactions ORDER BY id ASC")
            ).fetchall()

            for tx_id, sw_id, m_id, tx_mode in tx_rows:
                norm_tx_mode = normalize_string(tx_mode)
                key = (sw_id, norm_tx_mode)

                if key not in super_mode_to_mini:
                    # Create missing mini-wallet for this payment method
                    if dialect_name == "postgresql":
                        new_mini_id = conn.execute(
                            text(
                                "INSERT INTO mini_wallets (super_wallet_id, name, modeofpayment, date_created) "
                                "VALUES (:sw_id, :name, :mode, NOW()) RETURNING id"
                            ),
                            {"sw_id": sw_id, "name": norm_tx_mode, "mode": norm_tx_mode},
                        ).scalar()
                    else:
                        conn.execute(
                            text(
                                "INSERT INTO mini_wallets (super_wallet_id, name, modeofpayment, date_created) "
                                "VALUES (:sw_id, :name, :mode, datetime('now'))"
                            ),
                            {"sw_id": sw_id, "name": norm_tx_mode, "mode": norm_tx_mode},
                        )
                        new_mini_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()

                    super_mode_to_mini[key] = new_mini_id

                target_mini_id = super_mode_to_mini[key]

                # Update transaction's modeofpayment and mini_wallet_id
                conn.execute(
                    text(
                        "UPDATE transactions SET mini_wallet_id = :mini_id, modeofpayment = :mode "
                        "WHERE id = :id"
                    ),
                    {"mini_id": target_mini_id, "mode": norm_tx_mode, "id": tx_id},
                )

        # 3. Add uniqueness constraint on mini_wallets (super_wallet_id, modeofpayment)
        if dialect_name == "postgresql":
            constraint_check = conn.execute(
                text(
                    "SELECT constraint_name FROM information_schema.table_constraints "
                    "WHERE table_name='mini_wallets' AND constraint_name='uq_mini_wallets_super_wallet_modeofpayment'"
                )
            ).fetchone()
            if not constraint_check:
                conn.execute(
                    text(
                        "ALTER TABLE mini_wallets ADD CONSTRAINT uq_mini_wallets_super_wallet_modeofpayment "
                        "UNIQUE (super_wallet_id, modeofpayment)"
                    )
                )
        else:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_mini_wallets_super_wallet_modeofpayment "
                    "ON mini_wallets (super_wallet_id, modeofpayment)"
                )
            )

        # 4. Remove modeofpayment from wallets table if present
        if "wallets" in existing_tables:
            if dialect_name == "postgresql":
                col_check = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name='wallets' AND column_name='modeofpayment'"
                    )
                ).fetchone()
                if col_check:
                    conn.execute(text("ALTER TABLE wallets DROP COLUMN modeofpayment"))
            else:
                table_info = conn.execute(text("PRAGMA table_info(wallets)")).fetchall()
                col_names = [row[1] for row in table_info]
                if "modeofpayment" in col_names:
                    try:
                        conn.execute(text("ALTER TABLE wallets DROP COLUMN modeofpayment"))
                    except Exception as exc:
                        logger.warning("Could not drop column modeofpayment in SQLite: %s", exc)

    logger.info("Migrations completed successfully.")


if __name__ == "__main__":
    from app.database import engine

    run_migrations(engine)
