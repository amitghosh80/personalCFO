"""Tests for insight_engine.dashboard_insights — the AMI-48 top-3 proactive
insights surfaced on the per-import summary page."""
from datetime import date

from sqlmodel import Session, SQLModel, create_engine

from app.models.transaction import Transaction, TransactionType
from app.services.encryption import encrypt
from app.services.insight_engine import dashboard_insights
from tests.conftest import TEST_USER_ID


def _engine():
    eng = create_engine("sqlite://")
    SQLModel.metadata.create_all(eng)
    return eng


def _txn(job_id, d, desc, amount, ttype, **kw):
    return Transaction(
        user_id=TEST_USER_ID,
        import_job_id=job_id, date=d, description=encrypt(desc), amount=amount,
        transaction_type=ttype, source_file_hash=job_id, **kw,
    )


def _seed_three_months(session):
    rows = [
        # March — baseline
        _txn("job-mar", date(2026, 3, 5), "TRADER JOES", 100.0, TransactionType.debit,
             expense_category="food_and_drink", expense_subcategory="groceries"),
        _txn("job-mar", date(2026, 3, 10), "MOVIE THEATER", 15.0, TransactionType.debit,
             expense_category="entertainment", expense_subcategory="movies"),
        # April — baseline
        _txn("job-apr", date(2026, 4, 5), "TRADER JOES", 105.0, TransactionType.debit,
             expense_category="food_and_drink", expense_subcategory="groceries"),
        _txn("job-apr", date(2026, 4, 10), "MOVIE THEATER", 15.0, TransactionType.debit,
             expense_category="entertainment", expense_subcategory="movies"),
        # May — the import under test: recurring grocery continues, a big
        # restaurant charge, an unusually large entertainment charge, and income.
        _txn("job-may", date(2026, 5, 2), "ADP PAYROLL", 6000.0, TransactionType.credit,
             is_income_candidate=True, income_category="salary", income_confirmed=True),
        _txn("job-may", date(2026, 5, 5), "TRADER JOES", 110.0, TransactionType.debit,
             expense_category="food_and_drink", expense_subcategory="groceries"),
        _txn("job-may", date(2026, 5, 12), "RESTAURANT XYZ", 300.0, TransactionType.debit,
             expense_category="food_and_drink", expense_subcategory="restaurant"),
        _txn("job-may", date(2026, 5, 20), "MOVIE THEATER", 150.0, TransactionType.debit,
             expense_category="entertainment", expense_subcategory="movies"),
    ]
    for r in rows:
        session.add(r)
    session.commit()


def test_returns_top_three_grounded_insights():
    eng = _engine()
    with Session(eng) as session:
        _seed_three_months(session)
        insights = dashboard_insights(session, TEST_USER_ID, "job-may")

    assert len(insights) == 3
    for ins in insights:
        assert ins["title"] and ins["text"] and ins["question"]
        assert "severity" not in ins

    types = {ins["type"] for ins in insights}
    # Food & drink dwarfs its April baseline, total spending swings >20% MoM,
    # and a recurring grocery charge exists — these should outrank the (mild,
    # low-severity) healthy savings-rate candidate for the top 3 slots.
    assert types == {"top_category_vs_prior", "mom_spending_change", "recurring_total"}

    top_category = next(i for i in insights if i["type"] == "top_category_vs_prior")
    assert "$410.00" in top_category["text"]  # May food_and_drink total (110 + 300)

    mom = next(i for i in insights if i["type"] == "mom_spending_change")
    assert "$560.00" in mom["text"]  # May total spending (410 + 150)


def test_single_month_import_does_not_crash_on_missing_prior_period():
    eng = _engine()
    with Session(eng) as session:
        session.add(_txn("job-only", date(2026, 6, 2), "ADP PAYROLL", 5000.0, TransactionType.credit,
                          is_income_candidate=True, income_category="salary", income_confirmed=True))
        session.add(_txn("job-only", date(2026, 6, 5), "WHOLE FOODS", 200.0, TransactionType.debit,
                          expense_category="food_and_drink", expense_subcategory="groceries"))
        session.commit()
        insights = dashboard_insights(session, TEST_USER_ID, "job-only")

    assert 1 <= len(insights) <= 3
    # No prior month exists, so the MoM-comparison type must not appear.
    assert all(i["type"] != "mom_spending_change" for i in insights)


def test_missing_job_returns_nothing():
    eng = _engine()
    with Session(eng) as session:
        assert dashboard_insights(session, TEST_USER_ID, "missing-job") == []
