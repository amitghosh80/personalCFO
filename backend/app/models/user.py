from sqlmodel import Field, SQLModel
from datetime import datetime
from typing import Optional


class User(SQLModel, table=True):
    __tablename__ = "app_user"  # "user" is a reserved word in most SQL dialects

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    # None for accounts created via Google Sign-In that never set a password.
    hashed_password: Optional[str] = Field(default=None)
    google_sub: Optional[str] = Field(default=None, unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Set when the user picks "Import a statement" from the first-run choice
    # screen, so it isn't shown again on later /app visits (AMI-66).
    vitals_prompt_dismissed_at: Optional[datetime] = Field(default=None)
