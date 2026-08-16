from sqlmodel import Field, SQLModel
from datetime import datetime
from typing import Optional


class PasswordResetToken(SQLModel, table=True):
    """A single-use, time-limited token for the forgot-password flow.

    Only a SHA-256 hash of the token is stored, so a database leak alone
    can't be used to reset an account (the raw token only ever travels in
    the emailed link).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="app_user.id", index=True)
    token_hash: str = Field(index=True, unique=True)
    expires_at: datetime
    used_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
