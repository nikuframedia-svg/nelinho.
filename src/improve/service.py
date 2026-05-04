"""
ProdPlan ONE - Improve Service
================================

Service layer for improvement suggestions. Sprint Q.10 Fase C.

Replaces the in-memory ``suggestions_store`` dict and the fake
"AI-powered" generator with:
* DB-backed CRUD with tenant isolation
* Per-tenant seeding from ``SEED_SUGGESTIONS``
* Real LLM-based generator via Copilot/Ollama with graceful fallback
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.improve.models import (
    ImprovementSuggestion,
    SuggestionSource,
    SuggestionStatus,
)
from src.shared.decorators import record_rule_firing

logger = logging.getLogger(__name__)


class SuggestionNotFoundError(Exception):
    """Raised when a suggestion id doesn't belong to the current tenant."""


class SuggestionStateError(Exception):
    """Raised when an operation is invalid for the suggestion's status."""


# ─── Per-tenant seed data ────────────────────────────────────────────
# Promoted from the previous in-memory PREDEFINED_SUGGESTIONS list. Each
# tenant gets a copy on first interaction so empty installs aren't
# completely empty.
SEED_SUGGESTIONS: List[Dict[str, Any]] = [
    {
        "title": "Reduce standard times for Laminagem phase",
        "description": (
            "Analysis shows that Laminagem phase standard times are 15% "
            "higher than actual production times. Reducing standard times "
            "will improve performance metrics."
        ),
        "domain": "oee",
        "action_type": "reduce_standard_time",
        "estimated_impact": {
            "oee": {"delta": 3.5, "confidence": 0.85},
            "performance": {"delta": 5.0, "confidence": 0.90},
        },
        "confidence": 0.87,
    },
    {
        "title": "Add backup machine for bottleneck station",
        "description": (
            "Station P003 (Corte) is a bottleneck with 92% utilization. "
            "Adding a backup machine would reduce wait times and improve "
            "availability."
        ),
        "domain": "oee",
        "action_type": "add_machine",
        "estimated_impact": {
            "oee": {"delta": 2.0, "confidence": 0.80},
            "availability": {"delta": 3.0, "confidence": 0.85},
        },
        "confidence": 0.82,
    },
    {
        "title": "Implement SPC for quality control",
        "description": (
            "Statistical Process Control at critical quality gates would "
            "reduce defects by catching issues earlier in the process."
        ),
        "domain": "quality",
        "action_type": "improve_quality",
        "estimated_impact": {
            "quality": {"delta": 2.5, "confidence": 0.88},
            "oee": {"delta": 1.8, "confidence": 0.85},
        },
        "confidence": 0.86,
    },
    {
        "title": "Optimize production schedule for OTD improvement",
        "description": (
            "Rescheduling based on delivery deadlines rather than arrival "
            "order would improve on-time delivery by 8%."
        ),
        "domain": "supply",
        "action_type": "optimize_schedule",
        "estimated_impact": {
            "otd": {"delta": 8.0, "confidence": 0.78},
            "lead_time": {"delta": -0.5, "confidence": 0.75},
        },
        "confidence": 0.77,
    },
    {
        "title": "Cross-train operators for multi-station flexibility",
        "description": (
            "Training operators on multiple stations would reduce idle "
            "time during absences and improve overall efficiency."
        ),
        "domain": "hr",
        "action_type": "cross_training",
        "estimated_impact": {
            "availability": {"delta": 2.0, "confidence": 0.82},
            "oee": {"delta": 1.5, "confidence": 0.80},
        },
        "confidence": 0.81,
    },
]


_LLM_PROMPT_TEMPLATE = (
    "És um analista de melhoria contínua de uma fábrica de barcos NELO.\n"
    "Aqui está uma snapshot do estado atual:\n\n"
    "{factory_state}\n\n"
    "Gera {limit} sugestões de melhoria{domain_hint}. Devolve um JSON com "
    "a forma:\n"
    '{{"suggestions": [{{ "title": str, "description": str, '
    '"domain": "oee|quality|supply|hr|other", '
    '"action_type": str, "estimated_impact": {{ "<kpi>": {{ "delta": '
    'float, "confidence": float }} }}, "confidence": float }} ]}}\n\n'
    "Foca-te em mudanças accionáveis a curto prazo. Confidence ∈ [0,1]."
)


