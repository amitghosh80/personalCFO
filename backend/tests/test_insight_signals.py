"""collect_signals() exposes the detector battery over the whole ledger as
candidate dicts WITHOUT persisting Insight rows — the grounded seed for the AI
insight layer. generate_insights() must keep persisting as before."""
from sqlmodel import select

from app.models.insight import Insight
from app.models.transaction import TransactionType
from app.services.insight_engine import collect_signals, generate_insights


def _seed_two_months(make_txn):
    # Two months of grocery spending + a salary credit -> enough for detectors.
    for day, amt in [("2026-04-03", 200.0), ("2026-04-18", 150.0),
                     ("2026-05-05", 400.0), ("2026-05-20", 350.0)]:
        make_txn(day=day, amount=amt, txn_type=TransactionType.debit,
                 description="SAFEWAY", expense_category="food_and_drink")
    make_txn(day="2026-05-01", amount=5000.0, txn_type=TransactionType.credit,
             description="ACME PAYROLL", is_income_candidate=True,
             income_confirmed=True, income_category="salary")


def test_collect_signals_returns_candidate_dicts(make_txn):
    s = make_txn.__self_session__
    _seed_two_months(make_txn)

    signals = collect_signals(s)

    assert isinstance(signals, list)
    assert len(signals) > 0
    for sig in signals:
        assert {"insight_type", "title", "explanation", "severity"} <= set(sig)


def test_collect_signals_does_not_persist(make_txn):
    s = make_txn.__self_session__
    _seed_two_months(make_txn)

    collect_signals(s)

    # No Insight rows should have been written by collect_signals.
    assert s.exec(select(Insight)).all() == []


def test_generate_insights_still_persists(make_txn):
    s = make_txn.__self_session__
    _seed_two_months(make_txn)

    created = generate_insights(s, "job1")

    assert len(created) > 0
    assert len(s.exec(select(Insight)).all()) == len(created)
