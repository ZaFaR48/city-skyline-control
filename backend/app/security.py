from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt, JWTError
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(p: str) -> str:
    return pwd_context.hash(p)


def verify_password(p: str, hashed: str) -> bool:
    return pwd_context.verify(p, hashed)


def _encode(payload: dict[str, Any], ttl: timedelta) -> str:
    payload = {**payload, "exp": datetime.now(timezone.utc) + ttl}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(sub: str, role: str) -> str:
    return _encode({"sub": sub, "role": role, "typ": "access"},
                   timedelta(minutes=settings.ACCESS_TOKEN_TTL_MIN))


def create_refresh_token(sub: str) -> str:
    return _encode({"sub": sub, "typ": "refresh"},
                   timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS))


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as e:
        raise ValueError("invalid_token") from e
