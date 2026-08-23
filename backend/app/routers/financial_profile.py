from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..database import get_session
from ..dependencies import get_current_user
from ..models.user import User
from ..services.profile_engine import get_financial_profile

router = APIRouter(prefix="/api", tags=["financial-profile"])


@router.get("/financial-profile")
def financial_profile(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Evergreen metrics module (Flow 5) for the View Important page. Always
    returns 200 with all six metrics; a metric with insufficient data reports
    its own status rather than failing the whole request."""
    return get_financial_profile(session, current_user.id)
