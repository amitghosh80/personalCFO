"""Unit tests for pdf_parser internals — regression coverage for three bugs
found by the statement-parse-tester against real ground-truth statements:

1. Sign inversion missed when the payment-acknowledgment line reads
   "AUTOMATIC PAYMENT - THANK YOU" (punctuation between "payment" and "thank you").
2. First Tech FCU statements misdetected as Chase because the page-1 domain is
   "firsttechfed.com" but the keyword list only had "firsttech.com".
3. Amex foreign-currency rows ("<foreign> $<usd>") stored the foreign amount
   instead of the USD charge.

These target pure functions, so they need no external PDF files.
"""
from app.parsers.pdf_parser import (
    _needs_pdf_sign_inversion,
    _detect_institution,
    _parse_text_lines,
)
from app.models.transaction import TransactionType


# ── Bug 1: sign inversion with punctuated payment-ack line ─────────────────────

def test_sign_inversion_detected_for_hyphenated_payment_thank_you():
    text = "06/07 AUTOMATIC PAYMENT - THANK YOU -35.00"
    assert _needs_pdf_sign_inversion(None, text) is True


def test_no_inversion_without_negative_payment_ack():
    # A plain checking line with a positive deposit must NOT trigger inversion.
    text = "05/01 PAYROLL DEPOSIT 1,200.00 5,340.00"
    assert _needs_pdf_sign_inversion(None, text) is False


# ── Bug 2: First Tech domain detection ─────────────────────────────────────────

def test_detects_first_tech_from_firsttechfed_domain():
    # Page-1 text carries the domain with "fed", plus a Chase mention in a
    # transaction line that must NOT win.
    text = (
        "P.O. Box 2100 Beaverton, OR 97075-2100 855.855.8805 firsttechfed.com\n"
        "05/01 ACH Deposit JPMorgan Chase - Ext Trnsfr 1,000.00"
    )
    assert _detect_institution(text) == "First Tech"


# ── Bug 3: Amex FX rows use the USD ($-prefixed) amount ────────────────────────

def test_fx_line_uses_usd_amount_not_foreign():
    line = "05/06/26 PTI*MORAINELAKE BUS BANFF 374.74 $275.50"
    result = _parse_text_lines(line, invert_sign=True)
    txns = result["transactions"]
    assert len(txns) == 1
    assert txns[0]["amount"] == 275.50
    assert txns[0]["transaction_type"] == TransactionType.debit


def test_running_balance_line_still_uses_transaction_amount():
    # Guard: when neither amount is $-prefixed, keep the running-balance
    # heuristic (transaction amount is second-to-last).
    line = "05/01 PAYROLL DEPOSIT 1,200.00 5,340.00"
    result = _parse_text_lines(line, invert_sign=False)
    txns = result["transactions"]
    assert len(txns) == 1
    assert txns[0]["amount"] == 1200.00
    assert txns[0]["transaction_type"] == TransactionType.credit
