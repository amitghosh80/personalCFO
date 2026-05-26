"""
Income / Expense Classification Regression Test Suite
======================================================
Ground truth: user-reviewed feedback from income-review-e7add718.xlsx (May 2026).
Eight real PDFs cover three account types: Chase checking, Chase CC, Amex CC,
and First Tech Federal Credit Union checking.

Run from backend/:
    pytest tests/test_income_classification.py -v
    pytest tests/test_income_classification.py -v --tb=short     # brief tracebacks
    pytest tests/test_income_classification.py -v -k "FirstTech" # one class

Override the PDF folder:
    set INCOME_TEST_PDF_DIR=C:\\some\\other\\path
    pytest tests/test_income_classification.py -v
"""
import os
import pytest
from pathlib import Path

from app.parsers.pdf_parser import parse_pdf
from app.services.income_classifier import classify_income, exclude_from_review
from app.models.transaction import IncomeCategory, TransactionType

# ── Configuration ─────────────────────────────────────────────────────────────

PDF_DIR = Path(os.getenv("INCOME_TEST_PDF_DIR", r"C:\Users\amitg\Downloads"))


# ── Core parse + classify helper ──────────────────────────────────────────────

def _load_and_parse(filename: str):
    """Parse a PDF and annotate every transaction with classification results.

    Returns (institution: str | None, transactions: list[dict]).
    Skips the test if the file is not found.
    """
    path = PDF_DIR / filename
    if not path.exists():
        pytest.skip(f"PDF not found: {path}")

    result = parse_pdf(path.read_bytes())
    annotated = []
    for raw in result["transactions"]:
        is_cand, cat = classify_income(
            raw["description"], raw["amount"], raw["transaction_type"]
        )
        annotated.append({
            **raw,
            "is_income_candidate": is_cand,
            "income_category": cat,
            # True when the transaction should be hidden from the income-review UI
            "hidden": (not is_cand) and exclude_from_review(raw["description"]),
        })
    return result.get("institution"), annotated


def _find(txns: list[dict], fragment: str, amount: float = None) -> list[dict]:
    """Return transactions whose description contains `fragment` (case-insensitive).
    Optionally filter by amount within $0.02.
    """
    hits = [t for t in txns if fragment.lower() in t["description"].lower()]
    if amount is not None:
        hits = [t for t in hits if abs(t["amount"] - amount) < 0.02]
    return hits


# ── Assertion helpers ─────────────────────────────────────────────────────────

def assert_income_candidate(txns, fragment, amount=None, category: str = None):
    """Assert that matching transaction(s) are classified as income candidates."""
    hits = _find(txns, fragment, amount)
    tag = f"'{fragment}'" + (f" ${amount}" if amount else "")
    assert hits, f"[MISSING] No transaction found for {tag}"
    for t in hits:
        assert t["is_income_candidate"], (
            f"[NOT INCOME] Expected income candidate: '{t['description']}' ${t['amount']:.2f}"
        )
        if category:
            got = t["income_category"]
            assert got == category, (
                f"[WRONG CATEGORY] {tag}: expected '{category}', got '{got}'"
            )


def assert_not_income_visible(txns, fragment, amount=None):
    """Assert credit is visible in Other Credits — not income candidate, not hidden."""
    hits = _find(txns, fragment, amount)
    tag = f"'{fragment}'" + (f" ${amount}" if amount else "")
    assert hits, f"[MISSING] No transaction found for {tag}"
    for t in hits:
        assert not t["is_income_candidate"], (
            f"[FALSE INCOME] Should NOT be income candidate: '{t['description']}' ${t['amount']:.2f}"
        )
        assert not t["hidden"], (
            f"[WRONGLY HIDDEN] Should be visible in Other Credits: '{t['description']}' ${t['amount']:.2f}"
        )


def assert_hidden_from_review(txns, fragment, amount=None):
    """Assert credit is hidden from the income-review UI entirely.

    Used for CC payment confirmations, ACH debits, and other definite non-income
    that would only confuse the user if shown.
    """
    hits = _find(txns, fragment, amount)
    tag = f"'{fragment}'" + (f" ${amount}" if amount else "")
    assert hits, f"[MISSING] No transaction found for {tag}"
    for t in hits:
        assert not t["is_income_candidate"], (
            f"[FALSE INCOME] Should not be income: '{t['description']}'"
        )
        assert t["hidden"], (
            f"[NOT HIDDEN] Should be hidden from review: '{t['description']}' ${t['amount']:.2f}"
        )


