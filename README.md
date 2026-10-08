# ETL Testing Portfolio: trade data pipeline (work in progress)

A small ETL pipeline for fund trade data (CSV -> SQLite) and a test suite
that proves the data arriving in the warehouse is complete, valid and correct.

## Status

- [x] Source data with deliberately planted defects (duplicates, orphan accounts, invalid dates)
- [x] Source-to-target mapping spec with open questions for the analyst (docs/mapping.md)
- [x] ETL pipeline: staging, clean, rejected (with reason) and aggregated positions
- [ ] pytest + SQL test suite: completeness, schema, data quality, reconciliation, business rules
- [ ] Mutation testing: proving the tests catch injected bugs
- [ ] CI with GitHub Actions and HTML test reports

## Run it

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python -m etl.pipeline