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


def test_spending_by_category_groups_and_excludes_non_spending(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-02", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink", expense_subcategory="groceries")
    make_txn(day="2026-05-10", amount=40.0, txn_type=TransactionType.debit,
             description="CHIPOTLE", expense_category="food_and_drink", expense_subcategory="restaurant")
    make_txn(day="2026-05-15", amount=60.0, txn_type=TransactionType.debit,
             description="SHELL", expense_category="transportation", expense_subcategory="gas")
    # Non-spending: a credit-card payment debit must be excluded.
    make_txn(day="2026-05-20", amount=500.0, txn_type=TransactionType.debit,
             description="CHASE CARD PAYMENT", expense_category="credit_card_payment")
    # Out of period: ignored.
    make_txn(day="2026-04-01", amount=999.0, txn_type=TransactionType.debit,
             description="OLD", expense_category="shopping")

    out = analytics.spending_by_category(s, {"month": "2026-05"}, today=TODAY)

    assert out["total_spending"] == 200.0
    assert out["transaction_count"] == 3
    top = out["by_primary"][0]
    assert top["category"] == "food_and_drink"
    assert top["amount"] == 140.0
    subs = {x["subcategory"]: x["amount"] for x in top["by_subcategory"]}
    assert subs == {"groceries": 100.0, "restaurant": 40.0}


def test_spending_by_category_filtered_to_one_primary(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-02", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink", expense_subcategory="groceries")
    make_txn(day="2026-05-15", amount=60.0, txn_type=TransactionType.debit,
             description="SHELL", expense_category="transportation", expense_subcategory="gas")

    out = analytics.spending_by_category(s, {"month": "2026-05"}, primary="transportation", today=TODAY)
    assert out["total_spending"] == 60.0
    assert len(out["by_primary"]) == 1
    assert out["by_primary"][0]["category"] == "transportation"


def test_cashflow_summary_totals_and_by_month(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-01", amount=3000.0, txn_type=TransactionType.credit,
             description="ACME PAYROLL", is_income_candidate=True, income_confirmed=True,
             income_category="salary")
    make_txn(day="2026-05-05", amount=200.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")
    make_txn(day="2026-06-05", amount=100.0, txn_type=TransactionType.debit,
             description="SHELL", expense_category="transportation")

    out = analytics.cashflow_summary(s, {"start": "2026-05-01", "end": "2026-06-30"}, today=TODAY)
    assert out["total_credits"] == 3000.0
    assert out["total_debits"] == 300.0
    assert out["net_cashflow"] == 2700.0
    assert out["confirmed_income"] == 3000.0
    months = {m["month"]: m for m in out["by_month"]}
    assert months["2026-05"]["debits"] == 200.0
    assert months["2026-06"]["debits"] == 100.0


def test_income_summary_prefers_confirmed_and_groups_by_category(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-01", amount=3000.0, txn_type=TransactionType.credit,
             description="ACME PAYROLL", is_income_candidate=True, income_confirmed=True,
             income_category="salary")
    make_txn(day="2026-05-20", amount=50.0, txn_type=TransactionType.credit,
             description="SAVINGS INTEREST", is_income_candidate=True, income_confirmed=True,
             income_category="interest")
    # Unconfirmed candidate is ignored once confirmed income exists.
    make_txn(day="2026-05-25", amount=999.0, txn_type=TransactionType.credit,
             description="MAYBE INCOME", is_income_candidate=True, income_confirmed=None,
             income_category="other")

    out = analytics.income_summary(s, {"month": "2026-05"}, today=TODAY)
    assert out["basis"] == "confirmed"
    assert out["total_income"] == 3050.0
    by_cat = {c["category"]: c["amount"] for c in out["by_category"]}
    assert by_cat == {"salary": 3000.0, "interest": 50.0}


def test_compare_periods_delta_and_pct(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-04-10", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")
    make_txn(day="2026-05-10", amount=150.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")

    out = analytics.compare_periods(
        s, {"month": "2026-04"}, {"month": "2026-05"}, today=TODAY)
    assert out["period_a"]["total"] == 100.0
    assert out["period_b"]["total"] == 150.0
    assert out["delta"] == 50.0
    assert out["pct_change"] == 50.0


def test_recurring_charges_detects_monthly_merchant(make_txn):
    s = make_txn.__self_session__
    for day in ("2026-03-15", "2026-04-15", "2026-05-15"):
        make_txn(day=day, amount=15.99, txn_type=TransactionType.debit,
                 description="NETFLIX SUBSCRIPTION", expense_category="subscriptions",
                 expense_subcategory="streaming")
    # A one-off should not be flagged.
    make_txn(day="2026-05-02", amount=200.0, txn_type=TransactionType.debit,
             description="RANDOM SHOP", expense_category="shopping")

    out = analytics.recurring_charges(s, today=TODAY)
    merchants = {r["merchant"]: r for r in out["recurring"]}
    assert "NETFLIX SUBSCRIPTION" in merchants
    netflix = merchants["NETFLIX SUBSCRIPTION"]
    assert netflix["occurrences"] == 3
    assert netflix["typical_amount"] == 15.99
    assert netflix["cadence"] == "monthly"
    assert "RANDOM SHOP" not in merchants
