"""
ProdPlan ONE - Database Configuration
======================================

Async SQLAlchemy 2.0 setup with PostgreSQL.
Includes multi-tenancy base model and session management.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Optional
from uuid import UUID, uuid4

from sqlalchemy import MetaData, event, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .config import settings

# Naming convention for constraints (helps with migrations)
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Base class for all models."""
    
    metadata = metadata


class TenantBase(Base):
    """
    Base class for tenant-scoped models.
    
    All models that are tenant-specific should inherit from this class.
    Provides automatic tenant_id column and created_at/updated_at timestamps.
    """
    
    __abstract__ = True
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class GlobalBase(Base):
    """
    Base class for global (non-tenant) models.
    
    For system-wide entities like tenants themselves.
    """
    
    __abstract__ = True
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


# Create async engine
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.database_echo,
    pool_pre_ping=True,
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session.
    
    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            # Only commit if there are pending changes
            if session.dirty or session.new or session.deleted:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database session.
    
    Usage:
        async with get_session_context() as session:
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            # Only commit if there are pending changes
            if session.dirty or session.new or session.deleted:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class TenantSession:
    """
    Tenant-scoped session wrapper.
    
    Automatically filters queries by tenant_id.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self.tenant_id = tenant_id
    
    @property
    def session(self) -> AsyncSession:
        return self._session
    
    async def execute(self, statement, **kwargs):
        """Execute a statement with automatic tenant filtering."""
        return await self._session.execute(statement, **kwargs)
    
    async def commit(self):
        await self._session.commit()
    
    async def rollback(self):
        await self._session.rollback()
    
    def add(self, instance):
        """Add instance, automatically setting tenant_id if applicable."""
        if hasattr(instance, "tenant_id") and instance.tenant_id is None:
            instance.tenant_id = self.tenant_id
        self._session.add(instance)
    
    def add_all(self, instances):
        """Add multiple instances, setting tenant_id on each."""
        for instance in instances:
            self.add(instance)


async def init_db() -> None:
    """Initialize database tables.

    pgvector pode não estar disponível (scoop Postgres sem a extensão
    `vector`). Nesse caso a tabela `copilot_rag_chunk` — coluna
    `VECTOR(768)` — não pode ser criada; em vez de abortar todo o
    `init_db` (e deixar o backend sem BD), excluímo-la do `create_all`.
    Mesmo comportamento do `scripts/bootstrap_dev_full.py`; o RAG
    semântico fica desligado até pgvector existir. Ver CLAUDE.md.
    """
    import logging

    async with engine.begin() as conn:
        has_vector = await conn.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_available_extensions "
                "WHERE name = 'vector')"
            )
        )
        if has_vector:
            await conn.run_sync(Base.metadata.create_all)
            return
        tables = [
            t for t in Base.metadata.sorted_tables
            if t.name != "copilot_rag_chunk"
        ]
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=tables
            )
        )
        logging.getLogger(__name__).warning(
            "pgvector indisponível — copilot_rag_chunk excluído do "
            "init_db (RAG semântico desligado)."
        )


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


# Health check
async def check_db_health() -> bool:
    """Check database connectivity."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# ============================================================================
# Database Availability Check (with caching)
# ============================================================================

_db_available_cache = {"status": None, "timestamp": 0}
_CACHE_TTL = 5  # seconds


async def is_db_available() -> bool:
    """Check if DB is available (with caching)."""
    import time
    now = time.time()
    if now - _db_available_cache["timestamp"] < _CACHE_TTL:
        return _db_available_cache["status"]
    
    status = await check_db_health()
    _db_available_cache["status"] = status
    _db_available_cache["timestamp"] = now
    return status


async def get_session_safe() -> AsyncGenerator[AsyncSession, None]:
    """Safe session dependency that handles DB unavailability."""
    from fastapi import HTTPException, status
    
    if not await is_db_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please check PostgreSQL connection."
        )
    async for session in get_session():
        yield session

