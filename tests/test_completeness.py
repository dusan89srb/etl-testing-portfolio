"""Completeness: no source row is lost, duplicated or invented on the way."""


def test_every_source_row_is_staged(scalar, source_trades):
    assert scalar("SELECT COUNT(*) FROM stg_trades") == len(source_trades)


def test_row_counts_reconcile(scalar):
    staged = scalar("SELECT COUNT(*) FROM stg_trades")
    clean = scalar("SELECT COUNT(*) FROM trades_clean")
    rejected = scalar("SELECT COUNT(*) FROM trades_rejected")
    assert clean + rejected == staged, (
        f"staged={staged}, clean={clean}, rejected={rejected}")


def test_every_staged_row_lands_somewhere(query):
    missing = query("""
        SELECT source_row FROM stg_trades
        EXCEPT
        SELECT source_row FROM trades_clean
        EXCEPT
        SELECT source_row FROM trades_rejected
    """)
    assert missing == [], f"source rows that vanished: {missing}"


def test_no_row_is_both_clean_and_rejected(query):
    overlap = query("""
        SELECT source_row FROM trades_clean
        INTERSECT
        SELECT source_row FROM trades_rejected
    """)
    assert overlap == [], f"rows in both tables: {overlap}"