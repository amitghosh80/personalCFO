"""AMI-43: resolve_period must handle free-form natural-language period strings
('January', 'last week', 'yesterday', 'since March', 'Q1 2026', 'last month'),
not just the structured {preset|month|quarter|year|start/end} dict.

All cases anchored to today = 2026-06-30.
"""
from datetime import date

import pytest

from app.services.analytics import resolve_period

TODAY = date(2026, 6, 30)


def r(spec):
    return resolve_period(spec, today=TODAY)


def test_last_month_string():
    s, e, _ = r("last month")
    assert (s, e) == (date(2026, 5, 1), date(2026, 5, 31))


def test_this_month_string():
    s, e, _ = r("this month")
    assert (s, e) == (date(2026, 6, 1), date(2026, 6, 30))


def test_yesterday():
    s, e, _ = r("yesterday")
    assert (s, e) == (date(2026, 6, 29), date(2026, 6, 29))


def test_last_week_is_trailing_seven_days():
    s, e, _ = r("last week")
    assert (s, e) == (date(2026, 6, 24), date(2026, 6, 30))


def test_bare_month_name_resolves_to_most_recent_past():
    # January already happened this year → 2026-01
    s, e, _ = r("January")
    assert (s, e) == (date(2026, 1, 1), date(2026, 1, 31))


def test_bare_month_name_future_rolls_to_prior_year():
    # July hasn't happened in 2026 yet → most recent is 2025-07
    s, e, _ = r("July")
    assert (s, e) == (date(2025, 7, 1), date(2025, 7, 31))


def test_quarter_with_year():
    s, e, label = r("Q1 2026")
    assert (s, e) == (date(2026, 1, 1), date(2026, 3, 31))
    assert "Q1 2026" in label


def test_since_month():
    s, e, _ = r("since March")
    assert (s, e) == (date(2026, 3, 1), date(2026, 6, 30))


def test_text_key_in_dict_also_supported():
    s, e, _ = r({"text": "last month"})
    assert (s, e) == (date(2026, 5, 1), date(2026, 5, 31))


def test_structured_dict_still_works():
    s, e, _ = r({"month": "2026-04"})
    assert (s, e) == (date(2026, 4, 1), date(2026, 4, 30))
