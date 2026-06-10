"""Q.115.F — MarginPreview: margem prevista para um ScheduleCommit.

Calcula `predicted_margin_eur` somando, por operação do commit:
    op_margin = bonus_eur − custo_op
onde `bonus_eur` é o CoeficienteX (bónus € do PhaseBonusPayout — dinheiro)
e `custo_op = duration_h × cost_rate` (€). Margem = € − €; nunca tempo.

Baseline = daily_revenue_target mais recente × (commit_hours / 8h).

NÃO importa nada de src.plan.cpo (invariante CoeficienteX).
DurationModel via ModelRegistry — fallback para duration_p50_h da
RoutingTemplatePhase se sem modelo activo (confidence sempre "low" nesse caso).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.daily_revenue_target import DailyRevenueTarget
from src.plan.cpo.commits import ScheduleCommit
from src.plan.models.routing_template import RoutingTemplatePhase
from src.profit.models.phase_bonus import PhaseBonusPayout
from src.shared.time import local_today

log = logging.getLogger(__name__)

# Custo horário de mão-de-obra padrão (€/h) quando não existe tabela labor_rates.
# Valor NELO provisório — substituir por core.labor_rates quando disponível.
_DEFAULT_COST_RATE_EUR_H = Decimal("12.00")


@dataclass
class MarginPreview:
    schedule_commit_id: str
    predicted_margin_eur: Optional[Decimal]
    baseline_margin_eur: Optional[Decimal]
    delta_eur: Optional[Decimal]
    confidence: Literal["high", "medium", "low"]
    sample_size: int
    computed_at: datetime


async def compute_margin_preview(
    session: AsyncSession,
    tenant_id: UUID,
    commit_id_str: str,
    *,
    duration_model: Optional[Any] = None,
) -> MarginPreview:
    """Calcula a margem prevista para um ScheduleCommit.

    Levanta `ValueError("commit_not_found")` se o commit não existe.
    """
    # 1. Carrega o commit
    commit = await _load_commit(session, tenant_id, commit_id_str)
    if commit is None:
        raise ValueError("commit_not_found")

    operations: List[Dict[str, Any]] = list(commit.operations or [])
    sample_size = len(operations)
    today = local_today()

    # 2. Calcula margem prevista somando por operação
    predicted_total = Decimal("0")
    using_fallback = False

    for op in operations:
        product_id_raw = op.get("product_id")
        phase_id_raw = op.get("phase_id") or op.get("fase_id")

        # 2a. CoeficienteX (bónus € desta operação)
        bonus_eur = await _load_bonus(
            session, tenant_id, product_id_raw, phase_id_raw, today
        )

        # 2b. Duração prevista
        duration_h, fallback = await _estimate_duration(
            session, tenant_id, op, phase_id_raw, duration_model
        )
        if fallback:
            using_fallback = True

        # 2c. Custo horário — usa default até existir tabela labor_rates
        cost_rate = _DEFAULT_COST_RATE_EUR_H

        op_margin = bonus_eur - (duration_h * cost_rate)
        predicted_total += op_margin

    predicted_margin = predicted_total if sample_size > 0 else None

    # 3. Baseline via daily_revenue_target
    baseline_margin = await _compute_baseline(session, tenant_id, operations)

    # 4. Delta
    delta: Optional[Decimal] = None
    if predicted_margin is not None and baseline_margin is not None:
        delta = predicted_margin - baseline_margin

    # 5. Confidence
    confidence = _confidence(sample_size, using_fallback)

    return MarginPreview(
        schedule_commit_id=commit_id_str,
        predicted_margin_eur=predicted_margin,
        baseline_margin_eur=baseline_margin,
        delta_eur=delta,
        confidence=confidence,
        sample_size=sample_size,
        computed_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------

async def _load_commit(
    session: AsyncSession,
    tenant_id: UUID,
    commit_id_str: str,
) -> Optional[ScheduleCommit]:
    """Tenta por id (UUID) e por sha256 prefix (>=7 chars)."""
    # Tenta por UUID primeiro
    try:
        commit_uuid = UUID(commit_id_str)
        row = await session.get(ScheduleCommit, commit_uuid)
        if row is not None and row.tenant_id == tenant_id:
            return row
    except (ValueError, AttributeError):
        pass

    # Tenta por sha prefix
    if len(commit_id_str) >= 7:
        stmt = (
            select(ScheduleCommit)
            .where(
                and_(
                    ScheduleCommit.tenant_id == tenant_id,
                    ScheduleCommit.commit_sha256.like(f"{commit_id_str}%"),
                )
            )
            .limit(2)
        )
        result = await session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) == 1:
            return rows[0]

    return None


async def _load_bonus(
    session: AsyncSession,
    tenant_id: UUID,
    product_id_raw: Any,
    phase_id_raw: Any,
    ref_date: date,
) -> Decimal:
    """Devolve bonus_eur para (produto, fase) na data ref. Devolve 0 se ausente."""
    if not product_id_raw or not phase_id_raw:
        return Decimal("0")

    try:
        product_uuid = UUID(str(product_id_raw))
        phase_uuid = UUID(str(phase_id_raw))
    except (ValueError, AttributeError):
        return Decimal("0")

    stmt = (
        select(PhaseBonusPayout)
        .where(
            and_(
                PhaseBonusPayout.tenant_id == tenant_id,
                PhaseBonusPayout.product_id == product_uuid,
                PhaseBonusPayout.phase_id == phase_uuid,
                PhaseBonusPayout.valid_from <= ref_date,
            )
        )
        .order_by(desc(PhaseBonusPayout.valid_from))
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return Decimal("0")
    # Verifica validade final
    if row.valid_to is not None and row.valid_to < ref_date:
        return Decimal("0")
    return Decimal(str(row.bonus_eur))


async def _estimate_duration(
    session: AsyncSession,
    tenant_id: UUID,
    op: Dict[str, Any],
    phase_id_raw: Any,
    duration_model: Optional[Any],
) -> tuple[Decimal, bool]:
    """Devolve (duration_h, used_fallback).

    Tenta DurationModel → p50_duration se ML falhou → 1h como último recurso.
    """
    # Tenta DurationModel (já carregado pelo chamador)
    if duration_model is not None and hasattr(duration_model, "predict"):
        modelo_id = op.get("modelo_id") or op.get("model_id") or ""
        fase_id = str(phase_id_raw or "")
        team_size = int(op.get("team_size", 1) or 1)
        try:
            pred = duration_model.predict({
                "modelo_id": str(modelo_id),
                "fase_id": fase_id,
                "team_size": team_size,
                "mold_pocket_count": int(op.get("mold_pocket_count", 1) or 1),
                "is_rework": int(op.get("is_rework", 0) or 0),
                "queue_depth": int(op.get("queue_depth", 0) or 0),
            })
            p50 = pred.get("p50_hours", 0.0)
            if p50 > 0:
                return Decimal(str(round(p50, 4))), False
        except Exception as exc:
            log.debug("DurationModel.predict falhou (%s) — fallback p50", exc)

    # Fallback: duration já gravada na operação
    dur_h = op.get("duration_h") or op.get("duration_hours")
    if dur_h and float(dur_h) > 0:
        return Decimal(str(round(float(dur_h), 4))), True

    # Fallback: RoutingTemplatePhase.duration_p50_h
    if phase_id_raw:
        p50_db = await _load_template_p50(session, tenant_id, phase_id_raw)
        if p50_db is not None and p50_db > 0:
            return Decimal(str(round(float(p50_db), 4))), True

    # Último recurso: 1h
    return Decimal("1.0"), True


async def _load_template_p50(
    session: AsyncSession,
    tenant_id: UUID,
    phase_id_raw: Any,
) -> Optional[float]:
    """Lê duration_p50_h do RoutingTemplatePhase para esta fase."""
    stmt = (
        select(RoutingTemplatePhase.duration_p50_h)
        .where(
            and_(
                RoutingTemplatePhase.tenant_id == tenant_id,
                RoutingTemplatePhase.phase_id == str(phase_id_raw),
            )
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return float(row) if row else None


async def _compute_baseline(
    session: AsyncSession,
    tenant_id: UUID,
    operations: List[Dict[str, Any]],
) -> Optional[Decimal]:
    """baseline_margin_eur = daily_target × (commit_hours / 8h).

    Devolve None se não existe target definido.
    """
    today = local_today()
    stmt = (
        select(DailyRevenueTarget)
        .where(
            and_(
                DailyRevenueTarget.tenant_id == tenant_id,
                DailyRevenueTarget.effective_from <= today,
            )
        )
        .order_by(desc(DailyRevenueTarget.effective_from))
        .limit(1)
    )
    result = await session.execute(stmt)
    target_row = result.scalar_one_or_none()
    if target_row is None:
        return None

    daily_target = Decimal(str(target_row.target_eur))

    # Estima horas totais do commit (soma das durações das operações)
    commit_hours = Decimal("0")
    for op in operations:
        dur = op.get("duration_h") or op.get("duration_hours") or 0
        commit_hours += Decimal(str(float(dur or 0)))

    if commit_hours <= 0:
        # Sem horas nas operações — usa proporção neutra (1 turno = 8h)
        commit_hours = Decimal("8")

    return daily_target * (commit_hours / Decimal("8"))


def _confidence(sample_size: int, using_fallback: bool) -> Literal["high", "medium", "low"]:
    if using_fallback or sample_size < 100:
        return "low"
    if sample_size <= 500:
        return "medium"
    return "high"
