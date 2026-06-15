from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import Role, User
from .security import decode_token

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2), db: AsyncSession = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
        if payload.get("typ") != "access":
            raise ValueError()
        username = payload["sub"]
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User inactive")
    return user


def require_roles(*roles: Role):
    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return _dep
