"""Daily per-user cap on /api/chat requests, to bound Anthropic API cost
exposure from any single user."""
from datetime import date

from sqlmodel import Session, select

from ..models.chat_usage import ChatUsage


class ChatUsageLimitExceeded(Exception):
    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(f"Daily chat limit of {limit} messages reached")


def check_and_record_usage(
    session: Session, user_id: int, limit: int, today: date | None = None
) -> int:
    """Raise ChatUsageLimitExceeded if the user has already hit `limit` chat
    requests today; otherwise record this request and return the new count.

    Recorded before the model call, since a request that reaches this point
    is about to incur API cost regardless of how it resolves.
    """
    effective_today = today or date.today()
    row = session.exec(
        select(ChatUsage).where(
            ChatUsage.user_id == user_id, ChatUsage.usage_date == effective_today
        )
    ).first()
    if row is None:
        row = ChatUsage(user_id=user_id, usage_date=effective_today, message_count=0)

    if row.message_count >= limit:
        raise ChatUsageLimitExceeded(limit)

    row.message_count += 1
    session.add(row)
    session.commit()
    return row.message_count
