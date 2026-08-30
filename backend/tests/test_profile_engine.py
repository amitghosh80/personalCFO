from datetime import date
from app.models.transaction import TransactionType

from app.services import profile_engine
from tests.conftest import TEST_USER_ID

TODAY = date(2026, 8, 15)


def _profile(session, today=TODAY):
    return profile_engine.get_financial_profile(session, TEST_USER_ID, today=today)


def test_empty_ledger_is_insufficient_data_everywhere(session):
    metrics = _profile(session)["metrics"]
    for key in (
        "committed_monthly_spend", "average_monthly_burn", "average_monthly_income",
        "fixed_vs_discretionary", "savings_rate", "fees_and_interest",
    ):
        assert metrics[key]["status"] == "insufficient_data"
        assert metrics[key]["requirement"]


def test_committed_monthly_spend_detects_stable_monthly_charges(make_txn):
    for m in ("05", "06", "07"):
        make_txn(day=f"2026-{m}-05", amount=17.99, txn_type=TransactionType.debit,
                 description="NETFLIX.COM", expense_category="subscriptions")
        make_txn(day=f"2026-{m}-01", amount=1500.00, txn_type=TransactionType.debit,
                 description="RENT PAYMENT", expense_category="housing")

    metrics = _profile(make_txn.__self_session__)["metrics"]
    m1 = metrics["committed_monthly_spend"]
    assert m1["status"] == "ok"
    payload = m1["payload"]
    assert payload["commitment_count"] == 2
    assert round(payload["committed_monthly_total"], 2) == 1517.99
    assert round(payload["committed_annualized_total"], 2) == round(1517.99 * 12, 2)
    assert m1["confidence_label"] == "high"


def test_committed_monthly_spend_splits_merged_price_tiers(make_txn):
    # Some billers (Apple, Google) reuse one generic descriptor for multiple
    # distinct subscriptions — the two price points here share identical text.
    for m in ("05", "06"):
        make_txn(day=f"2026-{m}-10", amount=2.99, txn_type=TransactionType.debit,
                 description="APPLE.COM/BILL INTERNET CHARGE", expense_category="subscriptions")
        make_txn(day=f"2026-{m}-22", amount=10.92, txn_type=TransactionType.debit,
                 description="APPLE.COM/BILL INTERNET CHARGE", expense_category="subscriptions")

    metrics = _profile(make_txn.__self_session__, today=date(2026, 7, 1))["metrics"]
    payload = metrics["committed_monthly_spend"]["payload"]
    assert payload["commitment_count"] == 2
    amounts = sorted(c["amount_per_period"] for c in payload["commitments"])
    assert amounts == [2.99, 10.92]
    assert round(payload["committed_monthly_total"], 2) == round(2.99 + 10.92, 2)


def test_committed_monthly_spend_survives_a_stale_ledger(make_txn):
    # Last import was two months ago; the mortgage is presumably still active
    # but there's no newer data to prove it — it must not be pruned as
    # "cancelled" just because the real calendar date has moved on.
    make_txn(day="2026-04-02", amount=1540.24, txn_type=TransactionType.debit,
             description="ROCKET MORTGAGE LOAN", expense_category="housing")
    make_txn(day="2026-05-04", amount=1540.24, txn_type=TransactionType.debit,
             description="ROCKET MORTGAGE LOAN", expense_category="housing")

    metrics = _profile(make_txn.__self_session__, today=date(2026, 8, 23))["metrics"]
    payload = metrics["committed_monthly_spend"]["payload"]
    assert payload["commitment_count"] == 1
    assert payload["commitments"][0]["merchant"] == "Rocket Mortgage Loan"


def test_committed_monthly_spend_still_drops_a_genuinely_cancelled_charge(make_txn):
    # The ledger DOES extend close to "today" via unrelated activity, so a
    # commitment that stopped months ago should still be pruned.
    make_txn(day="2026-04-02", amount=1540.24, txn_type=TransactionType.debit,
             description="ROCKET MORTGAGE LOAN", expense_category="housing")
    make_txn(day="2026-05-04", amount=1540.24, txn_type=TransactionType.debit,
             description="ROCKET MORTGAGE LOAN", expense_category="housing")
    for m, amount in zip(("06", "07", "08"), (40.0, 85.0, 22.0)):
        make_txn(day=f"2026-{m}-15", amount=amount, txn_type=TransactionType.debit,
                 description="GROCERY STORE", expense_category="food_and_drink")

    metrics = _profile(make_txn.__self_session__, today=date(2026, 8, 23))["metrics"]
    payload = metrics["committed_monthly_spend"]["payload"]
    assert payload["commitment_count"] == 0


