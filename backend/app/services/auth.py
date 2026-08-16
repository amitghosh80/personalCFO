import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlmodel import Session, select

from ..config import get_settings
from ..models.password_reset_token import PasswordResetToken
from ..models.user import User

RESET_TOKEN_TTL_MINUTES = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not set in environment")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> int:
    """Returns the user id encoded in the token, or raises jwt.PyJWTError."""
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not set in environment")
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    return int(payload["sub"])


def _hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_reset_token(session: Session, user_id: int) -> str:
    """Invalidates any outstanding reset tokens for this user and issues a new one.
    Returns the raw token (only ever held in memory / the emailed link; the DB stores
    just its hash)."""
    existing = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at == None,  # noqa: E711
        )
    ).all()
    for token in existing:
        session.delete(token)

    raw_token = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            user_id=user_id,
            token_hash=_hash_reset_token(raw_token),
            expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
        )
    )
    return raw_token


def consume_reset_token(session: Session, raw_token: str) -> User | None:
    """Validates and single-use-consumes a reset token, returning the associated user
    (or None if the token is missing/expired/already used). Caller must commit."""
    token = session.exec(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == _hash_reset_token(raw_token)
        )
    ).first()
    if not token or token.used_at is not None or token.expires_at < datetime.utcnow():
        return None

    token.used_at = datetime.utcnow()
    session.add(token)
    return session.get(User, token.user_id)
