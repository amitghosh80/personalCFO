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
    # Credit card payments — these appear as credits on card statements but are not income
    r"\bautopay\b",
    r"payment (thank you|received|processed|applied)",
    r"payment - thank you",
    r"(automatic|online|electronic|minimum) payment",
    r"thank you for.{0,20}payment",
    r"\bbill pay(ment)?\b",
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
    r"interest (paid|earned|credit)",
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

_GIG = [
    r"\bpaypal\b",
    r"\bvenmo\b",
    r"\bstripe\b",
    r"\bsquare\b",
    r"\bdoordash\b",
    r"\buber\b",
    r"\blyft\b",
    r"\bupwork\b",
    r"\bfiverr\b",
    r"\betsy\b",
    r"\bshopify\b",
    r"amazon marketplace",
    r"amazon seller",
    r"freelance",
    r"consulting fee",
    r"contractor pay",
]

# Threshold: large unexplained credits are flagged for user review
_LARGE_CREDIT_THRESHOLD = 500.0


def _matches_any(desc: str, patterns: list[str]) -> bool:
    return any(re.search(p, desc, re.IGNORECASE) for p in patterns)


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
