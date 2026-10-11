"""Schema: target tables have exactly the agreed columns, types and keys."""
import pytest

EXPECTED_COLUMNS = {
    "trades_clean": {
        "source_row": "INTEGER", "trade_id": "TEXT", "account_id": "TEXT",
        "ticker": "TEXT", "side": "TEXT", "quantity": "INTEGER", "price": "REAL",
        "currency": "TEXT", "trade_date": "TEXT", "notional_local": "REAL",
        "notional_usd": "REAL",
    },
    "trades_rejected": {
        "source_row": "INTEGER", "trade_id": "TEXT",
        "reject_reason": "TEXT", "raw_record": "TEXT",
    },
    "positions": {
        "account_id": "TEXT", "ticker": "TEXT",
        "net_quantity": "INTEGER", "trade_count": "INTEGER",
    },
}

EXPECTED_PRIMARY_KEYS = {
    "trades_clean": ["trade_id"],
    "trades_rejected": ["source_row"],
    "positions": ["account_id", "ticker"],
}


@pytest.mark.parametrize("table", EXPECTED_COLUMNS)
def test_columns_and_types(query, table):
    # PRAGMA table_info rows: (cid, name, type, notnull, default, pk)
    actual = {name: col_type for _, name, col_type, *_ in query(f"PRAGMA table_info({table})")}
    assert actual == EXPECTED_COLUMNS[table]


@pytest.mark.parametrize("table", EXPECTED_PRIMARY_KEYS)
def test_primary_keys(query, table):
    info = query(f"PRAGMA table_info({table})")
    key_columns = [name for _, name, _, _, _, pk in sorted(info, key=lambda r: r[5]) if pk]
    assert key_columns == EXPECTED_PRIMARY_KEYS[table]


@pytest.mark.parametrize("table", EXPECTED_COLUMNS)
def test_stored_values_match_declared_types(query, table):
    
    sqlite_type = {"INTEGER": "integer", "REAL": "real", "TEXT": "text"}
    for column, declared in EXPECTED_COLUMNS[table].items():
        wrong = query(f"""
            SELECT DISTINCT typeof({column}) FROM {table}
            WHERE typeof({column}) <> ?
        """, (sqlite_type[declared],))
        assert wrong == [], f"{table}.{column} holds {wrong}, expected {declared}"