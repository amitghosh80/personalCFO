"""Grounding eval for the chat substrate. Runs the REAL tool-use loop against a
fixed fixture ledger and asserts the model uses the right tool and states the
correct number. Skips if ANTHROPIC_API_KEY is not set.

Run from backend/:
    pytest tests/test_qa_eval.py -v
"""
import os
from datetime import date

import pytest

from app.config import get_settings
from app.models.transaction import TransactionType
from app.services.chat_service import answer_question
from tests.conftest import TEST_USER_ID

TODAY = date(2026, 6, 6)

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY") and not get_settings().anthropic_api_key,
    reason="ANTHROPIC_API_KEY not set; skipping live grounding eval",
)


@pytest.fixture
def seeded(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-02", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink", expense_subcategory="groceries")
    make_txn(day="2026-05-10", amount=40.0, txn_type=TransactionType.debit,
             description="CHIPOTLE", expense_category="food_and_drink", expense_subcategory="restaurant")
    make_txn(day="2026-05-01", amount=3000.0, txn_type=TransactionType.credit,
             description="ACME PAYROLL", is_income_candidate=True, income_confirmed=True,
             income_category="salary")
    return s


def test_spending_question_is_grounded(seeded):
    out = answer_question(seeded, TEST_USER_ID, "How much did I spend on food in May 2026?", [], today=TODAY)
    assert any(t["name"] == "spending_by_category" for t in out["tools_used"])
    assert "140" in out["answer"]


def test_income_question_is_grounded(seeded):
    out = answer_question(seeded, TEST_USER_ID, "What was my income in May 2026?", [], today=TODAY)
    assert any(t["name"] in ("income_summary", "cashflow_summary") for t in out["tools_used"])
    assert "3,000" in out["answer"] or "3000" in out["answer"]
