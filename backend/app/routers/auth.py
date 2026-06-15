from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginIn, TokenOut, UserOut
from ..security import create_access_token, create_refresh_token, decode_token, verify_password

router = APIRouter()


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == payload.username))).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    return TokenOut(
        access_token=create_access_token(user.username, user.role.value),
        refresh_token=create_refresh_token(user.username),
    )


@router.post("/refresh", response_model=TokenOut)
async def refresh(token: str, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(token)
        if payload.get("typ") != "refresh":
            raise ValueError()
        username = payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return TokenOut(
        access_token=create_access_token(user.username, user.role.value),
        refresh_token=create_refresh_token(user.username),
    )


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user