def assert_is_debit(txns, fragment):
    """Assert all matching transactions are debits — sign-inversion regression guard."""
    hits = _find(txns, fragment)
    assert hits, f"[MISSING] No transaction found for '{fragment}'"
    for t in hits:
        assert t["transaction_type"] == TransactionType.debit, (
            f"[SIGN BUG] Parsed as CREDIT (should be debit): "
            f"'{t['description']}' ${t['amount']:.2f}"
        )


def assert_zero_income_candidates(txns, context=""):
    """Assert that no transaction is an income candidate."""
    candidates = [t for t in txns if t["is_income_candidate"]]
    assert not candidates, (
        f"[FALSE INCOME]{' ' + context if context else ''} "
        f"Expected 0 income candidates, got {len(candidates)}:\n"
        + "\n".join(f"  '{t['description']}' ${t['amount']:.2f}" for t in candidates)
    )


def assert_no_expense_as_credit(txns, expense_keywords: list[str], context=""):
    """Assert that none of the known expense-description keywords appear as credits.

    This guards against the sign-inversion bug where checking-account debits
    (loan payments, ATM withdrawals, POS purchases) were flipped to credits.
    """
    for kw in expense_keywords:
        false_credits = [
            t for t in txns
            if kw.lower() in t["description"].lower()
            and t["transaction_type"] == TransactionType.credit
        ]
        assert not false_credits, (
            f"[SIGN BUG]{' ' + context if context else ''} "
            f"Expense keyword '{kw}' found in credit transactions:\n"
            + "\n".join(f"  '{t['description']}' ${t['amount']:.2f}" for t in false_credits)
        )


# ── Chase Checking – Feb 2026 ─────────────────────────────────────────────────

class TestChaseCheckingFeb:
    """Chase checking account – Feb 2026 (20260227-statements-3278-.pdf)"""

    @pytest.fixture(scope="class")
    def data(self):
        return _load_and_parse("20260227-statements-3278-.pdf")

    def test_institution(self, data):
        institution, _ = data
        assert institution == "Chase"

    def test_zelle_from_brian_heredia_is_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "Zelle Payment From Brian Heredia", 4145.00)

    def test_venmo_cashout_is_gig_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "Venmo Cashout", 2450.00, category="gig")

    def test_microsoft_edipayment_is_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "Microsoft Edipayment", 1500.00)

    def test_interest_payment_classified_as_interest(self, data):
        _, txns = data
        assert_income_candidate(txns, "Interest Payment", 0.03, category="interest")

    def test_atm_surcharge_refund_visible_in_other_credits(self, data):
        """Small fee refund — not auto-income but should be shown for user to decide."""
        _, txns = data
        assert_not_income_visible(txns, "ATM Surcharge Refund")


# ── Chase Checking – Mar 2026 ─────────────────────────────────────────────────

class TestChaseCheckingMar:
    """Chase checking account – Mar 2026 (20260331-statements-3278-.pdf)"""

    @pytest.fixture(scope="class")
    def data(self):
        return _load_and_parse("20260331-statements-3278-.pdf")

    def test_institution(self, data):
        institution, _ = data
        assert institution == "Chase"

    def test_zelle_from_brian_heredia_is_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "Zelle Payment From Brian Heredia", 4145.00)

    def test_zelle_from_petro_kushnirenko_is_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "Zelle Payment From Petro Kushnirenko", 2900.00)

    def test_venmo_real_time_transfer_is_gig_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "From: Venmo", 2425.00, category="gig")

    def test_microsoft_edipayment_is_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "Microsoft Edipayment", 1500.00)

    def test_interest_payment_classified_as_interest(self, data):
        _, txns = data
        assert_income_candidate(txns, "Interest Payment", category="interest")


# ── Chase Credit Card – Feb/Mar 2026 ─────────────────────────────────────────

class TestChaseCreditCardFebMar:
    """Chase credit card – Feb/Mar 2026 (20260310-statements-1874-.pdf)

    Sign convention: positive = charge, payment lines are negative.
    After inversion: charges become debits, payments become credits.
    CC payments must be hidden from review; no income candidates expected.
    """

    @pytest.fixture(scope="class")
    def data(self):
        return _load_and_parse("20260310-statements-1874-.pdf")

    def test_institution(self, data):
        institution, _ = data
        assert institution == "Chase"

    def test_doordash_dashpass_is_debit(self, data):
        """Regression: DoorDash charge was appearing as a credit/income before sign fix."""
        _, txns = data
        assert_is_debit(txns, "DOORDASHDASHPASS")

    def test_payment_thank_you_mobile_is_hidden(self, data):
        """CC payment confirmation must not appear in income review UI."""
        _, txns = data
        assert_hidden_from_review(txns, "Payment Thank You-Mobile", 3150.00)

    def test_zero_income_candidates(self, data):
        _, txns = data
        assert_zero_income_candidates(txns, context="Chase CC Feb/Mar")


