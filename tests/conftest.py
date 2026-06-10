"""
Shared test fixtures for the API test suite.

Design goals:
- Default `pytest` (unit) runs without any external services (no Postgres).
- `pytest -m integration` (or `make test-integration`) boots the full app,
  applies Alembic migrations once per session, and provides per-test
  transaction rollback via a SAVEPOINT pattern.
- Tests placed under `tests/unit/` or `tests/integration/` are auto-tagged
  with the corresponding marker — no decorator required.
"""
from __future__ import annotations

import asyncio
import os
import re
from collections.abc import AsyncGenerator
from collections.abc import Awaitable, Callable

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ---------------------------------------------------------------------------
# Collection hook: auto-tag tests by directory.
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items):
    """Auto-apply the `unit` or `integration` marker based on the test path."""
    for item in items:
        path = str(item.fspath)
        if "/tests/unit/" in path and not any(
            m.name == "unit" for m in item.iter_markers()
        ):
            item.add_marker(pytest.mark.unit)
        elif "/tests/integration/" in path and not any(
            m.name == "integration" for m in item.iter_markers()
        ):
            item.add_marker(pytest.mark.integration)


def _integration_selected(config) -> bool:
    """Return True when the active marker expression targets integration tests."""
    expr = config.getoption("-m") or ""
    return bool(re.search(r"\bintegration\b", expr)) and not bool(
        re.search(r"\bnot\s+integration\b", expr)
    )


# ---------------------------------------------------------------------------
# Session-scoped async engine bound to the dedicated test database.
# Only materialized when integration tests are selected.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Session-scoped async engine bound to TEST_DATABASE_URL."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "TEST_DATABASE_URL is not set. Define it in api/.env.test or the shell "
            "environment before running integration tests."
        )
    eng = create_async_engine(url, future=True, pool_pre_ping=True)
    try:
        yield eng
    finally:
        await eng.dispose()


# ---------------------------------------------------------------------------
# Alembic migrations: integration-only, once per session.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="session")
async def apply_migrations(request) -> AsyncGenerator[None, None]:
    """
    Apply `alembic upgrade head` once before integration tests.

    NOT autouse — gated on the `-m integration` selection so unit-only
    runs never touch Postgres or Alembic.
    """
    if not _integration_selected(request.config):
        yield
        return

    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["TEST_DATABASE_URL"])
    await asyncio.to_thread(command.upgrade, cfg, "head")
    yield
    # Downgrade intentionally skipped for speed; the dedicated test DB is
    # recreated/cleared out-of-band when schema resets are required.


# ---------------------------------------------------------------------------
# Per-test DB session with full transaction rollback.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session(
    engine: AsyncEngine,
    apply_migrations: None,
) -> AsyncGenerator[AsyncSession, None]:
    """
    Per-test async session bound to a connection-level transaction that is
    rolled back in teardown. Uses SAVEPOINT + `after_transaction_end` to
    keep the test transaction alive even if test code calls `session.commit()`.
    """
    async with engine.connect() as conn:
        trans = await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        async with session_factory() as session:
            await session.begin_nested()

            @event.listens_for(session.sync_session, "after_transaction_end")
            def _restart_savepoint(sess, transaction):  # pragma: no cover - SA hook
                if transaction.nested and not transaction._parent.nested:
                    sess.begin_nested()

            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()


# ---------------------------------------------------------------------------
# ASGI client with FastAPI lifespan and DB dependency override.
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Async HTTP client bound to the FastAPI app under test.

    The DB dependency is overridden to share the rollback-scoped session,
    so endpoint code participates in the same transaction as the test.
    """
    from asgi_lifespan import LifespanManager

    from app.db.session import get_db
    from app.main import app

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with LifespanManager(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                # Use HTTPS so Secure auth cookies participate in integration flows.
                base_url="https://testserver",
            ) as ac:
                yield ac
    finally:
        app.dependency_overrides.pop(get_db, None)


# ---------------------------------------------------------------------------
# Shared auth fixtures for protected endpoint integration tests.
# ---------------------------------------------------------------------------


@pytest.fixture
def authenticate(
    client: httpx.AsyncClient,
) -> Callable[[str | None], Awaitable["AuthenticatedTestContext"]]:
    """Return a helper that authenticates the shared client via OTP flow."""
    from tests.auth_helpers import AuthenticatedTestContext, authenticate_via_email_otp

    async def _authenticate(email: str | None = None) -> AuthenticatedTestContext:
        return await authenticate_via_email_otp(client, email=email)

    return _authenticate


@pytest_asyncio.fixture
async def authenticated_context(
    authenticate: Callable[[str | None], Awaitable["AuthenticatedTestContext"]],
) -> "AuthenticatedTestContext":
    """Authenticated test context backed by the real OTP -> session flow."""
    return await authenticate()


@pytest_asyncio.fixture
async def authenticated_client(
    authenticated_context: "AuthenticatedTestContext",
) -> httpx.AsyncClient:
    """HTTP client with a real backend-issued session cookie."""
    return authenticated_context.client


@pytest.fixture
def authenticated_user(
    authenticated_context: "AuthenticatedTestContext",
) -> dict[str, object]:
    """Authenticated user summary associated with `authenticated_client`."""
    return authenticated_context.user


# ---------------------------------------------------------------------------
# Bind factory-boy BaseFactory to the active rollback-scoped session.
# Sync autouse so we don't re-enter the async fixture's event loop.
# Only activates when the current test (transitively) depends on `db_session`.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _bind_factory_session(request):
    if "db_session" not in request.fixturenames:
        yield
        return

    from tests.factories import BaseFactory

    session = request.getfixturevalue("db_session")
    previous = BaseFactory._meta.sqlalchemy_session
    BaseFactory._meta.sqlalchemy_session = session
    try:
        yield
    finally:
        BaseFactory._meta.sqlalchemy_session = previous
