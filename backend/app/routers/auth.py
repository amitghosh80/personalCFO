import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, field_validator
from sqlmodel import Session, select

from ..config import get_settings
from ..database import get_session
from ..dependencies import get_current_user
from ..models.import_job import ImportJob
from ..models.insight import Insight
from ..models.merchant_rule import MerchantRule
from ..models.transaction import Transaction
from ..models.user import User
from ..rate_limit import limiter
from ..services.auth import (
    consume_reset_token,
    create_access_token,
    create_reset_token,
    hash_password,
    verify_password,
)
from ..services.email import send_password_reset_email

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("personalcfo.auth")


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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


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
@limiter.limit("5/hour")
def signup(request: Request, body: SignupRequest, session: Session = Depends(get_session)):
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

    logger.info(f"signup user_id={user.id}")
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": _user_out(user)}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, session: Session = Depends(get_session)):
    email = body.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        logger.info("login failed")
        raise HTTPException(status_code=401, detail="Invalid email or password")

    logger.info(f"login user_id={user.id}")
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer", "user": _user_out(user)}


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return _user_out(current_user)


@router.post("/forgot-password")
@limiter.limit("5/hour")
def forgot_password(request: Request, body: ForgotPasswordRequest, session: Session = Depends(get_session)):
    email = body.email.lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        raw_token = create_reset_token(session, user.id)
        reset_link = f"{get_settings().frontend_url}/reset-password?token={raw_token}"
        try:
            send_password_reset_email(user.email, reset_link)
        except Exception:
            logger.exception(f"failed to send password reset email user_id={user.id}")
        session.commit()
        logger.info(f"password reset requested user_id={user.id}")

    # Always return the same message, whether or not the email exists, to avoid
    # leaking which addresses are registered.
    return {"message": "If that email is registered, we've sent a password reset link."}


@router.post("/reset-password")
@limiter.limit("10/hour")
def reset_password(request: Request, body: ResetPasswordRequest, session: Session = Depends(get_session)):
    user = consume_reset_token(session, body.token)
    if not user:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired.")

    user.hashed_password = hash_password(body.new_password)
    session.add(user)
    session.commit()

    logger.info(f"password reset completed user_id={user.id}")
    return {"message": "Password updated. You can now log in."}
