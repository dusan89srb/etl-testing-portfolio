"""Negative tests: bad source rows are rejected for the right reason and kept for audit."""
import json

import pytest

EXPECTED_REJECTIONS = {
    8: ("T007", "DUPLICATE_TRADE_ID"),
    9: ("T008", "UNKNOWN_ACCOUNT"),
    10: ("T009", "INVALID_QUANTITY"),
    11: ("T010", "UNKNOWN_CURRENCY"),
    12: ("T011", "MISSING_TICKER"),
    13: ("T012", "INVALID_DATE"),
}


def test_exactly_the_expected_rows_are_rejected(query):
    actual = {row for (row,) in query("SELECT source_row FROM trades_rejected")}
    assert actual == set(EXPECTED_REJECTIONS)


@pytest.mark.parametrize("source_row, expected", EXPECTED_REJECTIONS.items())
def test_rejection_reason(query, source_row, expected):
    actual = query("SELECT trade_id, reject_reason FROM trades_rejected WHERE source_row = ?",
                   (source_row,))
    assert actual == [expected]


def test_first_occurrence_of_duplicate_is_kept(scalar):
    assert scalar("SELECT source_row FROM trades_clean WHERE trade_id = 'T007'") == 7


def test_raw_record_is_preserved_for_audit(query, source_trades):
    """The rejected table keeps the original row exactly as received."""
    for source_row, raw_record in query("SELECT source_row, raw_record FROM trades_rejected"):
        original = source_trades.iloc[source_row - 1].to_dict()
        assert json.loads(raw_record) == original