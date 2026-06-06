from datetime import date
from types import SimpleNamespace

from app.models.transaction import TransactionType
from app.services import chat_service

TODAY = date(2026, 6, 6)


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_block(tid, name, tool_input):
    return SimpleNamespace(type="tool_use", id=tid, name=name, input=tool_input)


class FakeClient:
    """Scripts a sequence of responses. Each .create() pops the next one."""
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def test_loop_runs_tool_then_returns_grounded_answer(make_txn):
    s = make_txn.__self_session__
    make_txn(day="2026-05-02", amount=100.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")

    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[
            _tool_block("t1", "spending_by_category", {"period": {"month": "2026-05"}})]),
        SimpleNamespace(stop_reason="end_turn", content=[
            _text_block("In May 2026 you spent $100.00 on food.")]),
    ]
    client = FakeClient(responses)

    out = chat_service.answer_question(
        s, "How much did I spend in May?", [], client=client, model="m", today=TODAY)

    assert "100" in out["answer"]
    assert out["tools_used"] == [{"name": "spending_by_category", "input": {"period": {"month": "2026-05"}}}]
    # Second call must include the tool_result the loop fed back.
    second_msgs = client.calls[1]["messages"]
    assert any(
        isinstance(m["content"], list) and m["content"][0].get("type") == "tool_result"
        for m in second_msgs
    )


def test_loop_respects_iteration_cap(make_txn):
    s = make_txn.__self_session__
    # Always asks for a tool -> never terminates on its own.
    always_tool = SimpleNamespace(stop_reason="tool_use", content=[
        _tool_block("t", "recurring_charges", {})])
    client = FakeClient([always_tool] * 10)

    out = chat_service.answer_question(
        s, "loop forever?", [], client=client, model="m", today=TODAY, max_iterations=3)

    assert len(client.calls) == 3  # capped
    assert out["answer"]  # returns a graceful message, not an exception