def test_committed_monthly_spend_rejects_coincidental_same_amount_repeats(make_txn):
    # Two same-priced coffee purchases that happen to land ~35 days apart (inside
    # the "monthly" gap window) but on different days of the month. This is not
    # a recurring commitment — it's a coincidence — and must not be surfaced.
    make_txn(day="2026-05-01", amount=5.25, txn_type=TransactionType.debit,
             description="STARBUCKS STORE #123", expense_category="dining")
    make_txn(day="2026-06-05", amount=5.25, txn_type=TransactionType.debit,
             description="STARBUCKS STORE #123", expense_category="dining")

    metrics = _profile(make_txn.__self_session__, today=date(2026, 7, 1))["metrics"]
    payload = metrics["committed_monthly_spend"]["payload"]
    assert payload["commitment_count"] == 0


def test_committed_monthly_spend_excludes_non_bill_categories(make_txn):
    # Two grocery runs that happen to satisfy amount stability, monthly cadence,
    # AND the day-of-month anchor (all other checks pass) — but groceries are a
    # many-independent-purchases category, so a matching pair out of many visits
    # is coincidence, not a bill. Must be excluded on category grounds alone.
    make_txn(day="2026-05-05", amount=62.40, txn_type=TransactionType.debit,
             description="WHOLE FOODS MARKET", expense_category="food_and_drink")
    make_txn(day="2026-06-06", amount=62.40, txn_type=TransactionType.debit,
             description="WHOLE FOODS MARKET", expense_category="food_and_drink")

    metrics = _profile(make_txn.__self_session__, today=date(2026, 7, 1))["metrics"]
    payload = metrics["committed_monthly_spend"]["payload"]
    assert payload["commitment_count"] == 0


def test_committed_monthly_spend_accepts_month_end_anchored_billing(make_txn):
    # A real subscription billed on the last day of the month lands on the 31st
    # in a long month and the 28th in February — the day numbers differ by 3 but
    # both are "last day of the month," so this must still be detected.
    make_txn(day="2026-01-31", amount=9.99, txn_type=TransactionType.debit,
             description="APPLE.COM/BILL", expense_category="subscriptions")
    make_txn(day="2026-02-28", amount=9.99, txn_type=TransactionType.debit,
             description="APPLE.COM/BILL", expense_category="subscriptions")

    metrics = _profile(make_txn.__self_session__, today=date(2026, 3, 1))["metrics"]
    payload = metrics["committed_monthly_spend"]["payload"]
    assert payload["commitment_count"] == 1
    assert payload["commitments"][0]["merchant"] == "Apple.Com/Bill"


def test_average_monthly_burn_3mo_and_month_to_date(make_txn):
    make_txn(day="2026-04-10", amount=1000.0, txn_type=TransactionType.debit, description="OLD MONTH", expense_category="shopping")
    make_txn(day="2026-05-10", amount=5000.0, txn_type=TransactionType.debit, description="MAY SPEND", expense_category="shopping")
    make_txn(day="2026-06-10", amount=5200.0, txn_type=TransactionType.debit, description="JUN SPEND", expense_category="shopping")
    make_txn(day="2026-07-10", amount=5400.0, txn_type=TransactionType.debit, description="JUL SPEND", expense_category="shopping")
    make_txn(day="2026-08-05", amount=800.0, txn_type=TransactionType.debit, description="AUG SPEND SO FAR", expense_category="shopping")

    metrics = _profile(make_txn.__self_session__)["metrics"]
    burn = metrics["average_monthly_burn"]
    assert burn["status"] == "ok"
    payload = burn["payload"]
    assert payload["burn_3mo"] == 5200.0
    assert payload["burn_6mo"] is None
    assert payload["month_to_date"] == 800.0
    assert payload["months_in_window"] == 3

    series = {row["month"]: row for row in payload["monthly_series"]}
    assert series["2026-05"]["vs_prev_month_pct"] is None  # first month in window, no prior point
    assert series["2026-06"]["vs_prev_month_pct"] == 4.0  # (5200-5000)/5000
    assert series["2026-07"]["transaction_count"] == 1
    assert series["2026-07"]["top_categories"] == [
        {"category": "shopping", "display": "Shopping", "amount": 5400.0}
    ]


