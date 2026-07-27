"""AMI-33: when uncategorized spending exceeds the threshold (>10% of count OR
>15% of spend), the chatbot must warn before surfacing spending insights, until
the user dismisses it.
"""
from datetime import date
from types import SimpleNamespace

from app.models.transaction import TransactionType
from app.services import chat_service
from app.services.analytics import uncategorized_status
from tests.conftest import TEST_USER_ID

TODAY = date(2026, 6, 6)
D = TransactionType.debit


def _text(t):
    return SimpleNamespace(type="text", text=t)


def _tool(tid, name, inp):
    return SimpleNamespace(type="tool_use", id=tid, name=name, input=inp)


class FakeClient:
    def __init__(self, responses):
        self._r = list(responses)
        self.messages = SimpleNamespace(create=lambda **k: self._r.pop(0))


def _seed(make_txn, categorized, uncategorized, amount=50.0):
    for i in range(categorized):
        make_txn(day="2026-05-02", amount=amount, txn_type=D,
                 description=f"SAFEWAY{i}", expense_category="food_and_drink")
    for i in range(uncategorized):
        make_txn(day="2026-05-02", amount=amount, txn_type=D,
                 description=f"MYSTERY{i}", expense_category="other")


# ── status math ────────────────────────────────────────────────────────────────

def test_status_trips_over_count_threshold(make_txn):
    _seed(make_txn, categorized=8, uncategorized=2)   # 2/10 = 20% > 10%
    assert uncategorized_status(make_txn.__self_session__, TEST_USER_ID)["over"] is True


def test_status_below_threshold_is_not_over(make_txn):
    _seed(make_txn, categorized=19, uncategorized=1)  # 1/20 = 5%, spend 5%
    assert uncategorized_status(make_txn.__self_session__, TEST_USER_ID)["over"] is False


# ── chatbot gating ───────────────────────────────────────────────────────────

def _spending_answer_run(session, **kw):
    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[
            _tool("t1", "spending_by_category", {"period": {"month": "2026-05"}})]),
        SimpleNamespace(stop_reason="end_turn", content=[
            _text("In May 2026 you spent $500.00 on food.")]),
    ]
    return chat_service.answer_question(
        session, TEST_USER_ID, "How much did I spend?", [], client=FakeClient(responses),
        model="m", today=TODAY, **kw)


def test_chat_prepends_warning_when_over_and_spending_tool_used(make_txn):
    _seed(make_txn, categorized=8, uncategorized=2)
    out = _spending_answer_run(make_txn.__self_session__)
    assert "uncategorized" in out["answer"].lower()
    assert "500" in out["answer"]   # original grounded answer still present


def test_chat_warning_can_be_suppressed(make_txn):
    _seed(make_txn, categorized=8, uncategorized=2)
    out = _spending_answer_run(make_txn.__self_session__, suppress_data_warning=True)
    assert "uncategorized" not in out["answer"].lower()


def test_chat_no_warning_when_under_threshold(make_txn):
    _seed(make_txn, categorized=19, uncategorized=1)
    out = _spending_answer_run(make_txn.__self_session__)
    assert "uncategorized" not in out["answer"].lower()
