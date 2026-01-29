"""
ProdPlan ONE - Test Fixtures
============================

Common fixtures for all tests.
"""

import pytest
import asyncio
from typing import AsyncGenerator
from uuid import uuid4
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Test database URL (in-memory SQLite for fast tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=StaticPool,
    connect_args={"check_same_thread": False},
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="function")
async def test_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a test database session.
    
    Creates tables, yields session, then drops tables after test.
    """
    from src.shared.database import Base
    
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
    
    # Drop all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def sample_tenant_id():
    """Sample tenant ID for tests."""
    return uuid4()


@pytest.fixture
def sample_aggregate_id():
    """Sample aggregate ID for tests."""
    return uuid4()


@pytest.fixture
def sample_event_payload():
    """Sample event payload for tests."""
    return {
        "plan_id": str(uuid4()),
        "makespan_minutes": 1200,
        "cost_eur": 5000.0,
        "oee_percent": 85.5,
    }










