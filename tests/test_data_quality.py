"""Data quality: every row in trades_clean obeys the rules in docs/mapping.md.

Each check is a SQL query that returns the rows BREAKING a rule.
An empty result means the rule holds.
"""
import pytest

QUALITY_RULES = {
    "trade_id is unique": """
        SELECT trade_id, COUNT(*) FROM trades_clean
        GROUP BY trade_id HAVING COUNT(*) > 1""",
    "no empty required values": """
        SELECT trade_id FROM trades_clean
        WHERE COALESCE(trade_id, '') = '' OR COALESCE(account_id, '') = ''
           OR COALESCE(ticker, '') = ''   OR COALESCE(side, '') = ''
           OR COALESCE(currency, '') = '' OR COALESCE(trade_date, '') = ''""",
    "side is BUY or SELL": """
        SELECT trade_id, side FROM trades_clean
        WHERE side NOT IN ('BUY', 'SELL')""",
    "quantity is positive": """
        SELECT trade_id, quantity FROM trades_clean WHERE quantity <= 0""",
    "price is positive": """
        SELECT trade_id, price FROM trades_clean WHERE price <= 0""",
    "trade_date is a real YYYY-MM-DD date": """
        SELECT trade_id, trade_date FROM trades_clean
        WHERE date(trade_date) IS NULL OR date(trade_date) <> trade_date""",
    "codes are trimmed and upper-case": """
        SELECT trade_id FROM trades_clean
        WHERE trade_id   <> UPPER(TRIM(trade_id))
           OR account_id <> UPPER(TRIM(account_id))
           OR ticker     <> UPPER(TRIM(ticker))
           OR currency   <> UPPER(TRIM(currency))""",
    "every account exists (referential integrity)": """
        SELECT t.trade_id, t.account_id
        FROM trades_clean t
        LEFT JOIN dim_accounts a ON a.account_id = t.account_id
        WHERE a.account_id IS NULL""",
    "every currency has an FX rate": """
        SELECT t.trade_id, t.currency
        FROM trades_clean t
        LEFT JOIN dim_fx_rates f ON f.currency = t.currency
        WHERE f.currency IS NULL""",
    "every rejected row has a known reason": """
        SELECT source_row, reject_reason FROM trades_rejected
        WHERE reject_reason NOT IN (
            'DUPLICATE_TRADE_ID', 'MISSING_TICKER', 'INVALID_SIDE',
            'INVALID_QUANTITY', 'INVALID_PRICE', 'INVALID_DATE',
            'UNKNOWN_CURRENCY', 'UNKNOWN_ACCOUNT')""",
}


@pytest.mark.parametrize("rule", QUALITY_RULES)
def test_quality_rule(query, rule):
    violations = query(QUALITY_RULES[rule])
    assert violations == [], f"'{rule}' broken by: {violations}"