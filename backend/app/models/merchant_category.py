from sqlmodel import Field, SQLModel
from datetime import datetime
from typing import Optional


class MerchantCategoryCache(SQLModel, table=True):
    """Persistent cache of merchant → category decisions.

    Keyed by a normalized merchant string so repeat merchants (and re-imports)
    never re-hit the AI categorizer. Populated by both rule and AI results that
    resolve a previously uncategorized merchant.
    """

    merchant_key: str = Field(primary_key=True)
    primary: str
    subcategory: str
    source: str = Field(default="ai")  # "ai" | "rule"
    created_at: datetime = Field(default_factory=datetime.utcnow)
