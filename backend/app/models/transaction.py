from sqlmodel import Field, SQLModel
from datetime import date, datetime
from typing import Optional
from enum import Enum


class TransactionType(str, Enum):
    debit = "debit"
    credit = "credit"


class IncomeCategory(str, Enum):
    salary = "salary"
    freelance = "freelance"
    interest = "interest"
    rental = "rental"
    gig = "gig"
    other = "other"


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="app_user.id", index=True)
    import_job_id: str = Field(index=True)
    date: date
    description: bytes  # Fernet-encrypted
    amount: float
    transaction_type: TransactionType
    currency: str = Field(default="USD")
    account_last4: Optional[str] = Field(default=None)
    institution: Optional[str] = Field(default=None)
    source_file_hash: str = Field(index=True)

    is_income_candidate: bool = Field(default=False)
    income_category: Optional[str] = Field(default=None)  # IncomeCategory value
    income_confirmed: Optional[bool] = Field(default=None)  # None=unreviewed

    expense_category: Optional[str] = Field(default=None)       # primary taxonomy key
    expense_subcategory: Optional[str] = Field(default=None)    # detailed taxonomy key
    category_source: Optional[str] = Field(default=None)        # "rule" | "ai" | "user" | "fallback"
    category_confidence: Optional[float] = Field(default=None)  # 0.0–1.0
    confidence_label: Optional[str] = Field(default=None)       # "high" | "medium" | "low"

    is_ambiguous: bool = Field(default=False)
    ambiguity_reason: Optional[str] = Field(default=None)
    is_duplicate: bool = Field(default=False)

    # Cross-account transfer detection (F1). A "paired" transfer is excluded from
    # spending + income; an "unconfirmed" one is flagged for the user to confirm.
    is_transfer: bool = Field(default=False)
    transfer_status: Optional[str] = Field(default=None)   # "paired" | "unconfirmed"
    transfer_pair_id: Optional[int] = Field(default=None)  # the matched transaction's id

    created_at: datetime = Field(default_factory=datetime.utcnow)
