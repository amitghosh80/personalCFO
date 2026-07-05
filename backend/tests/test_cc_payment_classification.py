"""AMI-13 / AMI-14: credit-card bill payments must be classified as non-spending
transfers on BOTH sides of the ledger.

- AMI-13 (bank/checking side): a debit that pays a card bill → credit_card_payment,
  never an expense category. Bank of America was previously missed.
- AMI-14 (card side): an incoming-payment credit ("PAYMENT THANK YOU", etc.) →
  explicitly tagged credit_card_payment (a non-spending category), not left
  uncategorized.
"""
from app.services.expense_categorizer import categorize_expense, is_spending
from app.services.income_classifier import credit_expense_category


# ── AMI-13: bank-side CC bill payments (debits) ────────────────────────────────

def test_bank_of_america_creditcard_payment_is_non_spending():
    primary, _sub, _src = categorize_expense("BANK OF AMERICA CREDITCARD 1234 PAYMENT")
    assert primary == "credit_card_payment"
    assert is_spending(primary) is False


def test_existing_cc_payment_patterns_still_detected():
    for desc in [
        "CHASE CREDIT CRD AUTOPAY",
        "AMEX EPAYMENT ACH PMT",
        "CITI AUTOPAY",
        "CAPITAL ONE ONLINE PMT",
        "DISCOVER E-PAYMENT",
    ]:
        primary, _sub, _src = categorize_expense(desc)
        assert primary == "credit_card_payment", f"{desc!r} -> {primary}"


# ── AMI-14: card-side incoming-payment credits ────────────────────────────────

def test_card_payment_ack_credit_tagged_non_spending():
    for desc in [
        "AUTOMATIC PAYMENT - THANK YOU",
        "PAYMENT THANK YOU",
        "ONLINE PAYMENT",
        "PAYMENT RECEIVED",
    ]:
        cat = credit_expense_category(desc)
        assert cat == "credit_card_payment", f"{desc!r} -> {cat}"
        assert is_spending(cat) is False


def test_real_income_credit_not_tagged_as_payment():
    for desc in ["GUSTO PAYROLL", "ACME CORP DIRECT DEPOSIT"]:
        assert credit_expense_category(desc) is None, desc
