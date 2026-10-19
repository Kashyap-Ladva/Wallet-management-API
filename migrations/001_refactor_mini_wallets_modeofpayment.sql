-- Migration: 001_refactor_mini_wallets_modeofpayment.sql
-- Purpose:
-- 1. Remove modeofpayment from super-wallet (wallets table)
-- 2. Normalize modeofpayment in mini_wallets and transactions to UPPERCASE TRIM
-- 3. Resolve/create missing mini-wallets for distinct modes of payment
-- 4. Remap transactions to their payment-method-specific mini-wallets
-- 5. Deduplicate any duplicate mini-wallets per (super_wallet_id, modeofpayment)
-- 6. Add database-level unique constraint on mini_wallets(super_wallet_id, modeofpayment)

BEGIN;

-- Step 1: Normalize mini_wallets modeofpayment
UPDATE mini_wallets
SET modeofpayment = UPPER(TRIM(modeofpayment));

-- Step 2: Handle any duplicate mini-wallets for the same (super_wallet_id, modeofpayment)
WITH ranked_minis AS (
    SELECT id, super_wallet_id, modeofpayment,
           ROW_NUMBER() OVER (PARTITION BY super_wallet_id, modeofpayment ORDER BY id ASC) AS rn,
           FIRST_VALUE(id) OVER (PARTITION BY super_wallet_id, modeofpayment ORDER BY id ASC) AS primary_id
    FROM mini_wallets
),
duplicates AS (
    SELECT id, primary_id
    FROM ranked_minis
    WHERE rn > 1
)
-- Remap transactions pointing to duplicate mini-wallets
UPDATE transactions t
SET mini_wallet_id = d.primary_id
FROM duplicates d
WHERE t.mini_wallet_id = d.id;

-- Delete the duplicates
WITH ranked_minis AS (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY super_wallet_id, modeofpayment ORDER BY id ASC) AS rn
    FROM mini_wallets
)
DELETE FROM mini_wallets
WHERE id IN (SELECT id FROM ranked_minis WHERE rn > 1);

-- Step 3: Normalize modeofpayment on transactions
UPDATE transactions
SET modeofpayment = UPPER(TRIM(modeofpayment));

-- Step 4: Create mini-wallets for any transaction payment methods that don't have a mini-wallet yet
INSERT INTO mini_wallets (super_wallet_id, name, modeofpayment, date_created)
SELECT DISTINCT t.super_wallet_id, t.modeofpayment, t.modeofpayment, NOW()
FROM transactions t
LEFT JOIN mini_wallets m
    ON m.super_wallet_id = t.super_wallet_id AND m.modeofpayment = t.modeofpayment
WHERE m.id IS NULL;

-- Step 5: Remap all transactions to their matching payment-method mini-wallet
UPDATE transactions t
SET mini_wallet_id = m.id
FROM mini_wallets m
WHERE t.super_wallet_id = m.super_wallet_id
  AND t.modeofpayment = m.modeofpayment
  AND t.mini_wallet_id <> m.id;

-- Step 6: Add unique constraint on mini_wallets(super_wallet_id, modeofpayment)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_mini_wallets_super_wallet_modeofpayment'
    ) THEN
        ALTER TABLE mini_wallets
        ADD CONSTRAINT uq_mini_wallets_super_wallet_modeofpayment
        UNIQUE (super_wallet_id, modeofpayment);
    END IF;
END $$;

-- Step 7: Drop modeofpayment from wallets table if present
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'wallets' AND column_name = 'modeofpayment'
    ) THEN
        ALTER TABLE wallets DROP COLUMN modeofpayment;
    END IF;
END $$;

COMMIT;
