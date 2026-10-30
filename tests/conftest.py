import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

TEST_DB_URL = os.environ.get("CANDLECORE_TEST_DATABASE_URL")


@pytest_asyncio.fixture
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


@pytest_asyncio.fixture
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