def test_average_monthly_burn_category_breakdown_splits_by_month(make_txn):
    make_txn(day="2026-06-05", amount=1500.0, txn_type=TransactionType.debit,
             description="RENT PAYMENT", expense_category="housing")
    make_txn(day="2026-06-12", amount=300.0, txn_type=TransactionType.debit,
             description="WHOLE FOODS", expense_category="food_and_drink")
    make_txn(day="2026-07-05", amount=1500.0, txn_type=TransactionType.debit,
             description="RENT PAYMENT", expense_category="housing")
    make_txn(day="2026-07-12", amount=900.0, txn_type=TransactionType.debit,
             description="WHOLE FOODS", expense_category="food_and_drink")

    metrics = _profile(make_txn.__self_session__, today=date(2026, 8, 1))["metrics"]
    payload = metrics["average_monthly_burn"]["payload"]
    series = {row["month"]: row for row in payload["monthly_series"]}

    assert series["2026-06"]["top_categories"] == [
        {"category": "housing", "display": "Housing", "amount": 1500.0},
        {"category": "food_and_drink", "display": "Food & Drink", "amount": 300.0},
    ]
    assert series["2026-07"]["top_categories"] == [
        {"category": "housing", "display": "Housing", "amount": 1500.0},
        {"category": "food_and_drink", "display": "Food & Drink", "amount": 900.0},
    ]
    assert series["2026-07"]["vs_prev_month_pct"] == 33.3  # (2400-1800)/1800


def test_average_monthly_income_confirmed_biweekly_stable(make_txn):
    for day in ("01", "15"):
        for m in ("05", "06", "07"):
            make_txn(day=f"2026-{m}-{day}", amount=2500.0, txn_type=TransactionType.credit,
                     description="CONTOSO PAYROLL DIRECT DEPOSIT",
                     income_confirmed=True, is_income_candidate=True, income_category="salary")

    metrics = _profile(make_txn.__self_session__)["metrics"]
    income = metrics["average_monthly_income"]
    assert income["status"] == "ok"
    payload = income["payload"]
    assert payload["used_income_fallback"] is False
    assert payload["income_3mo"] == 5000.0
    assert payload["income_6mo"] is None
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["cadence"] == "biweekly"
    assert payload["sources"][0]["stability"] == "stable"
    assert income["confidence_label"] == "high"


def test_average_monthly_income_falls_back_to_candidates(make_txn):
    make_txn(day="2026-07-20", amount=600.0, txn_type=TransactionType.credit,
             description="UNKNOWN DEPOSIT", is_income_candidate=True, income_confirmed=None,
             income_category="other")

    metrics = _profile(make_txn.__self_session__)["metrics"]
    income = metrics["average_monthly_income"]
    assert income["status"] == "ok"
    assert income["payload"]["used_income_fallback"] is True
    assert income["confidence"] == 0.0
    assert income["confidence_label"] == "low"


def test_fixed_vs_discretionary_splits_rent_from_dining(make_txn):
    # Dining amounts vary >10% month to month so they aren't also picked up as a
    # metric-1 recurring commitment (which would legitimately count as fixed too).
    dining_amounts = {"05": 300.0, "06": 350.0, "07": 280.0}
    for m in ("05", "06", "07"):
        make_txn(day=f"2026-{m}-01", amount=1500.0, txn_type=TransactionType.debit,
                 description="RENT PAYMENT", expense_category="housing")
        make_txn(day=f"2026-{m}-12", amount=dining_amounts[m], txn_type=TransactionType.debit,
                 description="CHIPOTLE", expense_category="food_and_drink")

    discretionary_avg = sum(dining_amounts.values()) / 3
    total_avg = 1500.0 + discretionary_avg

    metrics = _profile(make_txn.__self_session__)["metrics"]
    fixed = metrics["fixed_vs_discretionary"]
    assert fixed["status"] == "ok"
    payload = fixed["payload"]
    assert payload["fixed_monthly_avg"] == 1500.0
    assert round(payload["discretionary_monthly_avg"], 2) == round(discretionary_avg, 2)
    assert round(payload["fixed_pct"], 1) == round(1500 / total_avg * 100, 1)
    assert payload["burn_rate_floor"] == 1500.0
    assert len(payload["fixed_breakdown"]) == 1
    housing = payload["fixed_breakdown"][0]
    assert housing["group"] == "Housing"
    assert housing["category"] == "housing"
    assert housing["monthly_avg"] == 1500.0
    assert len(housing["transactions"]) == 3
    assert {t["amount"] for t in housing["transactions"]} == {1500.0}
    assert fixed["confidence_label"] == "high"


def test_fixed_vs_discretionary_does_not_flag_one_time_car_rental_as_fixed(make_txn):
    # "BUDGET RENT A CAR" is a one-time travel expense, but its description
    # contains the word "rent" — regression guard against a keyword-matching
    # false positive that isn't a detected recurring commitment.
    for m in ("05", "06", "07"):
        make_txn(day=f"2026-{m}-01", amount=1500.0, txn_type=TransactionType.debit,
                 description="RENT PAYMENT", expense_category="housing")
    make_txn(day="2026-07-15", amount=701.14, txn_type=TransactionType.debit,
             description="BUDGET RENT A CAR CALGARY", expense_category="travel")

    metrics = _profile(make_txn.__self_session__)["metrics"]
    payload = metrics["fixed_vs_discretionary"]["payload"]
    assert payload["fixed_monthly_avg"] == 1500.0
    assert len(payload["fixed_breakdown"]) == 1
    assert payload["fixed_breakdown"][0]["group"] == "Housing"
    assert payload["fixed_breakdown"][0]["monthly_avg"] == 1500.0
    assert round(payload["discretionary_monthly_avg"], 2) == round(701.14 / 3, 2)
    assert len(payload["discretionary_breakdown"]) == 1
    assert payload["discretionary_breakdown"][0]["group"] == "Travel"
    assert len(payload["discretionary_breakdown"][0]["transactions"]) == 1


