from datetime import date

from app.models.transaction import TransactionType
from app.services import analytics

TODAY = date(2026, 6, 6)


def test_load_ledger_decrypts_and_excludes_dupes_and_ambiguous(make_txn):
    make_txn(day="2026-05-01", amount=10.0, txn_type=TransactionType.debit,
             description="STARBUCKS", expense_category="food_and_drink")
    make_txn(day="2026-05-02", amount=99.0, txn_type=TransactionType.debit,
             description="DUPE", expense_category="shopping", is_duplicate=True)
    make_txn(day="2026-05-03", amount=88.0, txn_type=TransactionType.debit,
             description="AMBIG", expense_category="shopping", is_ambiguous=True)

    rows = analytics.load_ledger(_session_of(make_txn))
    assert len(rows) == 1
    assert rows[0]["description"] == "STARBUCKS"
    assert rows[0]["month"] == "2026-05"
    assert rows[0]["expense_category"] == "food_and_drink"


def test_is_transfer_matches_keywords():
    assert analytics.is_transfer("ZELLE PAYMENT TO JOHN")
    assert analytics.is_transfer("ONLINE TRANSFER TO SAVINGS")
    assert not analytics.is_transfer("STARBUCKS STORE 123")


def test_resolve_period_explicit_range():
    s, e, label = analytics.resolve_period(
        {"start": "2026-01-01", "end": "2026-03-31"}, today=TODAY)
    assert (s, e) == (date(2026, 1, 1), date(2026, 3, 31))
    assert "2026-01-01" in label


def test_resolve_period_month_and_quarter_and_year():
    s, e, label = analytics.resolve_period({"month": "2026-05"}, today=TODAY)
    assert (s, e, label) == (date(2026, 5, 1), date(2026, 5, 31), "May 2026")

    s, e, label = analytics.resolve_period({"quarter": "2026-Q1"}, today=TODAY)
    assert (s, e, label) == (date(2026, 1, 1), date(2026, 3, 31), "Q1 2026")

    s, e, label = analytics.resolve_period({"year": "2025"}, today=TODAY)
    assert (s, e, label) == (date(2025, 1, 1), date(2025, 12, 31), "2025")


def test_resolve_period_presets_relative_to_today():
    s, e, label = analytics.resolve_period({"preset": "last_month"}, today=TODAY)
    assert (s, e, label) == (date(2026, 5, 1), date(2026, 5, 31), "May 2026")

    s, e, label = analytics.resolve_period({"preset": "last_quarter"}, today=TODAY)
    assert (s, e, label) == (date(2026, 1, 1), date(2026, 3, 31), "Q1 2026")

    s, e, _ = analytics.resolve_period({"preset": "all_time"}, today=TODAY)
    assert s == date(1970, 1, 1) and e == TODAY


# Helper so tests can reach the session the factory writes to.
def _session_of(make_txn):
    return make_txn.__self_session__
