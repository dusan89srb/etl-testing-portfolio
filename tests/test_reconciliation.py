"""Source-to-target reconciliation: target values equal the transformed source."""
import pytest


def test_column_mapping_matches_source(query):
    """Every loaded row equals its staged source row after the mapping rules."""
    mismatches = query("""
        SELECT c.source_row
        FROM trades_clean c
        JOIN stg_trades s ON s.source_row = c.source_row
        WHERE c.trade_id   <> UPPER(TRIM(s.trade_id))
           OR c.account_id <> UPPER(TRIM(s.account_id))
           OR c.ticker     <> UPPER(TRIM(s.ticker))
           OR c.side       <> UPPER(TRIM(s.side))
           OR c.currency   <> UPPER(TRIM(s.currency))
           OR c.trade_date <> TRIM(s.trade_date)
           OR c.quantity   <> CAST(TRIM(s.quantity) AS INTEGER)
           OR ABS(c.price - CAST(TRIM(s.price) AS REAL)) > 1e-9
    """)
    assert mismatches == [], f"rows that do not match their source: {mismatches}"


def test_notional_usd_uses_the_fx_rate(query):
    wrong = query("""
        SELECT c.trade_id, c.notional_usd,
               ROUND(c.quantity * c.price * f.rate_to_usd, 2) AS expected
        FROM trades_clean c
        JOIN dim_fx_rates f ON f.currency = c.currency
        WHERE ABS(c.notional_usd - ROUND(c.quantity * c.price * f.rate_to_usd, 2)) > 0.005
    """)
    assert wrong == [], f"wrong USD notional: {wrong}"


def test_control_total_of_quantity(scalar, query, source_trades):
    """Sum of quantity loaded = sum of quantity of the same rows in the source file."""
    loaded_rows = {row for (row,) in query("SELECT source_row FROM trades_clean")}
    source = source_trades.assign(source_row=range(1, len(source_trades) + 1))
    expected = source[source["source_row"].isin(loaded_rows)]["quantity"].astype(int).sum()
    assert scalar("SELECT SUM(quantity) FROM trades_clean") == expected


def test_control_total_of_usd_notional(scalar):
    """Hand-checked total for the sample file (see docs/mapping.md)."""
    assert scalar("SELECT ROUND(SUM(notional_usd), 2) FROM trades_clean") == pytest.approx(106852.40)