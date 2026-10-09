-- 1. How many rows arrived, and how many ended up where?
SELECT 'staged'   AS layer, COUNT(*) AS row_count FROM stg_trades
UNION ALL SELECT 'clean',    COUNT(*) FROM trades_clean
UNION ALL SELECT 'rejected', COUNT(*) FROM trades_rejected;
-- Finding: staged 14 = clean 8 + rejected 6 -> no rows lost. PASS

-- 2. Duplicate trade_id in the source (window function)
SELECT source_row, trade_id, occurrence
FROM (
    SELECT source_row,
           UPPER(TRIM(trade_id)) AS trade_id,
           ROW_NUMBER() OVER (PARTITION BY UPPER(TRIM(trade_id)) ORDER BY source_row) AS occurrence
    FROM stg_trades
)
WHERE occurrence > 1;

-- Both copies of T007 in the source
SELECT * FROM stg_trades WHERE UPPER(TRIM(trade_id)) = 'T007';

-- Did the pipeline reject the duplicate?
SELECT * FROM trades_rejected WHERE source_row = 8;

-- Finding: 1 duplicate in source - T007 appears twice, 2nd copy at source_row 8.
-- Row 8 is in trades_rejected (duplicate) and T007 appears once in trades_clean. PASS

-- 3. Empty values per column in the source
SELECT SUM(TRIM(ticker) = '')     AS empty_ticker,
       SUM(TRIM(account_id) = '') AS empty_account,
       SUM(TRIM(currency) = '')   AS empty_currency
FROM stg_trades;

-- Which row has the empty ticker?
SELECT source_row, trade_id, ticker FROM stg_trades WHERE TRIM(ticker) = '';

-- Was it rejected?
SELECT * FROM trades_rejected WHERE source_row = 12;

-- NULLs are not caught by TRIM(x) = ''
SELECT SUM(ticker IS NULL)     AS null_ticker,
       SUM(account_id IS NULL) AS null_account,
       SUM(currency IS NULL)   AS null_currency
FROM stg_trades;

-- Finding: There is 1 empty ticker (source_row 12, trade T011) and no empty accounts/currency fields.
-- No NULLs in ticker/account_id/currency.
-- Row 12 is in trades_rejected (missing ticker) and not in trades_clean. PASS

-- 4. Dates that are not valid YYYY-MM-DD
SELECT source_row, trade_date
FROM stg_trades
WHERE date(TRIM(trade_date)) IS NULL
   OR date(TRIM(trade_date)) <> TRIM(trade_date);

--What is the trade?
SELECT * FROM stg_trades WHERE source_row = 13;

--Was it rejected?
SELECT * FROM trades_rejected WHERE source_row = 13;

--Make sure it is not in clean
SELECT * FROM trades_clean WHERE source_row = 13;

--Finding: 1 Trade (T012, source_row 13) has invalid date format '2026/09/07' (slashes instead of YYYY-MM-DD).
-- It is correctly put in trades_rejected and no impossible dates (e.g. YYYY-33-33)
-- Not in trades_clean. PASS

-- 5. Accounts that do not exist (orphans)
SELECT s.source_row, s.account_id
FROM stg_trades s
LEFT JOIN dim_accounts a ON a.account_id = UPPER(TRIM(s.account_id))
WHERE a.account_id IS NULL;

--What is the trade?
SELECT * FROM stg_trades WHERE source_row = 9;

--Was it rejected?
SELECT * FROM trades_rejected WHERE source_row = 9;

--Make sure it is not in clean
SELECT * FROM trades_clean WHERE source_row = 9;

-- Is dim_accounts itself clean?
SELECT account_id FROM dim_accounts
WHERE account_id <> UPPER(TRIM(account_id));

-- Finding: 1 orphan trade (T008, source_row 9) - account_id 'A004' does not exist in dim_accounts.
-- It is correctly put in trades_rejected and not in trades_clean. 
-- dim_accounts keys are clean (no case/whitespace issues). PASS

