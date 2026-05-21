"""
ProdPlan ONE - Database Configuration
======================================

Async SQLAlchemy 2.0 setup with PostgreSQL.
Includes multi-tenancy base model and session management.
"""

import logging
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

logger = logging.getLogger(__name__)

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


# ─── Q.62.B.2 — Row-Level Security tenant filter ──────────────────────
#
# Cada nova transacao injecta `SET LOCAL app.tenant_id` consoante o
# ContextVar `current_tenant_id_var` (definido pelo middleware FastAPI
# ou por `tenant_scope()` em background tasks). As policies RLS criadas
# em migration 056_q62_b_rls_enable filtram queries automaticamente.
#
# `SET LOCAL` (não `SET`) — libertado no commit/rollback, não vaza para
# proximo checkout do pool.
#
# Sem tenant_id setado (background task que esqueceu de set explicito,
# request sem header), `current_setting('app.tenant_id', true)` devolve
# string vazia. O cast para UUID falha silenciosamente -> RLS rejeita
# todas as rows (fail-closed).


@event.listens_for(engine.sync_engine, "begin")
def _set_tenant_id_on_transaction_begin(conn):
    """Q.62.B.2 — injecta SET LOCAL app.tenant_id no início de cada tx.

    `engine.sync_engine` é o sync engine subjacente ao async engine.
    Eventos disparados aqui aplicam-se a ambos os modos.
    """
    # Import local para evitar import circular (tenant_context não
    # precisa de database.py).
    from src.shared.auth.tenant_context import get_tenant_id as _get_tid

    tid = _get_tid()
    if tid is None:
        # Sem tenant set — RLS bloqueia tudo (fail-closed). Não levantamos
        # erro aqui porque queries de migration/health-check podem
        # legitimamente correr sem tenant.
        return
    # Uso de exec_driver_sql para evitar parsing SQLAlchemy + escape de
    # UUID inline. UUID validado pelo type system Python antes de chegar
    # aqui, mas defesa em profundidade: str() é seguro.
    conn.exec_driver_sql(f"SET LOCAL app.tenant_id = '{tid}'")


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


async def init_db() -> None:
    """Verify schema is up-to-date with Alembic migrations (Q.61.16).

    Production path: `alembic upgrade head` corre ANTES do uvicorn
    arrancar. Esta funcao apenas verifica que o DB tem uma revision
    aplicada; se nao tem, crash early em vez de criar silenciosamente.

    Pre-Q.61.16 isto fazia `Base.metadata.create_all` em todos os
    arranques — mascarava drift entre Alembic e o modelo SQLA (ex:
    se um modelo novo nao estivesse em `alembic/env.py`, create_all
    criava a tabela e producao via `alembic upgrade head` deixava-a
    orfa). Q.61.14 fechou o lado da deteccao (model_registry); Q.61.16
    fecha o lado da producao.

    Para tests/fixtures/bootstrap_dev: usar `init_db_create_all()`.
    """
    from alembic.runtime.migration import MigrationContext

    async with engine.connect() as conn:
        def _check_revision(sync_conn):
            ctx = MigrationContext.configure(sync_conn)
            return ctx.get_current_revision()

        rev = await conn.run_sync(_check_revision)

    if rev is None:
        raise RuntimeError(
            "DB schema not initialized (alembic_version table empty or "
            "absent). Run `alembic upgrade head` before starting the app."
        )
    logger.info("DB schema at revision %s", rev)


async def init_db_create_all() -> None:
    """Test/dev path — cria tabelas via metadata, sem Alembic.

    Usado por:
      * tests (fixtures async)
      * scripts/bootstrap_dev_full.py (dev fresh setup)
      * scripts ad-hoc que precisam de schema rapido

    NUNCA chamar de producao. Use `alembic upgrade head` antes do
    uvicorn arrancar.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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

