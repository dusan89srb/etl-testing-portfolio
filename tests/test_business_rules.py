"""Business rules and aggregations, checked against hand-calculated golden values."""
import pytest

# Calculated by hand from data/source/trades.csv, independently of the ETL code.
EXPECTED_POSITIONS = {
    ("A001", "AAPL"): (60, 2),    # T001 BUY 100, T007 SELL 40
    ("A001", "MSFT"): (60, 2),    # T002 BUY 50, T013 BUY 10
    ("A002", "SAP"): (150, 2),    # T003 BUY 200, T004 SELL 50 (T012 rejected)
    ("A003", "AAPL"): (30, 1),    # T005 BUY 30
    ("A003", "VOD"): (1000, 1),   # T006 BUY 1000
}


def test_positions_match_golden_values(query):
    actual = {(acc, tic): (qty, cnt) for acc, tic, qty, cnt
              in query("SELECT account_id, ticker, net_quantity, trade_count FROM positions")}
    assert actual == EXPECTED_POSITIONS


def test_positions_equal_sum_of_clean_trades(query):
    """Aggregation reconciliation: positions must be rebuildable from trades_clean."""
    differences = query("""
        WITH expected AS (
            SELECT account_id, ticker,
                   SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END) AS net_quantity,
                   COUNT(*) AS trade_count
            FROM trades_clean
            GROUP BY account_id, ticker
        )
        SELECT * FROM expected
        EXCEPT
        SELECT account_id, ticker, net_quantity, trade_count FROM positions
    """)
    assert differences == []


@pytest.mark.parametrize("trade_id, expected_usd", [
    ("T001", 19050.00),   # USD: 100 x 190.50 x 1.00
    ("T003", 38880.00),   # EUR: 200 x 180.00 x 1.08
    ("T006", 914.40),     # GBP: 1000 x 0.72 x 1.27
])
def test_known_usd_notional(scalar, trade_id, expected_usd):
    actual = scalar("SELECT notional_usd FROM trades_clean WHERE trade_id = ?", (trade_id,))
    assert actual == pytest.approx(expected_usd, abs=0.005)


def test_messy_row_is_normalized_not_rejected(query):
    """Source row 14 has spaces and lower case; the spec says clean it, not drop it."""
    row = query("""SELECT trade_id, account_id, ticker, side, currency
                   FROM trades_clean WHERE source_row = 14""")
    assert row == [("T013", "A001", "MSFT", "BUY", "USD")]