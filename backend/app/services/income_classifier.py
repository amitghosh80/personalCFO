import re
from ..models.transaction import IncomeCategory, TransactionType

# Patterns that disqualify a credit from being income
_NOT_INCOME = [
    # Inter-account transfers
    r"transfer (from|to|between)",
    r"from (savings|checking|account)",
    r"to (savings|checking|account)",
    r"online transfer",
    r"internal transfer",
    r"account transfer",
    r"\bext\s+trnsfr\b",            # JPMorgan "Ext Trnsfr" = external own-account transfer
    # Credit card payments — these appear as credits on card statements but are not income
    r"\bautopay\b",
    r"payment (thank you|received|processed|applied)",
    r"payment\s*-\s*thank you",
    r"(automatic|online|electronic|minimum) payment",
    r"thank you for.{0,20}payment",
    r"\bbill pay(ment)?\b",
    # ACH debits / outgoing payments (some PDF parsers show positive amounts for debits)
    r"\bach (debit|pmt)\b",
    r"\bloan pay(mt|ment)\b",
    # Explicit outflows that should never appear as income even if sign is wrong
    r"\batm withdrawal\b",
    r"\bpos transaction\b",
    # Statement metadata mistakenly parsed as transactions
    r"\bstarting balance\b",
    r"\bopening balance\b",
    # Reversals / adjustments
    r"\brefund\b",
    r"\breturn\b",
    r"\breversal\b",
    r"credit (adjustment|adj)",
    # Rewards / perks (not earned income)
    r"cash ?back",
    r"\breward(s)?\b",
    # Deposits that aren't income
    r"atm deposit",
    r"mobile deposit",
]

# Patterns for credit transactions that should be hidden from the income review UI
# entirely — not just excluded from income candidates, but invisible to the user.
# These are either accounting artifacts (CC payment confirmations) or outflows
# that were misclassified as credits due to sign-convention bugs.
_EXCLUDE_FROM_REVIEW = [
    # CC payment acknowledgment lines
    r"payment\s+(thank\s+you|received|processed|applied)",
    r"payment\s*-\s*thank\s+you",
    r"thank\s+you.{0,25}payment",
    r"\bautopay\b",
    r"(automatic|online|electronic|minimum)\s+payment",
    r"\bbill\s+pay(ment)?\b",
    # Explicit outflows (appear as credits only when sign convention is misread)
    r"\bach\s+debit\b",
    r"\batm\s+withdrawal\b",
    r"\bpos\s+transaction\b",
    r"\bloan\s+pay(mt|ment)\b",
    # Statement metadata
    r"\bstarting\s+balance\b",
    r"\bopening\s+balance\b",
]

_SALARY = [
    r"payroll",
    r"direct dep(osit)?",
    r"\bsalary\b",
    r"\bwages?\b",
    r"ach credit.{0,40}(payroll|salary|wages?|direct dep)",
    r"\bemployer\b",
    r"\bcompensation\b",
    r"\bpay(check)?\b",
    r"biweekly",
    r"bi-weekly",
    r"semi-?monthly",
]

_INTEREST = [
    r"interest (paid|earned|credit|payment)",
    r"\binterest\s+payment\b",
    r"\bdividend\b",
    r"\bapy\b",
    r"savings interest",
    r"investment income",
    r"capital gain",
]

_RENTAL = [
    r"rent (payment|received|income)",
    r"rental income",
    r"\blease payment\b",
    r"\btenant\b",
    r"property mgmt",
    r"airbnb",
    r"vrbo",
]

# Freelance / contract income — explicit contract signals only. Personal P2P
# rails (PayPal, Venmo, Zelle) deliberately stay under _GIG: in the user-reviewed
# ground truth those deposits were classified as gig, and the description alone
# can't distinguish a business client from a personal payment.
_FREELANCE = [
    r"\bstripe\b",
    r"\bfreelance\b",
    r"\bconsult(ing|ant)\b",
    r"\bcontractor\b",
    r"contract\s*(pay|pmt|payment)",
    r"\binvoice\b",
    r"\b1099\b",
]

_GIG = [
    r"\bpaypal\b",
    r"\bvenmo\b",
    r"\bsquare\b",
    r"\bdoordash\b",
    r"\bgrubhub\b",
    r"\binstacart\b",
    r"\buber\b",
    r"\blyft\b",
    r"\bupwork\b",
    r"\bfiverr\b",
    r"\betsy\b",
    r"\bshopify\b",
    r"amazon marketplace",
    r"amazon seller",
]

# Threshold: large unexplained credits are flagged for user review.
# PRD F2 / Open Question Q3 default for "Other Income".
_LARGE_CREDIT_THRESHOLD = 200.0


def _matches_any(desc: str, patterns: list[str]) -> bool:
    return any(re.search(p, desc, re.IGNORECASE) for p in patterns)


def exclude_from_review(description: str) -> bool:
    """True when a credit transaction should be hidden from the income review UI.

    Used to suppress CC payment confirmations and outflows that appear as credits
    due to sign-convention misreads — neither are useful to show for income review.
    """
    return _matches_any(description, _EXCLUDE_FROM_REVIEW)


def classify_income(
    description: str, amount: float, txn_type: TransactionType
) -> tuple[bool, IncomeCategory | None]:
    """Return (is_income_candidate, category). category is None if not a candidate."""
    if txn_type != TransactionType.credit or amount <= 0:
        return False, None

    if _matches_any(description, _NOT_INCOME):
        return False, None

    if _matches_any(description, _SALARY):
        return True, IncomeCategory.salary

    if _matches_any(description, _FREELANCE):
        return True, IncomeCategory.freelance

    if _matches_any(description, _INTEREST):
        return True, IncomeCategory.interest

    if _matches_any(description, _RENTAL):
        return True, IncomeCategory.rental

    if _matches_any(description, _GIG):
        return True, IncomeCategory.gig

    # Flag large unmatched credits for user review
    if amount >= _LARGE_CREDIT_THRESHOLD:
        return True, IncomeCategory.other

    return False, None
