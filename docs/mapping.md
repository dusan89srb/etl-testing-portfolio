# Source-to-target mapping: trades

## Target table: trades_clean

| Target column  | Source       | Rule                                                  |
|----------------|--------------|-------------------------------------------------------|
| source_row     | row number   | 1 = first data row of trades.csv                      |
| trade_id       | trade_id     | trim, upper-case; unique, first occurrence is kept    |
| account_id     | account_id   | trim, upper-case; must exist in accounts.csv          |
| ticker         | ticker       | trim, upper-case; must not be empty                   |
| side           | side         | trim, upper-case; BUY or SELL                         |
| quantity       | quantity     | integer greater than 0                                |
| price          | price        | decimal greater than 0                                |
| currency       | currency     | trim, upper-case; must exist in fx_rates.csv          |
| trade_date     | trade_date   | trim; valid date in YYYY-MM-DD format                 |
| notional_local | derived      | ROUND(quantity * price, 2)                            |
| notional_usd   | derived      | ROUND(quantity * price * rate_to_usd, 2)              |

## Rejection rules (checked in this order, the first failure wins)

1. DUPLICATE_TRADE_ID - trade_id already seen in an earlier row
2. MISSING_TICKER
3. INVALID_SIDE
4. INVALID_QUANTITY - not an integer, or not greater than 0
5. INVALID_PRICE - not a number, or not greater than 0
6. INVALID_DATE
7. UNKNOWN_CURRENCY
8. UNKNOWN_ACCOUNT

Rejected rows go to trades_rejected with source_row, trade_id,
reject_reason and the original row as JSON. No row may disappear.

## Target table: positions

One row per account_id + ticker, built from trades_clean:
- net_quantity = SUM(BUY quantity) - SUM(SELL quantity)
- trade_count  = number of clean trades

## Control totals for the sample file

- staged rows: 14, clean: 8, rejected: 6
- SUM(notional_usd) over trades_clean: 106,852.40

## Open questions

1. If the first occurrence of a duplicate trade_id is invalid, is the second one accepted?
   (Current spec: no, the second one is rejected as DUPLICATE_TRADE_ID.)
2. If two rows have the same trade_id but different values, is that a duplicate or a correction?
3. How should half a cent be rounded? Python's round() uses banker's rounding,
   while SQL's ROUND rounds half away from zero, so values like 0.125 can differ.
4. FX rates are fixed in the file. In a real-life scenario, which rate applies:
   the rate on the trade date or the latest available one?