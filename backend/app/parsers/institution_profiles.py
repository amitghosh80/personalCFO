from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InstitutionProfile:
    name: str
    required_columns: frozenset  # all must be present for a match
    optional_columns: frozenset  # raise confidence score if present
    date_col: str
    description_col: str
    amount_col: Optional[str]       # single signed amount column
    debit_col: Optional[str]        # separate debit column
    credit_col: Optional[str]       # separate credit column
    date_format: str
    # For institutions where positive = charge (e.g. Amex), set True
    invert_sign: bool = False


PROFILES: list[InstitutionProfile] = [
    InstitutionProfile(
        name="Chase",
        required_columns=frozenset(["Transaction Date", "Description", "Amount"]),
        optional_columns=frozenset(["Post Date", "Category", "Type", "Memo"]),
        date_col="Transaction Date",
        description_col="Description",
        amount_col="Amount",
        debit_col=None,
        credit_col=None,
        date_format="%m/%d/%Y",
    ),
    InstitutionProfile(
        name="Bank of America",
        required_columns=frozenset(["Date", "Description", "Amount", "Running Bal."]),
        optional_columns=frozenset([]),
        date_col="Date",
        description_col="Description",
        amount_col="Amount",
        debit_col=None,
        credit_col=None,
        date_format="%m/%d/%Y",
    ),
    InstitutionProfile(
        name="Citi",
        required_columns=frozenset(["Date", "Description", "Debit", "Credit"]),
        optional_columns=frozenset(["Status"]),
        date_col="Date",
        description_col="Description",
        amount_col=None,
        debit_col="Debit",
        credit_col="Credit",
        date_format="%m/%d/%Y",
    ),
    InstitutionProfile(
        name="Capital One",
        required_columns=frozenset(["Transaction Date", "Description", "Debit", "Credit"]),
        optional_columns=frozenset(["Posted Date", "Card No.", "Category"]),
        date_col="Transaction Date",
        description_col="Description",
        amount_col=None,
        debit_col="Debit",
        credit_col="Credit",
        date_format="%Y-%m-%d",
    ),
    InstitutionProfile(
        name="American Express",
        required_columns=frozenset(["Date", "Description", "Amount"]),
        optional_columns=frozenset(["Extended Details", "Appears On Your Statement As", "Address", "Category"]),
        date_col="Date",
        description_col="Description",
        amount_col="Amount",
        debit_col=None,
        credit_col=None,
        date_format="%m/%d/%Y",
        invert_sign=True,  # Amex: positive = charge, negative = payment/credit
    ),
    InstitutionProfile(
        name="Wells Fargo",
        required_columns=frozenset(["Date", "Amount", "Description"]),
        optional_columns=frozenset(["Check Number"]),
        date_col="Date",
        description_col="Description",
        amount_col="Amount",
        debit_col=None,
        credit_col=None,
        date_format="%m/%d/%Y",
    ),
]


def detect_institution(columns: list[str]) -> tuple[Optional[InstitutionProfile], float]:
    col_set = {c.strip() for c in columns}
    best_profile: Optional[InstitutionProfile] = None
    best_score = 0.0

    for profile in PROFILES:
        required_matched = profile.required_columns & col_set
        if len(required_matched) < len(profile.required_columns):
            continue  # missing a required column — skip

        optional_score = (
            len(profile.optional_columns & col_set) / len(profile.optional_columns)
            if profile.optional_columns
            else 0.0
        )
        score = 0.7 + 0.3 * optional_score

        if score > best_score:
            best_score = score
            best_profile = profile

    return best_profile, best_score
