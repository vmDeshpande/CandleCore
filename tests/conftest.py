import asyncio
import os
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_URL = os.environ.get("CANDLECORE_TEST_DATABASE_URL")


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def pg_engine():
    if not TEST_DB_URL:
        pytest.fail(
            "CANDLECORE_TEST_DATABASE_URL is not set; cannot run PostgreSQL integration tests"
        )
    try:
        engine = create_async_engine(TEST_DB_URL, echo=False)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.fail(f"PostgreSQL integration test connection failed: {exc.__class__.__name__}")
    yield engine
    await engine.dispose()


@pytest.fixture
async def pg_session(pg_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE candle_revisions, data_gaps, ingestion_checkpoints, candles, raw_market_events CASCADE"
            )
        )
        await session.commit()
        yield session
