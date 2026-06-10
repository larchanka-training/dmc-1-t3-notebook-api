"""
Async SQLAlchemy session factory and FastAPI dependency.

This module is the single source of truth for the application's database session.
The `get_db` callable is a FastAPI dependency that yields an `AsyncSession`
scoped to a single request; the test suite overrides it with a rollback-bound
session so endpoint code participates in the test transaction.

IMPORTANT FOR TESTS: import this module only inside fixture bodies, never at
test-module level. The module-level `engine` is created at import time using
`settings.DATABASE_URL`; importing it outside a fixture would connect to the
wrong host before `TEST_DATABASE_URL` is in effect.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings


def _make_engine() -> AsyncEngine:
    return create_async_engine(
        settings.DATABASE_URL,
        future=True,
        pool_pre_ping=True,
    )


engine: AsyncEngine = _make_engine()

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a transactional async session.

    The session is closed automatically after the request.
    Tests override this dependency to inject a rollback-scoped session.
    """
    async with SessionLocal() as session:
        yield session