class ImproveService:
    """CRUD + LLM-backed generator for improvement suggestions."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    # ── CRUD ──────────────────────────────────────────────────────────

    async def list_suggestions(
        self,
        *,
        status: Optional[str] = None,
        domain: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ImprovementSuggestion]:
        # Seed on empty so a brand-new tenant doesn't see a blank list.
        await self._ensure_seeded()

        stmt = select(ImprovementSuggestion).where(
            ImprovementSuggestion.tenant_id == self.tenant_id,
        )
        if status:
            stmt = stmt.where(ImprovementSuggestion.status == status)
        if domain:
            stmt = stmt.where(ImprovementSuggestion.domain == domain)
        stmt = stmt.order_by(
            ImprovementSuggestion.created_at.desc(),
        ).limit(limit).offset(offset)
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows)

    async def get_suggestion(self, suggestion_id: UUID) -> Optional[ImprovementSuggestion]:
        stmt = select(ImprovementSuggestion).where(
            and_(
                ImprovementSuggestion.id == suggestion_id,
                ImprovementSuggestion.tenant_id == self.tenant_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def approve(
        self,
        suggestion_id: UUID,
        reviewer_id: UUID,
    ) -> ImprovementSuggestion:
        sug = await self.get_suggestion(suggestion_id)
        if sug is None:
            raise SuggestionNotFoundError(str(suggestion_id))
        if sug.status != SuggestionStatus.PENDING.value:
            raise SuggestionStateError(
                f"cannot approve suggestion in status {sug.status!r}"
            )
        sug.status = SuggestionStatus.APPROVED.value
        sug.reviewed_at = datetime.now(timezone.utc)
        sug.reviewed_by = reviewer_id
        sug.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(sug)
        return sug

    async def reject(
        self,
        suggestion_id: UUID,
        reviewer_id: UUID,
        reason: Optional[str] = None,
    ) -> ImprovementSuggestion:
        sug = await self.get_suggestion(suggestion_id)
        if sug is None:
            raise SuggestionNotFoundError(str(suggestion_id))
        if sug.status != SuggestionStatus.PENDING.value:
            raise SuggestionStateError(
                f"cannot reject suggestion in status {sug.status!r}"
            )
        sug.status = SuggestionStatus.REJECTED.value
        sug.reviewed_at = datetime.now(timezone.utc)
        sug.reviewed_by = reviewer_id
        sug.rejection_reason = reason
        sug.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(sug)
        return sug

    # ── Adoption-signal feedback loop (Sprint Q.13.D / D.3) ──────────

    async def record_adoption_signal(
        self,
        *,
        action_type: str,
        accepted: bool,
    ) -> int:
        """Update confidence on suggestions whose `action_type` matches.

        Plan v4 §22-§26 — improve module is the closing piece of the
        learning loop: when a decision the operator EXECUTED matches
        a suggestion the system had pending, we want the suggestion's
        confidence to RISE; conversely when the operator REJECTED a
        decision of the same shape, confidence FALLS.

        Bayesian update via Beta-Bernoulli pseudo-counts
        ------------------------------------------------
        Treat `confidence` as the posterior mean of a Beta(α, β)
        distribution with effective sample size N = 10 (so α + β = 10).
        Each new signal moves α + 1 (accepted) or β + 1 (rejected)
        and we cap N at 50 so eventual convergence is bounded — without
        the cap, very early signals could dominate forever.

        Returns the number of suggestion rows updated. 0 means the
        action_type didn't match any suggestion (typical for free-text
        action_types from external systems).
        """
        # Beta-Bernoulli with effective sample size 10 (initial), capped
        # at 50 (so a single suggestion can't get pinned at confidence
        # 1.0 from one accept).
        prior_n = 10.0
        cap_n = 50.0
        delta_alpha = 1.0 if accepted else 0.0
        delta_beta = 0.0 if accepted else 1.0

        stmt = select(ImprovementSuggestion).where(
            and_(
                ImprovementSuggestion.tenant_id == self.tenant_id,
                ImprovementSuggestion.action_type == action_type,
            )
        )
        rows = list((await self.session.execute(stmt)).scalars().all())
        for sug in rows:
            # Recover (alpha, beta) from current confidence + sample
            # size carried in `estimated_impact["_adoption_n"]` (default
            # = prior_n on first signal).
            existing = sug.estimated_impact.get("_adoption_n") if sug.estimated_impact else None
            n = float(existing) if isinstance(existing, (int, float)) else prior_n
            alpha = n * float(sug.confidence)
            beta = n - alpha

            new_alpha = alpha + delta_alpha
            new_beta = beta + delta_beta
            new_n = min(cap_n, new_alpha + new_beta)
            new_conf = max(0.0, min(1.0, new_alpha / max(1e-9, new_alpha + new_beta)))

            sug.confidence = round(new_conf, 4)
            new_impact = dict(sug.estimated_impact or {})
            new_impact["_adoption_n"] = new_n
            new_impact["_last_signal"] = (
                "accepted" if accepted else "rejected"
            )
            sug.estimated_impact = new_impact
            sug.updated_at = datetime.now(timezone.utc)

        if rows:
            await self.session.flush()
            logger.info(
                "improve.record_adoption_signal: tenant=%s action_type=%s "
                "accepted=%s rows_updated=%d",
                self.tenant_id, action_type, accepted, len(rows),
            )
        return len(rows)

    # ── LLM generator ─────────────────────────────────────────────────

    @record_rule_firing(
        rule_id="improve.generate_via_llm",
        extract_payload=lambda self, *, scope=None, limit=5,
        factory_state_summary=None: {
            "scope": scope,
            "limit": limit,
            "has_factory_state": factory_state_summary is not None,
        },
        serialise_output=lambda result: {
            "suggestion_count": len(result),
            "sources": list({getattr(s, "source", None) for s in result}),
            "action_types": [getattr(s, "action_type", None) for s in result],
        },
        # No dedupe key — LLM gen is a deliberate operator action,
        # every call should appear as its own row.
    )
    async def generate_via_llm(
        self,
        *,
        scope: Optional[str] = None,
        limit: int = 5,
        factory_state_summary: Optional[Dict[str, Any]] = None,
    ) -> List[ImprovementSuggestion]:
        """Generate ``limit`` suggestions via Copilot/Ollama.

        Falls back gracefully to filtered SEED_SUGGESTIONS when:
        * Ollama is down / circuit-breaker is open
        * the LLM returns a malformed payload
        * the parsed list is empty

        ``factory_state_summary`` is the dict the prompt sees as the
        current state. Caller hands it in (typically from
        ``SemanticQueries``) so the service stays decoupled from the
        ingestion path.
        """
        from src.copilot.ollama_client import get_ollama_client

        client = get_ollama_client()
        domain_hint = f" no domínio '{scope}'" if scope else ""
        prompt = _LLM_PROMPT_TEMPLATE.format(
            factory_state=json.dumps(factory_state_summary or {}, ensure_ascii=False),
            limit=limit,
            domain_hint=domain_hint,
        )

        suggestions_payload: List[Dict[str, Any]] = []
        try:
            response = await client.chat_with_fallback(
                prompt=prompt,
                model="gemma4:e4b",
                format="json",
            )
        except Exception as exc:  # pragma: no cover — defensive
            logger.warning("ImproveService.generate_via_llm: chat raised: %s", exc)
            response = {"ok": False}

        if response.get("ok"):
            payload = response.get("suggestions") or response.get("content")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = None
            if isinstance(payload, dict):
                payload = payload.get("suggestions")
            if isinstance(payload, list):
                suggestions_payload = [s for s in payload if isinstance(s, dict)]

        # Fallback: filtered seed
        if not suggestions_payload:
            logger.info(
                "ImproveService.generate_via_llm: falling back to SEED for tenant %s",
                self.tenant_id,
            )
            seeds = (
                [s for s in SEED_SUGGESTIONS if s["domain"] == scope]
                if scope else list(SEED_SUGGESTIONS)
            )
            suggestions_payload = seeds[:limit]
            source = SuggestionSource.SEED.value
        else:
            source = SuggestionSource.LLM_GENERATED.value
            suggestions_payload = suggestions_payload[:limit]

        out: List[ImprovementSuggestion] = []
        for raw in suggestions_payload:
            sug = ImprovementSuggestion(
                tenant_id=self.tenant_id,
                title=str(raw.get("title", "Untitled"))[:255],
                description=str(raw.get("description", "")),
                domain=str(raw.get("domain", scope or "other")),
                action_type=str(raw.get("action_type", "generic")),
                estimated_impact=raw.get("estimated_impact") or {},
                confidence=float(raw.get("confidence", 0.5)),
                source=source,
                status=SuggestionStatus.PENDING.value,
            )
            self.session.add(sug)
            out.append(sug)

        if out:
            await self.session.flush()
            await self.session.commit()
            for sug in out:
                await self.session.refresh(sug)
        return out

    # ── Internal seeding ──────────────────────────────────────────────

    async def _ensure_seeded(self) -> None:
        """Insert the SEED_SUGGESTIONS into the tenant's bucket if it's
        currently empty. Idempotent — does nothing if any row already
        exists for the tenant."""
        stmt = select(func.count(ImprovementSuggestion.id)).where(
            ImprovementSuggestion.tenant_id == self.tenant_id,
        )
        existing = int((await self.session.execute(stmt)).scalar() or 0)
        if existing > 0:
            return
        for raw in SEED_SUGGESTIONS:
            sug = ImprovementSuggestion(
                tenant_id=self.tenant_id,
                title=raw["title"],
                description=raw["description"],
                domain=raw["domain"],
                action_type=raw["action_type"],
                estimated_impact=raw["estimated_impact"],
                confidence=raw["confidence"],
                source=SuggestionSource.SEED.value,
                status=SuggestionStatus.PENDING.value,
            )
            self.session.add(sug)
        await self.session.flush()
        await self.session.commit()