# ── Chase Credit Card – Mar/Apr 2026 ─────────────────────────────────────────

class TestChaseCreditCardMarApr:
    """Chase credit card – Mar/Apr 2026 (20260410-statements-1874-.pdf)"""

    @pytest.fixture(scope="class")
    def data(self):
        return _load_and_parse("20260410-statements-1874-.pdf")

    def test_payment_thank_you_web_is_hidden(self, data):
        _, txns = data
        assert_hidden_from_review(txns, "Payment Thank You - Web", 1140.84)

    def test_costco_return_visible_in_other_credits(self, data):
        """Merchant return/credit on CC — ambiguous, show for user to decide."""
        _, txns = data
        assert_not_income_visible(txns, "COSTCO WHSE", 18.33)

    def test_amazon_return_visible_in_other_credits(self, data):
        _, txns = data
        assert_not_income_visible(txns, "AMAZON MKTPLACE PMTS", 13.38)

    def test_zero_income_candidates(self, data):
        _, txns = data
        assert_zero_income_candidates(txns, context="Chase CC Mar/Apr")


# ── American Express – Feb/Mar 2026 ──────────────────────────────────────────

class TestAmexFebMar:
    """Amex credit card – Feb/Mar 2026 (2026-03-10.pdf)

    Sign convention: positive = charge (invert_sign=True from profile).
    Payments and card credits are negative → become positive after inversion.
    CC payment-ack lines must be hidden; statement credits visible.
    """

    @pytest.fixture(scope="class")
    def data(self):
        return _load_and_parse("2026-03-10.pdf")

    def test_institution(self, data):
        institution, _ = data
        assert institution == "American Express"

    def test_online_payment_thank_you_is_hidden(self, data):
        _, txns = data
        assert_hidden_from_review(txns, "ONLINE PAYMENT - THANK YOU")

    def test_mobile_payment_thank_you_is_hidden(self, data):
        _, txns = data
        assert_hidden_from_review(txns, "MOBILE PAYMENT - THANK YOU")

    def test_amex_resy_credit_visible_in_other_credits(self, data):
        """Card benefit credit — user confirmed as income, must be shown for review."""
        _, txns = data
        assert_not_income_visible(txns, "AMEX RESY CREDIT", 20.00)

    def test_amex_rideshare_credit_visible_in_other_credits(self, data):
        _, txns = data
        assert_not_income_visible(txns, "AMEX RIDESHARE CREDIT", 10.00)

    def test_zero_income_candidates(self, data):
        _, txns = data
        assert_zero_income_candidates(txns, context="Amex Feb/Mar")


# ── American Express – Mar/Apr 2026 ──────────────────────────────────────────

class TestAmexMarApr:
    """Amex credit card – Mar/Apr 2026 (2026-04-09.pdf)"""

    @pytest.fixture(scope="class")
    def data(self):
        return _load_and_parse("2026-04-09.pdf")

    def test_online_payment_thank_you_is_hidden(self, data):
        _, txns = data
        assert_hidden_from_review(txns, "ONLINE PAYMENT - THANK YOU")

    def test_amex_resy_credit_visible(self, data):
        _, txns = data
        assert_not_income_visible(txns, "AMEX RESY CREDIT")

    def test_amex_rideshare_credit_visible(self, data):
        _, txns = data
        assert_not_income_visible(txns, "AMEX RIDESHARE CREDIT")

    def test_zero_income_candidates(self, data):
        _, txns = data
        assert_zero_income_candidates(txns, context="Amex Mar/Apr")


# ── First Tech Checking – Feb 2026 ───────────────────────────────────────────

