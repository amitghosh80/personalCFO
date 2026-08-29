from datetime import date
from types import SimpleNamespace

from app.models.transaction import TransactionType
from app.services import chat_service
from tests.conftest import TEST_USER_ID

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
        s, TEST_USER_ID, "How much did I spend in May?", [], client=client, model="m", today=TODAY)

    assert "100" in out["answer"]
    assert len(out["tools_used"]) == 1
    used = out["tools_used"][0]
    assert used["name"] == "spending_by_category"
    assert used["input"] == {"period": {"month": "2026-05"}}
    assert used["result"]["total_spending"] == 100.0
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
        s, TEST_USER_ID, "loop forever?", [], client=client, model="m", today=TODAY, max_iterations=3)

    assert len(client.calls) == 3  # capped
    assert out["answer"]  # returns a graceful message, not an exception
    assert out["followups"] == []  # no extra call for a fallback answer


def test_followups_generated_from_clean_answer(make_txn):
    s = make_txn.__self_session__
    responses = [
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("You spent $100 on food.")]),
        SimpleNamespace(stop_reason="end_turn", content=[
            _text_block('["What about groceries?", "How does that compare to last month?"]')]),
    ]
    client = FakeClient(responses)

    out = chat_service.answer_question(
        s, TEST_USER_ID, "How much did I spend?", [], client=client, model="m", today=TODAY)

    assert out["followups"] == ["What about groceries?", "How does that compare to last month?"]
    assert len(client.calls) == 2
    followup_call = client.calls[1]
    assert "How much did I spend?" in followup_call["messages"][0]["content"]
    assert "You spent $100 on food." in followup_call["messages"][0]["content"]


def test_followups_default_to_empty_on_unparseable_response(make_txn):
    s = make_txn.__self_session__
    responses = [
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("You spent $100 on food.")]),
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("not json")]),
    ]
    client = FakeClient(responses)

    out = chat_service.answer_question(
        s, TEST_USER_ID, "How much did I spend?", [], client=client, model="m", today=TODAY)

    assert out["answer"] == "You spent $100 on food."
    assert out["followups"] == []


def test_system_prompt_includes_todays_date(make_txn):
    s = make_txn.__self_session__
    client = FakeClient([
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("hi")]),
    ])
    chat_service.answer_question(s, TEST_USER_ID, "hello", [], client=client, model="m", today=TODAY)
    system_arg = client.calls[0]["system"]
    assert "2026-06-06" in system_arg


def test_system_prompt_includes_data_coverage_range(make_txn):
    """The model must know the actual data window so relative periods that fall
    outside it (e.g. 'last month' when data is months old) don't silently return
    $0 with no explanation."""
    s = make_txn.__self_session__
    make_txn(day="2026-02-10", amount=50.0, txn_type=TransactionType.debit,
             description="SAFEWAY", expense_category="food_and_drink")
    make_txn(day="2026-04-05", amount=80.0, txn_type=TransactionType.debit,
             description="SHELL", expense_category="transportation")
    client = FakeClient([
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("ok")]),
    ])
    chat_service.answer_question(s, TEST_USER_ID, "what did I spend?", [], client=client, model="m", today=TODAY)
    system_arg = client.calls[0]["system"]
    assert "2026-02-10" in system_arg
    assert "2026-04-09" not in system_arg  # actual max is 2026-04-05
    assert "2026-04-05" in system_arg


def test_history_is_truncated_to_recent_turns(make_txn):
    """Older turns are dropped before the call so a long conversation doesn't
    grow request cost unboundedly (AMI cost-control)."""
    s = make_txn.__self_session__
    client = FakeClient([
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("ok")]),
    ])
    long_history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
        for i in range(30)
    ]

    chat_service.answer_question(
        s, TEST_USER_ID, "what now?", long_history, client=client, model="m", today=TODAY)

    # FakeClient stores `messages` by reference, and the loop appends the
    # assistant's own reply to that same list after the call completes — so
    # inspect only the slice that was actually sent, not the mutated tail.
    sent_messages = client.calls[0]["messages"][:21]
    # Last 20 history messages + the new question.
    assert len(sent_messages) == 21
    assert sent_messages[0]["content"] == "turn 10"
    assert sent_messages[-2]["content"] == "turn 29"
    assert sent_messages[-1]["content"] == "what now?"


def test_system_prompt_handles_empty_ledger(make_txn):
    """No imported data: prompt should still build (no coverage range crash)."""
    s = make_txn.__self_session__
    client = FakeClient([
        SimpleNamespace(stop_reason="end_turn", content=[_text_block("ok")]),
    ])
    chat_service.answer_question(s, TEST_USER_ID, "what did I spend?", [], client=client, model="m", today=TODAY)
    assert client.calls[0]["system"]  # built without error
