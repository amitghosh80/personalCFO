from datetime import date

import pytest

from app.services.chat_usage import ChatUsageLimitExceeded, check_and_record_usage
from tests.conftest import TEST_USER_ID

DAY1 = date(2026, 6, 6)
DAY2 = date(2026, 6, 7)


def test_increments_and_raises_once_limit_hit(session):
    assert check_and_record_usage(session, TEST_USER_ID, limit=2, today=DAY1) == 1
    assert check_and_record_usage(session, TEST_USER_ID, limit=2, today=DAY1) == 2
    with pytest.raises(ChatUsageLimitExceeded):
        check_and_record_usage(session, TEST_USER_ID, limit=2, today=DAY1)


def test_counter_resets_on_a_new_day(session):
    check_and_record_usage(session, TEST_USER_ID, limit=1, today=DAY1)
    with pytest.raises(ChatUsageLimitExceeded):
        check_and_record_usage(session, TEST_USER_ID, limit=1, today=DAY1)

    # A new day gets its own counter.
    assert check_and_record_usage(session, TEST_USER_ID, limit=1, today=DAY2) == 1


def test_counts_are_per_user(session):
    other_user_id = TEST_USER_ID + 1
    check_and_record_usage(session, TEST_USER_ID, limit=1, today=DAY1)
    assert check_and_record_usage(session, other_user_id, limit=1, today=DAY1) == 1
