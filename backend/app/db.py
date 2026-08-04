"""Database engine and session management."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

settings = get_settings()

# Under pytest every test runs on its own event loop, and an asyncpg connection
# is bound to the loop that opened it. A pooled connection therefore leaks
# across loops and fails with "Event loop is closed" on reuse. NullPool opens
# and closes per checkout, which is slower and correct; pooling stays on
# everywhere else.
_pool_kwargs: dict[str, object] = (
    {"poolclass": NullPool}
    if settings.ENVIRONMENT == "test"
    else {"pool_size": 5, "max_overflow": 5}
)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,  # Render free tier drops idle connections.
    **_pool_kwargs,  # type: ignore[arg-type]
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Let handlers read attributes after commit.
    autoflush=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a session that rolls back on error.

    Commits are explicit in the handler. An unhandled exception rolls the
    transaction back rather than leaving it half-applied.
    """
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
