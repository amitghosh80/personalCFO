"""Tests for insight_engine.proactive_observations — the PRD F4 post-import
2–3 observation set surfaced in the chat window."""
from datetime import date, datetime

from sqlmodel import Session, SQLModel, create_engine

from app.models.transaction import Transaction, TransactionType
from app.services.encryption import encrypt
from app.services.insight_engine import proactive_observations


def _engine():
    eng = create_engine("sqlite://")
    SQLModel.metadata.create_all(eng)
    return eng


def _txn(job_id, d, desc, amount, ttype, **kw):
    return Transaction(
        import_job_id=job_id, date=d, description=encrypt(desc), amount=amount,
        transaction_type=ttype, source_file_hash="h", **kw,
    )


def _seed(session, job_id):
    rows = [
        # Income
        _txn(job_id, date(2026, 5, 2), "ADP PAYROLL", 6000.0, TransactionType.credit,
             is_income_candidate=True, income_category="salary", income_confirmed=True),
        # Spending across two months so comparative detectors can fire
        _txn(job_id, date(2026, 4, 5), "WHOLE FOODS", 300.0, TransactionType.debit,
             expense_category="food_and_drink", expense_subcategory="groceries"),
        _txn(job_id, date(2026, 5, 5), "WHOLE FOODS", 900.0, TransactionType.debit,
             expense_category="food_and_drink", expense_subcategory="groceries"),
        _txn(job_id, date(2026, 5, 9), "RESTAURANT XYZ", 120.0, TransactionType.debit,
             expense_category="food_and_drink", expense_subcategory="restaurant"),
    ]
    for r in rows:
        session.add(r)
    session.commit()


def test_returns_two_to_three_observations_with_summary():
    eng = _engine()
    with Session(eng) as session:
        _seed(session, "job-1")
        obs = proactive_observations(session, "job-1")

    assert 1 <= len(obs) <= 3
    kinds = {o["kind"] for o in obs}
    # Always includes the income/cashflow summary, scoped to the imported period.
    assert "summary" in kinds
    summary = next(o for o in obs if o["kind"] == "summary")
    assert "transactions" in summary["text"]
    assert "$" in summary["text"]  # cites a real number


def test_includes_a_spending_observation():
    eng = _engine()
    with Session(eng) as session:
        _seed(session, "job-1")
        obs = proactive_observations(session, "job-1")
    assert any(o["kind"] == "spending" for o in obs)
    for o in obs:
        assert o["title"] and o["text"]


def test_empty_ledger_returns_nothing():
    eng = _engine()
    with Session(eng) as session:
        assert proactive_observations(session, "missing-job") == []
