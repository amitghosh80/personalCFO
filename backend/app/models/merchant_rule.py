from sqlmodel import Field, SQLModel
from datetime import datetime
from typing import Optional


class MerchantRule(SQLModel, table=True):
    """A user-defined categorization rule created from a manual correction.

    When a user re-categorizes a transaction and opts to "apply to all future
    transactions from this merchant", a rule is stored here. Rules are applied
    during import *before* the AI categorizer, so a corrected merchant is never
    re-sent to the model. ``merchant_pattern`` is a normalized merchant key
    matched case-insensitively as a substring of the transaction description.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="app_user.id", index=True)
    merchant_pattern: str = Field(index=True)
    primary: str
    subcategory: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    match_count: int = Field(default=0)
