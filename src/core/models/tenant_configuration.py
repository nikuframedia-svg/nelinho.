"""
ProdPlan ONE - Tenant Configuration Model
==========================================

Sprint L — per-tenant configuration entity. Each row holds one typed
configuration value (key) within a category, with optional validity window
and full audit trail (created_by / last_modified_by).

Consumers read via `TenantConfigService` (Sprint L.2); direct ORM access
is discouraged because the service layer enforces caching and invalidation.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import Base


# Fixed vocabulary. Consumers SHOULD use these constants rather than raw strings.
CATEGORY_GOVERNANCE = "governance"
CATEGORY_SUPPLY = "supply"
CATEGORY_PLANNING = "planning"
CATEGORY_QUALITY = "quality"
CATEGORY_COST = "cost"
CATEGORY_MOLD = "mold"
CATEGORY_LLM = "llm"
CATEGORY_COPILOT = "copilot"
CATEGORY_FACTORY_MAP = "factory_map"
CATEGORY_TRUST = "trust"
CATEGORY_WORKFORCE = "workforce"

ALLOWED_CATEGORIES = frozenset({
    CATEGORY_GOVERNANCE,
    CATEGORY_SUPPLY,
    CATEGORY_PLANNING,
    CATEGORY_QUALITY,
    CATEGORY_COST,
    CATEGORY_MOLD,
    CATEGORY_LLM,
    CATEGORY_COPILOT,
    CATEGORY_FACTORY_MAP,
    CATEGORY_TRUST,
    CATEGORY_WORKFORCE,
})

DATA_TYPE_INT = "int"
DATA_TYPE_FLOAT = "float"
DATA_TYPE_BOOL = "bool"
DATA_TYPE_STRING = "string"
DATA_TYPE_JSON = "json"
DATA_TYPE_DURATION = "duration"  # seconds, stored as int
DATA_TYPE_CURRENCY = "currency"  # decimal EUR, stored as float

ALLOWED_DATA_TYPES = frozenset({
    DATA_TYPE_INT,
    DATA_TYPE_FLOAT,
    DATA_TYPE_BOOL,
    DATA_TYPE_STRING,
    DATA_TYPE_JSON,
    DATA_TYPE_DURATION,
    DATA_TYPE_CURRENCY,
})


class TenantConfiguration(Base):
    """Per-tenant configuration entry, versioned by `valid_from`."""

    __tablename__ = "tenant_configuration"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "category", "key", "valid_from",
            name="uq_tenant_configuration_scope",
        ),
        Index(
            "ix_tenant_configuration_tenant_cat_key",
            "tenant_id", "category", "key",
        ),
        {"schema": "core"},
    )

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

    # Vocabulary (see ALLOWED_* sets). Kept as String so DB doesn't need a
    # migration each time we introduce a new category.
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)

    # Typed payload. Always wrapped as {"v": value} so primitives and lists
    # round-trip cleanly through JSONB.
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Validity window (null valid_to = currently active).
    valid_from: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.utcnow,
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Audit
    created_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, nullable=False)
    last_modified_by: Mapped[Optional[UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    last_modified_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<TenantConfiguration tenant={self.tenant_id} "
            f"{self.category}.{self.key}={self.value!r}>"
        )

    @staticmethod
    def wrap(raw_value: Any) -> dict:
        """Wrap a primitive or list into the JSONB storage envelope."""
        return {"v": raw_value}

    @staticmethod
    def unwrap(stored: dict) -> Any:
        """Inverse of `wrap`."""
        if not isinstance(stored, dict) or "v" not in stored:
            # tolerate legacy rows that stored the raw object directly
            return stored
        return stored["v"]

    @property
    def raw_value(self) -> Any:
        return self.unwrap(self.value)
