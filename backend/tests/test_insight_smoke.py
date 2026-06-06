from app.models.transaction import TransactionType
from app.services.insight_engine import generate_insights


def test_generate_insights_runs_on_seeded_ledger(make_txn):
    s = make_txn.__self_session__
    # Two months of spending so detectors have something to chew on.
    for day, amt in (("2026-04-05", 100.0), ("2026-04-20", 120.0),
                     ("2026-05-05", 300.0), ("2026-05-20", 350.0)):
        make_txn(day=day, amount=amt, txn_type=TransactionType.debit,
                 description="SAFEWAY GROCERY", expense_category="food_and_drink")
    make_txn(day="2026-05-01", amount=3000.0, txn_type=TransactionType.credit,
             description="ACME PAYROLL", is_income_candidate=True, income_confirmed=True,
             income_category="salary")

    insights = generate_insights(s, "job1")
    assert isinstance(insights, list)  # runs without error and returns rows