-- 6. Currencies without an FX rate
SELECT DISTINCT UPPER(TRIM(currency)) AS currency
FROM stg_trades
WHERE UPPER(TRIM(currency)) NOT IN (SELECT currency FROM dim_fx_rates);


--What is the trade?
SELECT * FROM stg_trades WHERE currency = 'CHF';

--Was it rejected?
SELECT * FROM trades_rejected WHERE source_row = 11;

--Make sure it is not in clean
SELECT * FROM trades_clean WHERE source_row = 11;

-- NOT IN returns nothing if dim_fx_rates has a NULL currency
SELECT COUNT(*) FROM dim_fx_rates WHERE currency IS NULL;

-- Finding: 1 trade (T010, source_row 11) has currency 'CHF', which has no rate in dim_fx_rates.
-- It is correctly put in trades_rejected and not in trades_clean.
-- dim_fx_rates has no NULL currencies, so the NOT IN result is reliable. PASS

-- 7. Rows with whitespace or lower case that the ETL must clean
SELECT source_row, trade_id, account_id, ticker, side, currency
FROM stg_trades
WHERE trade_id <> UPPER(TRIM(trade_id)) OR ticker <> UPPER(TRIM(ticker));

-- Was it rejected?
SELECT * FROM trades_rejected WHERE source_row = 14;

-- Make sure it is not in clean
SELECT * FROM trades_clean WHERE source_row = 14;

-- Check for NULL trade_id 
SELECT COUNT(*) FROM stg_trades WHERE trade_id IS NULL;

-- Confirm the values in trades_clean are really normalized
SELECT source_row, trade_id, ticker FROM trades_clean
WHERE source_row = 14
  AND trade_id = UPPER(TRIM(trade_id))
  AND ticker   = UPPER(TRIM(ticker));

-- Finding: 1 trade (T013, source_row 14) has whitespace/lower case in raw data ('...').
-- ETL normalized it (T013, MSFT) and loaded it into trades_clean; not in trades_rejected. PASS
-- No NULL trade_ids; ticker NULLs already covered in step 3.

-- 8. Why were rows rejected?
SELECT reject_reason, COUNT(*) AS rows_rejected
FROM trades_rejected
GROUP BY reject_reason
ORDER BY rows_rejected DESC;

-- No row may be in both tables
SELECT c.source_row
FROM trades_clean c
JOIN trades_rejected r ON r.source_row = c.source_row;

-- Every staged row must land somewhere
SELECT s.source_row
FROM stg_trades s
LEFT JOIN trades_clean    c ON c.source_row = s.source_row
LEFT JOIN trades_rejected r ON r.source_row = s.source_row
WHERE c.source_row IS NULL AND r.source_row IS NULL;

-- Results comparison
SELECT source_row, reject_reason FROM trades_rejected ORDER BY source_row;

-- Reject that was not covered manually
SELECT r.source_row, r.raw_record, s.quantity
FROM trades_rejected r
JOIN stg_trades s ON s.source_row = r.source_row
WHERE r.reject_reason = 'INVALID_QUANTITY';

-- Findings summary: 6 rejections, 1 per reason; each matches the rows found in steps 2-6.
-- No overlap between trades_clean and trades_rejected; no staged row lost. PASS
-- NOTE: INVALID_QUANTITY (source_row N, quantity '...') was not covered by queries 2-7 -> add a test later.

-- 9. Invalid quantity (not covered by queries 2-7)
SELECT source_row, trade_id, quantity
FROM stg_trades
WHERE quantity IS NULL
   OR TRIM(quantity) = ''
   OR TRIM(quantity) GLOB '*[^0-9.]*'          -- anything but digits/dot (minus, letters...)
   OR CAST(TRIM(quantity) AS REAL) <= 0;       -- zero (and negatives as a safety net)

-- Finding: 1 trade (T009, source_row 10) has invalid quantity -20.
-- No NULL/empty/zero/non-numeric quantities. Correctly in trades_rejected, not in trades_clean. PASS