def test_fixed_vs_discretionary_matches_committed_monthly_spend_commitment_set(make_txn):
    # "Fixed" must be exactly the transactions backing Committed Monthly Spend's
    # commitments — including a credit-card-payment commitment, which isn't
    # "spending" but is still counted as fixed there.
    for m in ("05", "06", "07"):
        make_txn(day=f"2026-{m}-08", amount=5000.0, txn_type=TransactionType.debit,
                 description="ACH Debit AMEX EPAYMENT", expense_category="credit_card_payment")
    # An extra, irregular payment to the same merchant that is NOT part of the
    # detected commitment cluster — must not be swept into "fixed" by merchant
    # name, and since credit_card_payment isn't "spending" it must not land in
    # "discretionary" either (it would double-count the card's own purchases).
    make_txn(day="2026-06-16", amount=2000.0, txn_type=TransactionType.debit,
             description="ACH Debit AMEX EPAYMENT", expense_category="credit_card_payment")

    profile = _profile(make_txn.__self_session__)
    committed = profile["metrics"]["committed_monthly_spend"]["payload"]
    fixed = profile["metrics"]["fixed_vs_discretionary"]["payload"]
    assert committed["committed_monthly_total"] == 5000.0
    assert fixed["fixed_monthly_avg"] == 5000.0
    assert fixed["discretionary_monthly_avg"] == 0.0
    assert len(fixed["fixed_breakdown"]) == 1
    ccp = fixed["fixed_breakdown"][0]
    assert ccp["group"] == "Credit Card Payment"
    assert ccp["monthly_avg"] == 5000.0
    assert len(ccp["transactions"]) == 3
    assert fixed["discretionary_breakdown"] == []


def test_savings_rate_aggregate_ratio_over_window(make_txn):
    for m in ("05", "06", "07"):
        make_txn(day=f"2026-{m}-01", amount=5000.0, txn_type=TransactionType.credit,
                 description="CONTOSO PAYROLL", income_confirmed=True, income_category="salary")
        make_txn(day=f"2026-{m}-15", amount=4000.0, txn_type=TransactionType.debit,
                 description="MONTHLY SPEND", expense_category="shopping")

    metrics = _profile(make_txn.__self_session__)["metrics"]
    savings = metrics["savings_rate"]
    assert savings["status"] == "ok"
    payload = savings["payload"]
    assert payload["window_income_total"] == 15000.0
    assert payload["window_spend_total"] == 12000.0
    assert payload["window_net_total"] == 3000.0
    assert round(payload["savings_rate_3mo"], 2) == 0.2
    assert savings["confidence_label"] == "high"


def test_fees_and_interest_zero_is_a_valid_result(make_txn):
    make_txn(day="2026-06-01", amount=50.0, txn_type=TransactionType.debit, description="GROCERY STORE", expense_category="food_and_drink")

    metrics = _profile(make_txn.__self_session__)["metrics"]
    fees = metrics["fees_and_interest"]
    assert fees["status"] == "ok"
    assert fees["payload"]["ytd_total"] == 0.0
    assert fees["payload"]["breakdown"] == []


def test_fees_and_interest_classifies_subtypes(make_txn):
    make_txn(day="2026-06-01", amount=35.0, txn_type=TransactionType.debit, description="OVERDRAFT FEE", expense_category="financial")
    make_txn(day="2026-06-02", amount=12.50, txn_type=TransactionType.debit, description="INTEREST CHARGE ON PURCHASES", expense_category="financial")
    make_txn(day="2026-06-03", amount=5.0, txn_type=TransactionType.debit, description="MONTHLY MAINTENANCE FEE", expense_category="financial")
    make_txn(day="2026-06-04", amount=95.0, txn_type=TransactionType.debit, description="ANNUAL FEE", expense_category="financial")

    metrics = _profile(make_txn.__self_session__)["metrics"]
    fees = metrics["fees_and_interest"]
    assert fees["status"] == "ok"
    payload = fees["payload"]
    assert payload["ytd_total"] == 147.5
    subtypes = {b["sub_type"]: b["ytd_total"] for b in payload["breakdown"]}
    assert subtypes == {"penalty_fees": 35.0, "interest": 12.5, "bank_fees": 5.0, "card_fees": 95.0}
