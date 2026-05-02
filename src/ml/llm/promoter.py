"""
ProdPlan ONE - LLM Adapter Promoter (Sprint S.5)
==================================================

Registers a completed QLoRA adapter with the Sprint G ModelRegistry and
optionally promotes it via governance. Returns the registered
ArtifactVersion so callers can chain decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class PromotionOutcome:
    model_name: str
    version: int
    adapter_path: Path
    registered: bool
    promoted: bool
    decision_id: Optional[UUID] = None
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "version": self.version,
            "adapter_path": str(self.adapter_path),
            "registered": self.registered,
            "promoted": self.promoted,
            "decision_id": str(self.decision_id) if self.decision_id else None,
            "error": self.error,
        }


class LLMAdapterPromoter:
    """Saves a LoRA adapter via ModelRegistry + optional governance path."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def register(
        self,
        *,
        model_name: str,
        adapter_path: Path,
        metrics: dict[str, Any],
    ) -> PromotionOutcome:
        try:
            from src.ml.models.registry import ModelRegistry

            registry = ModelRegistry(self.session, self.tenant_id)
            # FASE 1B.7 (CRIT-03) — call registry.save with the actual
            # signature `(model_name, model, metrics, trained_by, ...)`.
            # The previous version passed `model_obj=...` and `extra=...`,
            # which raised TypeError on every call — silently caught
            # below and returned `registered=False`. So no LoRA adapter
            # had ever been registered. We now stash the adapter path
            # plus a kind discriminator inside the `model` payload so the
            # joblib pickle still round-trips through ArtifactStorage,
            # and put the per-call metadata under `metrics["meta"]` so
            # callers can inspect it without changing the registry API.
            adapter_payload = {
                "kind": "lora_adapter",
                "adapter_path": str(adapter_path),
            }
            metrics_with_meta = dict(metrics)
            metrics_with_meta.setdefault("meta", {}).update({
                "kind": "lora_adapter",
                "adapter_path": str(adapter_path),
            })
            artifact = await registry.save(
                model_name=model_name,
                model=adapter_payload,
                metrics=metrics_with_meta,
                trained_by="qlora_trainer",
            )
            version = int(getattr(artifact, "version", 0))
            return PromotionOutcome(
                model_name=model_name,
                version=version,
                adapter_path=adapter_path,
                registered=True,
                promoted=False,
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Adapter registration failed: %s", exc)
            return PromotionOutcome(
                model_name=model_name, version=0,
                adapter_path=adapter_path,
                registered=False, promoted=False,
                error=str(exc),
            )

    async def propose_promotion(
        self,
        *,
        model_name: str,
        adapter_path: Path,
        metrics: dict[str, Any],
        proposed_by: str = "fine_tune_job",
    ) -> PromotionOutcome:
        outcome = await self.register(
            model_name=model_name, adapter_path=adapter_path, metrics=metrics,
        )
        if not outcome.registered:
            return outcome
        try:
            from src.governance.models import ApprovalAction
            from src.governance.service import GovernanceService

            svc = GovernanceService(self.session, self.tenant_id)
            decision = await svc.propose_decision(
                decision_type="model_promotion",
                title=f"Promote LoRA adapter {model_name} v{outcome.version}",
                action_data={
                    "model_name": model_name,
                    "version": outcome.version,
                    "adapter_path": str(adapter_path),
                },
                proposed_by=proposed_by,
                description="Auto-proposed after successful QLoRA training",
                expected_impact={"metrics": metrics},
                risk_level="low",
            )
            outcome.decision_id = UUID(decision["id"])
            outcome.promoted = decision["status"] == "approved"
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("Promotion proposal failed: %s", exc)
            outcome.error = str(exc)
        return outcome
