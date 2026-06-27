"""PRD success-metric guard: credit-card payments must never count as spending.

The metric is "CC payment double-count rate = 0%". CC bill payments on the
checking side must categorize as the non-spending `credit_card_payment` primary
so they're excluded from spending totals (otherwise they double-count against
the card's own imported purchases)."""
import pytest

from app.services.expense_categorizer import categorize_expense, is_spending

# Real-world checking-side CC payment descriptions across the 7 supported banks.
CC_PAYMENT_DESCRIPTIONS = [
    "ACH Debit AMEX EPAYMENT ER AM - ACH PMT",
    "Chase Credit Crd Autopay PPD ID: 4760039224",
    "AMEX EPAYMENT ACH PMT",
    "CITI AUTOPAY PAYMENT",
    "CITI CARD ONLINE PAYMENT",
    "CAPITAL ONE ONLINE PMT",
    "CAPITAL ONE CRD PYMT",
    "DISCOVER E-PYMT",
    "AMERICAN EXPRESS ACH PMT",
    "PAYMENT TO CHASE CARD ENDING IN 1234",
]


@pytest.mark.parametrize("desc", CC_PAYMENT_DESCRIPTIONS)
def test_cc_payment_is_non_spending(desc):
    primary, _sub, _source = categorize_expense(desc)
    assert primary == "credit_card_payment", f"{desc!r} → {primary} (expected credit_card_payment)"
    assert not is_spending(primary), f"{desc!r} leaked into spending as {primary}"