class TestFirstTechFeb:
    """First Tech Federal Credit Union checking – Feb 2026 (GetDocument (7).pdf)

    REGRESSION RISK: this statement contains "JPMorgan Chase" in an ACH deposit
    description, which historically caused misdetection as Chase. As long as
    invert_sign is NOT applied, parsing is correct regardless of institution label.
    """

    @pytest.fixture(scope="class")
    def data(self):
        return _load_and_parse("GetDocument (7).pdf")

    def test_institution_is_not_amex(self, data):
        """Critical: Amex detection would apply invert_sign=True and corrupt all signs."""
        institution, _ = data
        assert institution != "American Express", (
            "First Tech Feb misdetected as American Express — "
            "invert_sign will flip all debits to credits"
        )

    def test_microsoft_edipayment_is_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "ACH Deposit MICROSOFT - EDIPAYMENT")

    def test_amit_ghosh_m2m_is_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "ACH Deposit AMIT GHOSH M2M", 5000.00)

    def test_paypal_transfer_is_gig_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "ACH Deposit PAYPAL TRANSFER", 576.24, category="gig")

    def test_deposit_transfer_from_own_account_visible_not_income(self, data):
        """Inter-account transfer: should show in Other Credits (user decides)."""
        _, txns = data
        assert_not_income_visible(txns, "Deposit Transfer From", 2500.00)

    def test_ext_trnsfr_jpmorgan_not_income_candidate(self, data):
        """JPMorgan 'Ext Trnsfr' = own-account external transfer, not income."""
        _, txns = data
        hits = _find(txns, "Ext Trnsfr", 1000.00)
        assert hits, "Ext Trnsfr $1,000 transaction not found"
        for t in hits:
            assert not t["is_income_candidate"], (
                f"[FALSE INCOME] Ext Trnsfr classified as income: '{t['description']}'"
            )

    # ── Sign-convention regression guards ─────────────────────────────────────

    def test_amex_epayment_is_debit(self, data):
        """Previously inverted to a credit due to Amex misdetection of First Tech."""
        _, txns = data
        assert_is_debit(txns, "ACH Debit AMEX EPAYMENT")

    def test_boeing_loan_payment_is_debit(self, data):
        _, txns = data
        assert_is_debit(txns, "BOEING EMP CR U")

    def test_atm_withdrawal_is_debit(self, data):
        _, txns = data
        assert_is_debit(txns, "ATM Withdrawal")

    def test_no_expense_keywords_appear_as_credits(self, data):
        """Catch-all: none of these expense descriptors should ever be a credit."""
        _, txns = data
        assert_no_expense_as_credit(txns, [
            "ach debit", "atm withdrawal", "pos transaction", "loan paymt",
            "bmwfs pymt", "webpayment", "app",
        ], context="First Tech Feb")


# ── First Tech Checking – Mar 2026 ───────────────────────────────────────────

class TestFirstTechMar:
    """First Tech Federal Credit Union checking – Mar 2026 (GetDocument (6).pdf)

    REGRESSION RISK: this statement contains "AMEX EPAYMENT" in transaction
    descriptions, which historically caused misdetection as American Express.
    That applied invert_sign=True and flipped 14+ expense debits into credits,
    flooding the income review with loan payments, utilities, and POS purchases.
    """

    @pytest.fixture(scope="class")
    def data(self):
        return _load_and_parse("GetDocument (6).pdf")

    def test_institution_is_not_amex(self, data):
        """THE critical regression: Amex detection inverts all signs, corrupting data."""
        institution, _ = data
        assert institution != "American Express", (
            "First Tech Mar misdetected as American Express — "
            "this will flip all debits to credits and flood income review with expenses"
        )

    def test_microsoft_edipayment_is_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "ACH Deposit MICROSOFT - EDIPAYMENT")

    def test_amit_ghosh_m2m_is_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "ACH Deposit AMIT GHOSH M2M")

    def test_morgan_stanley_deposit_is_income(self, data):
        _, txns = data
        assert_income_candidate(txns, "Morgan Stanley")

    def test_deposit_transfer_from_visible_not_income(self, data):
        _, txns = data
        assert_not_income_visible(txns, "Deposit Transfer From")

    # ── Sign-convention regression guards ─────────────────────────────────────

    def test_amex_epayment_is_debit(self, data):
        """Was inverted to credit when First Tech was misdetected as American Express."""
        _, txns = data
        assert_is_debit(txns, "AMEX EPAYMENT")

    def test_boeing_loan_payment_is_debit(self, data):
        _, txns = data
        assert_is_debit(txns, "BOEING EMP CR U")

    def test_cal_bank_loan_is_debit(self, data):
        _, txns = data
        assert_is_debit(txns, "CAL BANK TRUST")

    def test_atm_withdrawal_is_debit(self, data):
        _, txns = data
        assert_is_debit(txns, "ATM Withdrawal")

    def test_dominos_pos_is_debit(self, data):
        _, txns = data
        assert_is_debit(txns, "DOMINO")

    def test_comcast_utility_is_debit(self, data):
        _, txns = data
        assert_is_debit(txns, "COMCAST-XFINITY")

    def test_bmw_loan_is_debit(self, data):
        _, txns = data
        assert_is_debit(txns, "BMW BANK")

    def test_no_expense_keywords_appear_as_credits(self, data):
        """Catch-all guard against the 14-transaction sign-inversion bug."""
        _, txns = data
        assert_no_expense_as_credit(txns, [
            "ach debit", "atm withdrawal", "pos transaction", "loan paymt",
            "bmwfs pymt", "webpayment", "premium", "cable svcs", "utility",
        ], context="First Tech Mar")
