"""Fast unit tests for income classification (no PDF fixtures required).

Complements test_income_classification.py (which parses real PDFs) by pinning
the classifier's category logic directly — especially the Freelance/Gig split,
where PayPal/Venmo/Zelle deliberately remain `gig` to match the user-reviewed
ground truth, while explicit contract signals map to the new `freelance` type.
"""
from app.services.income_classifier import classify_income
from app.models.transaction import IncomeCategory, TransactionType

CREDIT = TransactionType.credit
DEBIT = TransactionType.debit


def _cat(desc: str, amount: float = 1000.0):
    is_cand, cat = classify_income(desc, amount, CREDIT)
    return is_cand, cat


# ── Freelance / contract: explicit signals only ───────────────────────────────

def test_stripe_transfer_is_freelance():
    assert _cat("STRIPE TRANSFER") == (True, IncomeCategory.freelance)


def test_consulting_is_freelance():
    assert _cat("ACME LLC CONSULTING PAYMENT") == (True, IncomeCategory.freelance)


def test_invoice_is_freelance():
    assert _cat("INVOICE 1042 PAID") == (True, IncomeCategory.freelance)


def test_1099_is_freelance():
    assert _cat("CLIENT 1099 CONTRACT PMT") == (True, IncomeCategory.freelance)


# ── Personal P2P rails stay gig (preserves reviewed ground truth) ──────────────

def test_paypal_stays_gig():
    assert _cat("PAYPAL TRANSFER", 576.24) == (True, IncomeCategory.gig)


def test_venmo_stays_gig():
    assert _cat("VENMO CASHOUT", 2450.00) == (True, IncomeCategory.gig)


# ── Other types unaffected ─────────────────────────────────────────────────────

def test_payroll_is_salary():
    assert _cat("ADP PAYROLL") == (True, IncomeCategory.salary)


def test_interest_is_interest():
    assert _cat("SAVINGS INTEREST PAYMENT", 12.50) == (True, IncomeCategory.interest)


# ── $200 "Other Income" floor (PRD Q3 default) ─────────────────────────────────

def test_unmatched_credit_at_floor_is_other():
    assert _cat("RANDOM ACH CREDIT XYZ", 200.00) == (True, IncomeCategory.other)


def test_unmatched_credit_below_floor_not_candidate():
    assert _cat("RANDOM ACH CREDIT XYZ", 199.99) == (False, None)


def test_debit_is_never_income():
    assert classify_income("STRIPE TRANSFER", 1000.0, DEBIT) == (False, None)
