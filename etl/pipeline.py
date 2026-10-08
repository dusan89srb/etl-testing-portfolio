"""Small ETL pipeline: trade CSV files -> SQLite warehouse.

Extract   read the source CSV files exactly as they are
Transform clean, validate and enrich each trade (rules in docs/mapping.md)
Load      write staging, clean, rejected and aggregated tables to SQLite
"""
import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "data" / "source"
DEFAULT_DB = ROOT / "data" / "warehouse.db"

TRADE_COLUMNS = ["trade_id", "account_id", "ticker", "side",
                 "quantity", "price", "currency", "trade_date"]
UPPERCASE_COLUMNS = ["trade_id", "account_id", "ticker", "side", "currency"]
VALID_SIDES = {"BUY", "SELL"}


# ---------------------------------------------------------------- extract
def extract(source_dir=SOURCE_DIR):
    """Read every source file into a list of dicts. Values stay raw text."""
    def read(file_name):
        with open(Path(source_dir) / file_name, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    return {
        "trades": read("trades.csv"),
        "accounts": read("accounts.csv"),
        "fx_rates": read("fx_rates.csv"),
    }


# -------------------------------------------------------------- transform
def normalize(row):
    """Trim whitespace everywhere and upper-case the code columns."""
    clean = {key.strip(): (value or "").strip() for key, value in row.items()}
    for column in UPPERCASE_COLUMNS:
        clean[column] = clean[column].upper()
    return clean


def reject_reason(row, seen_ids, accounts, fx_rates):
    """Return the first rule the row breaks, or None if the row is valid.

    The order of the checks is part of the specification (docs/mapping.md).
    """
    if row["trade_id"] in seen_ids:
        return "DUPLICATE_TRADE_ID"
    if not row["ticker"]:
        return "MISSING_TICKER"
    if row["side"] not in VALID_SIDES:
        return "INVALID_SIDE"
    try:
        if int(row["quantity"]) <= 0:
            return "INVALID_QUANTITY"
    except ValueError:
        return "INVALID_QUANTITY"
    try:
        if float(row["price"]) <= 0:
            return "INVALID_PRICE"
    except ValueError:
        return "INVALID_PRICE"
    try:
        datetime.strptime(row["trade_date"], "%Y-%m-%d")
    except ValueError:
        return "INVALID_DATE"
    if row["currency"] not in fx_rates:
        return "UNKNOWN_CURRENCY"
    if row["account_id"] not in accounts:
        return "UNKNOWN_ACCOUNT"
    return None


def transform(raw):
    """Split source trades into clean rows and rejected rows."""
    accounts = {a["account_id"].strip().upper() for a in raw["accounts"]}
    fx_rates = {r["currency"].strip().upper(): float(r["rate_to_usd"])
                for r in raw["fx_rates"]}

    clean, rejected, seen_ids = [], [], set()
    for source_row, original in enumerate(raw["trades"], start=1):
        row = normalize(original)
        reason = reject_reason(row, seen_ids, accounts, fx_rates)
        seen_ids.add(row["trade_id"])

        if reason:
            rejected.append({
                "source_row": source_row,
                "trade_id": row["trade_id"],
                "reject_reason": reason,
                "raw_record": json.dumps(original),
            })
            continue

        quantity = int(row["quantity"])
        price = float(row["price"])
        clean.append({
            "source_row": source_row,
            "trade_id": row["trade_id"],
            "account_id": row["account_id"],
            "ticker": row["ticker"],
            "side": row["side"],
            "quantity": quantity,
            "price": price,
            "currency": row["currency"],
            "trade_date": row["trade_date"],
            "notional_local": round(quantity * price, 2),
            "notional_usd": round(quantity * price * fx_rates[row["currency"]], 2),
        })
    return clean, rejected


# ------------------------------------------------------------------- load
SCHEMA = """
DROP TABLE IF EXISTS stg_trades;
DROP TABLE IF EXISTS dim_accounts;
DROP TABLE IF EXISTS dim_fx_rates;
DROP TABLE IF EXISTS trades_clean;
DROP TABLE IF EXISTS trades_rejected;
DROP TABLE IF EXISTS positions;

CREATE TABLE stg_trades (
    source_row  INTEGER PRIMARY KEY,
    trade_id    TEXT, account_id TEXT, ticker TEXT, side TEXT,
    quantity    TEXT, price TEXT, currency TEXT, trade_date TEXT
);
CREATE TABLE dim_accounts (
    account_id    TEXT PRIMARY KEY,
    account_name  TEXT NOT NULL,
    base_currency TEXT NOT NULL
);
CREATE TABLE dim_fx_rates (
    currency    TEXT PRIMARY KEY,
    rate_to_usd REAL NOT NULL
);
CREATE TABLE trades_clean (
    source_row     INTEGER NOT NULL,
    trade_id       TEXT PRIMARY KEY,
    account_id     TEXT NOT NULL,
    ticker         TEXT NOT NULL,
    side           TEXT NOT NULL,
    quantity       INTEGER NOT NULL,
    price          REAL NOT NULL,
    currency       TEXT NOT NULL,
    trade_date     TEXT NOT NULL,
    notional_local REAL NOT NULL,
    notional_usd   REAL NOT NULL
);
CREATE TABLE trades_rejected (
    source_row    INTEGER PRIMARY KEY,
    trade_id      TEXT,
    reject_reason TEXT NOT NULL,
    raw_record    TEXT NOT NULL
);
CREATE TABLE positions (
    account_id   TEXT NOT NULL,
    ticker       TEXT NOT NULL,
    net_quantity INTEGER NOT NULL,
    trade_count  INTEGER NOT NULL,
    PRIMARY KEY (account_id, ticker)
);
"""

POSITIONS_SQL = """
INSERT INTO positions (account_id, ticker, net_quantity, trade_count)
SELECT account_id,
       ticker,
       SUM(CASE WHEN side = 'BUY' THEN quantity ELSE -quantity END),
       COUNT(*)
FROM trades_clean
GROUP BY account_id, ticker;
"""


def insert_rows(conn, table, rows):
    if not rows:
        return
    columns = list(rows[0])
    placeholders = ", ".join("?" for _ in columns)
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        [tuple(row[c] for c in columns) for row in rows],
    )


def load(db_path, raw, clean, rejected):
    """Rebuild every table from scratch, so each run gives the same result."""
    staged = [{"source_row": i, **{c: r.get(c) or "" for c in TRADE_COLUMNS}}
              for i, r in enumerate(raw["trades"], start=1)]
    accounts = [{"account_id": a["account_id"].strip().upper(),
                 "account_name": a["account_name"].strip(),
                 "base_currency": a["base_currency"].strip().upper()}
                for a in raw["accounts"]]
    fx_rates = [{"currency": r["currency"].strip().upper(),
                 "rate_to_usd": float(r["rate_to_usd"])}
                for r in raw["fx_rates"]]

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        insert_rows(conn, "stg_trades", staged)
        insert_rows(conn, "dim_accounts", accounts)
        insert_rows(conn, "dim_fx_rates", fx_rates)
        insert_rows(conn, "trades_clean", clean)
        insert_rows(conn, "trades_rejected", rejected)
        conn.execute(POSITIONS_SQL)
        conn.commit()
    finally:
        conn.close()
    return db_path


# -------------------------------------------------------------------- run
def run(db_path=DEFAULT_DB, source_dir=SOURCE_DIR):
    raw = extract(source_dir)
    clean, rejected = transform(raw)
    load(db_path, raw, clean, rejected)
    return db_path


if __name__ == "__main__":
    path = run()
    print(f"ETL finished. Warehouse written to {path}")