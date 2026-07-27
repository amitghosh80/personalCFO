from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import get_current_user
from ..models.import_job import ImportJob
from ..models.insight import Insight
from ..models.merchant_rule import MerchantRule
from ..models.transaction import Transaction
from ..models.user import User
from ..services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def _min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _user_out(user: User) -> dict:
    return {"id": user.id, "email": user.email}


def _claim_legacy_data(session: Session, user_id: int) -> None:
    """One-time backfill: the very first account to sign up inherits every
    pre-multi-tenancy row (local dev/test data with no owner yet)."""
    for model in (Transaction, ImportJob, MerchantRule, Insight):
        rows = session.exec(select(model).where(model.user_id == None)).all()  # noqa: E711
        for row in rows:
            row.user_id = user_id
            session.add(row)


@router.post("/signup")
def signup(body: SignupRequest, session: Session = Depends(get_session)):
    email = body.email.lower()
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    is_first_user = session.exec(select(User)).first() is None

    user = User(email=email, hashed_password=hash_password(body.password))
    session.add(user)
    session.flush()  # assign user.id before using it to claim legacy rows

    if is_first_user:
        _claim_legacy_data(session, user.id)

    session.commit()
    session.refresh(user)

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": _user_out(user)}


@router.post("/login")
def login(body: LoginRequest, session: Session = Depends(get_session)):
    email = body.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": _user_out(user)}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _user_out(current_user)
