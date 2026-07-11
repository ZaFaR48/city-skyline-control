from __future__ import annotations

from urllib.parse import urlparse

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings


def pytest_configure() -> None:
    database = urlparse(settings.DATABASE_URL.replace("+asyncpg", "")).path.lstrip("/")
    if "_test_" not in database:
        raise RuntimeError("Backend tests refuse to run unless DATABASE_URL names an isolated *_test_* database")


@pytest_asyncio.fixture
async def db():
    test_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False)
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()
    await test_engine.dispose()
