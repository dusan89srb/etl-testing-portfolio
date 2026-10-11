# Mutation testing results

Each bug was injected into etl/pipeline.py on its own, the suite was run,
and the change was reverted with `git checkout etl/pipeline.py`.

| # | Injected bug                     | Result                                      |
|---|----------------------------------|---------------------------------------------|
| 1 | De-duplication removed           | 42 errors: PRIMARY KEY rejected the load    |
| 2 | FX rate applied the wrong way    | 4 failed (EUR/GBP notional, control total)  |
| 3 | Normalization removed            | 4 failed (row 14 rejected as INVALID_SIDE)  |
| 4 | SELL counted as BUY              | 2 failed (golden positions, rebuild check)  |
| 5 | Rejected rows silently dropped   | 9 failed (completeness, rejection reasons)  |

Every injected bug was caught.