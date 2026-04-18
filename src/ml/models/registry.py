"""
ProdPlan ONE — Model Registry
==============================

Coordinates the lifecycle of trained ML artifacts: save a trained model
+ metadata, load the active version at inference time, promote a version
to active (atomic: deactivate previous).

Version numbers are per (tenant, model_name) and monotonically increasing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.ml.config import get_config
from src.ml.models.orm import MLModelArtifact
from src.ml.models.storage import ArtifactStorage

logger = logging.getLogger(__name__)


class ModelRegistryError(Exception):
    """Base class for registry errors."""


class ModelNotFoundError(ModelRegistryError):
    """Requested model/version does not exist."""


class ModelRegistry:
    """
    DB-backed registry for ML artifacts.

    Usage:
        reg = ModelRegistry(db, tenant_id)
        artifact = await reg.save(
            model_name="quality_risk",
            model=trained_xgb,
            metrics={"wmape": 0.08, "auc": 0.82, "samples": 89123},
            trained_by="retrain_job",
            training_duration_sec=124.5,
            training_samples=89123,
        )
        # Governance creates a DecisionRun; when approved, promote:
        await reg.promote(artifact.id, decision_id=decision_uuid, promoted_by="bob")

        # Inference:
        active = await reg.get_active("quality_risk")
        model = reg.load(active.storage_uri) if active else None
    """

    def __init__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        storage: Optional[ArtifactStorage] = None,
    ) -> None:
        self.session = session
        self.tenant_id = tenant_id
        self.storage = storage or ArtifactStorage(get_config())

    # ------------------------------------------------------------------ #
    # Persist                                                            #
    # ------------------------------------------------------------------ #

    async def save(
        self,
        model_name: str,
        model: Any,
        metrics: Dict[str, Any],
        trained_by: str = "system",
        training_duration_sec: Optional[float] = None,
        training_samples: Optional[int] = None,
    ) -> MLModelArtifact:
        """Persist `model` + metadata as a new version. Does NOT promote."""
        next_version = await self._next_version(model_name)
        storage_uri = self.storage.save(model, model_name, next_version)

        artifact = MLModelArtifact(
            id=uuid4(),
            tenant_id=self.tenant_id,
            model_name=model_name,
            version=next_version,
            storage_uri=storage_uri,
            metrics=metrics or {},
            active=False,
            trained_by=trained_by,
            training_duration_sec=training_duration_sec,
            training_samples=training_samples,
        )
        self.session.add(artifact)
        await self.session.flush()
        logger.info(
            f"Registered {model_name} v{next_version} (artifact_id={artifact.id}, "
            f"samples={training_samples})"
        )
        return artifact

    # ------------------------------------------------------------------ #
    # Retrieve                                                           #
    # ------------------------------------------------------------------ #

    async def get(self, artifact_id: UUID) -> Optional[MLModelArtifact]:
        stmt = select(MLModelArtifact).where(
            and_(
                MLModelArtifact.id == artifact_id,
                MLModelArtifact.tenant_id == self.tenant_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active(self, model_name: str) -> Optional[MLModelArtifact]:
        stmt = select(MLModelArtifact).where(
            and_(
                MLModelArtifact.tenant_id == self.tenant_id,
                MLModelArtifact.model_name == model_name,
                MLModelArtifact.active.is_(True),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(
        self,
        model_name: str,
        limit: int = 20,
    ) -> List[MLModelArtifact]:
        stmt = (
            select(MLModelArtifact)
            .where(
                and_(
                    MLModelArtifact.tenant_id == self.tenant_id,
                    MLModelArtifact.model_name == model_name,
                )
            )
            .order_by(desc(MLModelArtifact.version))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_models(self) -> List[str]:
        """Distinct model names for this tenant."""
        stmt = (
            select(MLModelArtifact.model_name)
            .where(MLModelArtifact.tenant_id == self.tenant_id)
            .distinct()
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    # ------------------------------------------------------------------ #
    # Promote                                                            #
    # ------------------------------------------------------------------ #

    async def promote(
        self,
        artifact_id: UUID,
        decision_id: Optional[UUID],
        promoted_by: str,
    ) -> MLModelArtifact:
        """
        Make `artifact_id` the active version for its model_name.
        Deactivates the previous active version in the same transaction.

        Callers that want governance enforcement should first create a
        DecisionRun with `decision_type='model_promotion'` and pass the
        resulting `decision_id` here.
        """
        target = await self.get(artifact_id)
        if target is None:
            raise ModelNotFoundError(f"Artifact {artifact_id} not found")

        # Deactivate any existing active artifact for this model
        await self.session.execute(
            update(MLModelArtifact)
            .where(
                and_(
                    MLModelArtifact.tenant_id == self.tenant_id,
                    MLModelArtifact.model_name == target.model_name,
                    MLModelArtifact.active.is_(True),
                )
            )
            .values(active=False)
        )

        target.active = True
        target.promoted_at = datetime.now(timezone.utc)
        target.promoted_by = promoted_by
        target.promoted_by_decision_id = decision_id
        await self.session.flush()
        logger.info(
            f"Promoted {target.model_name} v{target.version} "
            f"(artifact_id={target.id}, decision={decision_id})"
        )
        return target

    # ------------------------------------------------------------------ #
    # Load the actual model object from disk                             #
    # ------------------------------------------------------------------ #

    def load(self, storage_uri: str) -> Any:
        return self.storage.load(storage_uri)

    # ------------------------------------------------------------------ #
    # Helpers                                                            #
    # ------------------------------------------------------------------ #

    async def _next_version(self, model_name: str) -> int:
        stmt = (
            select(MLModelArtifact.version)
            .where(
                and_(
                    MLModelArtifact.tenant_id == self.tenant_id,
                    MLModelArtifact.model_name == model_name,
                )
            )
            .order_by(desc(MLModelArtifact.version))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        last = result.scalar_one_or_none()
        return (last or 0) + 1

    @staticmethod
    def to_dict(artifact: MLModelArtifact) -> Dict[str, Any]:
        return {
            "id": str(artifact.id),
            "tenant_id": str(artifact.tenant_id),
            "model_name": artifact.model_name,
            "version": artifact.version,
            "storage_uri": artifact.storage_uri,
            "metrics": artifact.metrics or {},
            "active": artifact.active,
            "promoted_by_decision_id": (
                str(artifact.promoted_by_decision_id)
                if artifact.promoted_by_decision_id else None
            ),
            "promoted_at": (
                artifact.promoted_at.isoformat() if artifact.promoted_at else None
            ),
            "promoted_by": artifact.promoted_by,
            "trained_by": artifact.trained_by,
            "training_duration_sec": artifact.training_duration_sec,
            "training_samples": artifact.training_samples,
            "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
        }
