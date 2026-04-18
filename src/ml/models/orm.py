"""
ProdPlan ONE — ML Model Artifact ORM
=====================================

`MLModelArtifact` row: one per trained version of a model.

Referenced by `ModelRegistry`. The `active` flag is unique per (tenant, name)
at the application level (not DB-enforced — enforced by registry.promote()
inside a transaction).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.database import TenantBase


class MLModelArtifact(TenantBase):
    """
    A trained ML model version owned by a tenant.

    Storage: `storage_uri` points to the joblib blob (local filesystem MVP;
    swap for S3/GCS later by pointing URIs accordingly).

    Promotion: `active=True` means this is the version that inference should
    use. Governance creates a `DecisionRun` that flips `active` via
    `ModelRegistry.promote()`.
    """

    __tablename__ = "ml_model_artifact"
    __table_args__ = (
        Index("idx_ml_artifact_tenant_name", "tenant_id", "model_name"),
        Index("idx_ml_artifact_active", "tenant_id", "model_name", "active"),
        Index("idx_ml_artifact_created", "created_at"),
    )

    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)

    # Training metadata — wmape, auc, samples, trained_at_utc, feature_schema_hash, etc.
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Link back to the governance decision that promoted this version.
    # Nullable because retrain-without-promotion is a valid state.
    promoted_by_decision_id: Mapped[Optional[UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )
    promoted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    promoted_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Training context
    trained_by: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    training_duration_sec: Mapped[Optional[float]] = mapped_column(nullable=True)
    training_samples: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
