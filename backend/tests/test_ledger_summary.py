"""Whole-ledger monthly summary (the "View import" dashboard): spending by
category, per month, across every import — using the same load_ledger +
is_spending_txn math as the chat tools so the dashboard and chatbot agree.
"""
from datetime import date

from fastapi.testclient import TestClient

from app.main import app
from app.database import get_session
from app.models.transaction import TransactionType
from app.services.analytics import monthly_summary

D = TransactionType.debit
C = TransactionType.credit


def _override(session):
    def _dep():
        yield session
    return _dep


def test_monthly_summary_aggregates_and_excludes_non_spending(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-04-03", amount=100.0, txn_type=D, description="SAFEWAY", expense_category="food_and_drink")
    make_txn(day="2026-04-10", amount=50.0, txn_type=D, description="SHELL", expense_category="transportation")
    make_txn(day="2026-05-02", amount=200.0, txn_type=D, description="RENT", expense_category="housing")
    # Non-spending (CC payment) must be excluded from expenses/categories.
    make_txn(day="2026-04-15", amount=1200.0, txn_type=D, description="CHASE CREDIT CRD AUTOPAY", expense_category="credit_card_payment")
    make_txn(day="2026-04-01", amount=5000.0, txn_type=C, description="GUSTO PAYROLL",
             is_income_candidate=True, income_confirmed=True, income_category="salary")

    out = monthly_summary(s)
    months = {r["month"]: r for r in out["monthly_breakdown"]}

    assert set(months) == {"2026-04", "2026-05"}
    assert months["2026-04"]["expenses"] == 150.0        # CC payment excluded
    assert months["2026-04"]["income"] == 5000.0
    assert months["2026-05"]["expenses"] == 200.0
    cats = {c["category"]: c["amount"] for c in months["2026-04"]["top_categories"]}
    assert cats["food_and_drink"] == 100.0
    assert cats["transportation"] == 50.0
    assert "credit_card_payment" not in cats
    assert out["total_transactions"] == 5


def test_ledger_summary_endpoint(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-04-03", amount=100.0, txn_type=D, description="SAFEWAY", expense_category="food_and_drink")
    app.dependency_overrides[get_session] = _override(s)
    res = TestClient(app).get("/api/summary")
    assert res.status_code == 200
    body = res.json()
    assert body["total_transactions"] == 1
    assert body["monthly_breakdown"][0]["month"] == "2026-04"
