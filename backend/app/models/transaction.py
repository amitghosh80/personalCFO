from sqlmodel import Field, SQLModel
from datetime import date, datetime
from typing import Optional
from enum import Enum


class TransactionType(str, Enum):
    debit = "debit"
    credit = "credit"


class IncomeCategory(str, Enum):
    salary = "salary"
    interest = "interest"
    rental = "rental"
    gig = "gig"
    other = "other"


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
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

    is_ambiguous: bool = Field(default=False)
    ambiguity_reason: Optional[str] = Field(default=None)
    is_duplicate: bool = Field(default=False)

    created_at: datetime = Field(default_factory=datetime.utcnow)
