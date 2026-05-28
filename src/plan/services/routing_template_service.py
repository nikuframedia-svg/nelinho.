"""
ProdPlan ONE - Routing Template Service (Sprint P.4)
======================================================

CRUD + mining helpers for `RoutingTemplate`/`RoutingTemplatePhase`/
`ModelRoutingAssignment`. The mining job extracts the canonical 50 patterns
that cover all 899 NELO models (Blueprint v2.0 §2.3).
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any, Iterable, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.plan.models.routing_template import (
    ModelRoutingAssignment,
    RoutingTemplate,
    RoutingTemplatePhase,
)

logger = logging.getLogger(__name__)


class RoutingTemplateNotFoundError(Exception):
    pass


class RoutingTemplateService:
    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ─── CRUD ─────────────────────────────────────────────────────────────

    async def create_template(
        self,
        *,
        code: str,
        name: str,
        phases: list[dict[str, Any]],
        description: Optional[str] = None,
        model_coverage: int = 0,
    ) -> RoutingTemplate:
        existing = await self._find_by_code(code)
        if existing is not None:
            raise ValueError(f"RoutingTemplate code={code} already exists")

        template = RoutingTemplate(
            id=uuid4(),
            tenant_id=self.tenant_id,
            code=code,
            name=name,
            description=description,
            phase_count=len(phases),
            active=True,
            model_coverage=model_coverage,
        )
        self.session.add(template)
        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="routing_template",
            entity_id=template.id,
            action="INSERT",
            old_values=None,
            new_values={
                "code": code,
                "name": name,
                "phase_count": len(phases),
                "model_coverage": model_coverage,
                "active": True,
            },
            reason="Q.66.B.3 — template de routing criado",
        )
        for idx, phase in enumerate(phases, start=1):
            phase_row = RoutingTemplatePhase(
                id=uuid4(),
                tenant_id=self.tenant_id,
                template_id=template.id,
                seq=phase.get("seq", idx),
                phase_id=str(phase["phase_id"]),
                phase_name=phase.get("phase_name"),
                duration_p50_h=_as_decimal(phase.get("duration_p50_h")),
                duration_p90_h=_as_decimal(phase.get("duration_p90_h")),
                requires_mold=bool(phase.get("requires_mold", False)),
                team_size_default=int(phase.get("team_size_default", 1) or 1),
                can_skip=bool(phase.get("can_skip", False)),
                alternative_group_id=phase.get("alternative_group_id"),
            )
            self.session.add(phase_row)
            await audit_change(
                self.session,
                tenant_id=self.tenant_id,
                entity_type="routing_template_phase",
                entity_id=phase_row.id,
                action="INSERT",
                old_values=None,
                new_values={
                    "template_id": str(template.id),
                    "seq": phase_row.seq,
                    "phase_id": phase_row.phase_id,
                    "requires_mold": phase_row.requires_mold,
                    "can_skip": phase_row.can_skip,
                },
                reason="Q.66.B.3 — fase de template de routing criada",
            )
        await self.session.flush()
        return template

    async def get_template(self, template_id: UUID) -> RoutingTemplate:
        stmt = select(RoutingTemplate).where(
            and_(
                RoutingTemplate.tenant_id == self.tenant_id,
                RoutingTemplate.id == template_id,
            )
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise RoutingTemplateNotFoundError(str(template_id))
        return row

    async def list_templates(self, *, active_only: bool = True) -> list[RoutingTemplate]:
        stmt = select(RoutingTemplate).where(
            RoutingTemplate.tenant_id == self.tenant_id,
        )
        if active_only:
            stmt = stmt.where(RoutingTemplate.active.is_(True))
        stmt = stmt.order_by(RoutingTemplate.model_coverage.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def template_phases(self, template_id: UUID) -> list[RoutingTemplatePhase]:
        stmt = (
            select(RoutingTemplatePhase)
            .where(
                and_(
                    RoutingTemplatePhase.tenant_id == self.tenant_id,
                    RoutingTemplatePhase.template_id == template_id,
                )
            )
            .order_by(RoutingTemplatePhase.seq)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def assign_model(
        self,
        *,
        model_id: str,
        primary_template_id: UUID,
        alt_template_id: Optional[UUID] = None,
    ) -> ModelRoutingAssignment:
        stmt = select(ModelRoutingAssignment).where(
            and_(
                ModelRoutingAssignment.tenant_id == self.tenant_id,
                ModelRoutingAssignment.model_id == model_id,
            )
        )
        existing = (await self.session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            existing.primary_template_id = primary_template_id
            existing.alt_template_id = alt_template_id
            await self.session.flush()
            return existing

        row = ModelRoutingAssignment(
            id=uuid4(),
            tenant_id=self.tenant_id,
            model_id=model_id,
            primary_template_id=primary_template_id,
            alt_template_id=alt_template_id,
        )
        self.session.add(row)
        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="model_routing_assignment",
            entity_id=row.id,
            action="INSERT",
            old_values=None,
            new_values={
                "model_id": model_id,
                "primary_template_id": str(primary_template_id),
                "alt_template_id": str(alt_template_id) if alt_template_id else None,
            },
            reason="Q.66.B.3 — atribuicao de routing a modelo",
        )
        await self.session.flush()
        return row

    async def resolve_for_model(
        self,
        *,
        model_id: str,
        variant: str = "A",
    ) -> Optional[UUID]:
        """Return the template_id to use given the chromosome's variant."""
        stmt = select(ModelRoutingAssignment).where(
            and_(
                ModelRoutingAssignment.tenant_id == self.tenant_id,
                ModelRoutingAssignment.model_id == model_id,
            )
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        if variant == "B" and row.alt_template_id is not None:
            return row.alt_template_id
        return row.primary_template_id

    async def _find_by_code(self, code: str) -> Optional[RoutingTemplate]:
        stmt = select(RoutingTemplate).where(
            and_(
                RoutingTemplate.tenant_id == self.tenant_id,
                RoutingTemplate.code == code,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    # ─── Q.116.B — phase editor ──────────────────────────────────────────

    async def update_phase_sequence(
        self,
        *,
        template_id: UUID,
        new_order: List[UUID],
        actor: Optional[UUID] = None,
    ) -> List[RoutingTemplatePhase]:
        """Reordena fases de um template — reindexa `seq` 1..N atomicamente.

        `new_order` e a lista de phase row IDs na nova sequencia. Tem de
        cobrir EXACTAMENTE as fases actuais do template (mesmas IDs, sem
        extras nem faltas). Escreve uma audit row `UPDATE` com a ordem
        antiga e a nova como listas de phase IDs.

        Levanta:
            RoutingTemplateNotFoundError: template inexistente.
            ValueError: `new_order` nao bate certo com o set de fases
                actuais — protege contra reorders de templates parciais.
        """
        # 1. Garante que o template existe e pertence ao tenant.
        await self.get_template(template_id)

        # 2. Carrega fases actuais ordenadas pelo seq actual.
        current = await self.template_phases(template_id)
        current_ids = {p.id for p in current}
        requested_ids = set(new_order)
        if requested_ids != current_ids or len(new_order) != len(current):
            raise ValueError(
                "new_order tem de cobrir exactamente as fases do template "
                f"(esperadas={len(current)} ids, recebidas={len(new_order)} ids)"
            )

        # 3. Indexa fases por id para reordenar in-place.
        by_id = {p.id: p for p in current}
        old_order = [str(p.id) for p in current]

        # 4. Reescreve seq 1..N segundo a nova ordem.
        reordered: List[RoutingTemplatePhase] = []
        for idx, pid in enumerate(new_order, start=1):
            phase = by_id[pid]
            phase.seq = idx
            reordered.append(phase)

        await self.session.flush()

        # 5. Audit na mesma tx.
        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="routing_template",
            entity_id=template_id,
            action="UPDATE",
            old_values={"phase_order": old_order},
            new_values={"phase_order": [str(pid) for pid in new_order]},
            actor_id=actor,
            reason="reorder_phases",
        )

        return reordered

    async def set_flexible(
        self,
        *,
        phase_row_id: UUID,
        is_flexible: bool,
        allowed_predecessors: List[str],
        actor: Optional[UUID] = None,
    ) -> RoutingTemplatePhase:
        """Marca uma fase como posicao alternativa.

        Regras:
          * `is_flexible=True` exige `allowed_predecessors` com pelo
            menos 1 phase_id e sem duplicados.
          * `is_flexible=False` exige `allowed_predecessors` vazia e
            limpa o campo para `NULL` no DB (a fase volta a posicao fixa).

        Levanta:
            ValueError: combinacao invalida (vazia + flexivel, duplicados,
                nao-vazia + nao-flexivel).
            RoutingTemplateNotFoundError: phase row inexistente para este
                tenant.
        """
        # 1. Validacao de combinacao antes de tocar na DB.
        if is_flexible:
            if not allowed_predecessors:
                raise ValueError(
                    "is_flexible=True exige pelo menos 1 phase_id em "
                    "allowed_predecessors"
                )
            if len(set(allowed_predecessors)) != len(allowed_predecessors):
                raise ValueError(
                    "allowed_predecessors tem duplicados"
                )
        else:
            if allowed_predecessors:
                raise ValueError(
                    "is_flexible=False exige allowed_predecessors vazia "
                    "(a fase volta a posicao fixa)"
                )

        # 2. SELECT phase por (tenant_id, id).
        stmt = select(RoutingTemplatePhase).where(
            and_(
                RoutingTemplatePhase.tenant_id == self.tenant_id,
                RoutingTemplatePhase.id == phase_row_id,
            )
        )
        phase = (await self.session.execute(stmt)).scalar_one_or_none()
        if phase is None:
            raise RoutingTemplateNotFoundError(str(phase_row_id))

        old_vals = {
            "is_flexible": phase.is_flexible,
            "allowed_predecessors": list(phase.allowed_predecessors)
            if phase.allowed_predecessors is not None
            else None,
        }

        phase.is_flexible = is_flexible
        phase.allowed_predecessors = (
            list(allowed_predecessors) if is_flexible else None
        )

        await self.session.flush()

        await audit_change(
            self.session,
            tenant_id=self.tenant_id,
            entity_type="routing_template_phase",
            entity_id=phase.id,
            action="UPDATE",
            old_values=old_vals,
            new_values={
                "is_flexible": phase.is_flexible,
                "allowed_predecessors": phase.allowed_predecessors,
            },
            actor_id=actor,
            reason="set_flexible_phase",
        )

        return phase


# ---------------------------------------------------------------------------
# Mining — extracts canonical routing patterns from curated history
# ---------------------------------------------------------------------------

def mine_routing_patterns(
    phase_sequences_by_model: dict[str, list[list[str]]],
    *,
    top_n: int = 50,
    min_frequency: int = 3,
) -> list[dict[str, Any]]:
    """Extract the `top_n` most common phase sequences.

    Args:
        phase_sequences_by_model:
            `{model_id: [phase_sequence_per_order, …]}`. Each phase_sequence
            is a list of `phase_id` strings in execution order.
        top_n: cap the result (default 50 per Blueprint v2.0 §2.3).
        min_frequency: pattern must appear at least this many times.

    Returns a list of pattern dicts ordered by coverage (most models first):
        [
          {
            "code": "ROUTING-0001",
            "phase_sequence": ["phase_1", …],
            "model_ids": ["K1-Vanquish-L-SCS", …],
            "model_coverage": 219,
            "occurrence_count": 4512,
          },
          …
        ]

    Ties on coverage are broken by frequency, then by canonical hash for
    deterministic ordering across runs.
    """
    pattern_counter: Counter[tuple[str, ...]] = Counter()
    models_by_pattern: dict[tuple[str, ...], set[str]] = defaultdict(set)

    for model_id, sequences in phase_sequences_by_model.items():
        for seq in sequences:
            key = tuple(seq)
            if not key:
                continue
            pattern_counter[key] += 1
            models_by_pattern[key].add(model_id)

    # Filter by frequency and rank.
    filtered = [
        (pattern, count) for pattern, count in pattern_counter.items()
        if count >= min_frequency
    ]
    filtered.sort(
        key=lambda kv: (
            -len(models_by_pattern[kv[0]]),
            -kv[1],
            _pattern_hash(kv[0]),
        )
    )

    results: list[dict[str, Any]] = []
    for idx, (pattern, count) in enumerate(filtered[:top_n], start=1):
        code = f"ROUTING-{idx:04d}"
        results.append({
            "code": code,
            "phase_sequence": list(pattern),
            "model_ids": sorted(models_by_pattern[pattern]),
            "model_coverage": len(models_by_pattern[pattern]),
            "occurrence_count": count,
        })
    return results


def _pattern_hash(pattern: Iterable[str]) -> str:
    return hashlib.sha256("|".join(pattern).encode("utf-8")).hexdigest()


def _as_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:  # pragma: no cover — defensive
        return None
