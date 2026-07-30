from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import jwt

from .services.auth import decode_access_token


def _key_func(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            user_id = decode_access_token(auth[7:])
            return f"user:{user_id}"
        except jwt.PyJWTError:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_key_func)
