"""Shared fixtures: run the ETL once, then let every test query the result."""
import sqlite3

import pandas as pd
import pytest

from etl.pipeline import SOURCE_DIR, run


@pytest.fixture(scope="session")
def db_path(tmp_path_factory):
    """Run the whole ETL once per test session into a fresh temporary database."""
    return run(db_path=tmp_path_factory.mktemp("warehouse") / "warehouse.db")


@pytest.fixture(scope="session")
def db(db_path):
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def query(db):
    """query("SELECT ...") -> list of row tuples."""
    def _query(sql, params=()):
        return db.execute(sql, params).fetchall()
    return _query


@pytest.fixture(scope="session")
def scalar(query):
    """scalar("SELECT COUNT(*) ...") -> the single value it returns."""
    def _scalar(sql, params=()):
        return query(sql, params)[0][0]
    return _scalar


@pytest.fixture(scope="session")
def source_trades():
    """The source file read independently of the ETL, every value as text."""
    return pd.read_csv(SOURCE_DIR / "trades.csv", dtype=str, keep_default_na=False)