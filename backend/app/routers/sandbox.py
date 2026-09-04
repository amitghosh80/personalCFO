"""Sandbox mode (supporting feature, not the primary CTA): a fictional demo
persona ("Jordan") that lets an anonymous visitor click through the Insight
Feed, Financial Profile, and chat with realistic-looking data, answering
"what will I get if I import?" without requiring signup. Deliberately has NO
`get_current_user` dependency anywhere in this file — every handler resolves
the demo user id internally and never accepts a client-supplied user id."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from ..config import get_settings
from ..database import get_session
from ..models.user import User
from ..rate_limit import limiter
from ..services.analytics import data_coverage, starter_questions
from ..services.chat_service import answer_question
from ..services.chat_usage import ChatUsageLimitExceeded, check_and_record_usage
from ..models.transaction import Transaction
from ..routers.transactions import _serialize
from ..services.demo_seed import DEMO_USER_EMAIL
from ..services.insight_engine import latest_ledger_insights
from ..services.profile_engine import get_financial_profile

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])
logger = logging.getLogger("personalcfo.sandbox")

_demo_user_id_cache: int | None = None


def _get_demo_user_id(session: Session) -> int:
    global _demo_user_id_cache
    if _demo_user_id_cache is not None:
        return _demo_user_id_cache
    user = session.exec(select(User).where(User.email == DEMO_USER_EMAIL)).first()
    if user is None:
        # Only reachable if the startup seed hasn't run yet (e.g. first
        # request racing app startup) — fail loudly rather than silently
        # resolving to a wrong/empty account.
        raise HTTPException(status_code=503, detail="Sandbox data is not ready yet — try again shortly")
    _demo_user_id_cache = user.id
    return user.id


class SandboxChatRequest(BaseModel):
    question: str
    history: list[dict] = []


@router.get("/financial-profile")
@limiter.limit("30/minute")
def sandbox_financial_profile(request: Request, session: Session = Depends(get_session)):
    return get_financial_profile(session, _get_demo_user_id(session))


@router.get("/transactions")
@limiter.limit("30/minute")
def sandbox_transactions(request: Request, session: Session = Depends(get_session)):
    """Same shape as the real GET /api/transactions — powers the sandbox's
    slowed-down ScanAnimation replay so visitors can actually see the
    'import experience', not just the end-state Financial Profile."""
    demo_user_id = _get_demo_user_id(session)
    query = (
        select(Transaction)
        .where(Transaction.user_id == demo_user_id)
        .order_by(Transaction.date.desc())
    )
    return [_serialize(t) for t in session.exec(query).all()]


@router.get("/insights")
@limiter.limit("30/minute")
def sandbox_insights(request: Request, session: Session = Depends(get_session)):
    return {"insights": latest_ledger_insights(session, _get_demo_user_id(session), limit=5)}


@router.get("/chat/starters")
@limiter.limit("30/minute")
def sandbox_chat_starters(request: Request, session: Session = Depends(get_session)):
    return {"questions": starter_questions(session, _get_demo_user_id(session))}


@router.post("/chat")
@limiter.limit("10/hour")
def sandbox_chat(request: Request, req: SandboxChatRequest, session: Session = Depends(get_session)):
    demo_user_id = _get_demo_user_id(session)
    try:
        check_and_record_usage(session, demo_user_id, get_settings().sandbox_chat_daily_limit)
    except ChatUsageLimitExceeded as e:
        raise HTTPException(
            status_code=429,
            detail=f"The sandbox demo has reached its shared daily question limit ({e.limit}). Try again tomorrow, or sign up to ask your own.",
        )
    try:
        result = answer_question(session, demo_user_id, req.question, req.history)
    except RuntimeError as e:  # config problem (e.g. missing API key)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception:
        logger.exception("sandbox chat failed")
        raise HTTPException(status_code=502, detail="Chat failed — please try again")
    result["coverage"] = data_coverage(session, demo_user_id)
    return result
