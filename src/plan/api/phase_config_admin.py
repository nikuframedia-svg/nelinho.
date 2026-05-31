"""Q.135.F3.2 — endpoints de config de fase para o CPO.

GET  /v1/plan/phases/{phase_id}/config
  Devolve overrides actuais + baselines READ para a UI:
    - operadores com skill (skill_matrix + afinidade)
    - nº de estações sugerido (p95 derive_phase_stations)
    - team_size default
    - duração esperada do histórico (median_duration_h / calibração)
    - rank canónico (NELO_PHASE_ORDER) + fases típicas antes/depois

PUT  /v1/plan/phases/{phase_id}/config
  Upsert dos overrides. RBAC ROUTING_EDIT. Audit.
  Validações Spelke → 400 se violado.

Padrão: ver routing_template_admin.py (audit_change na mesma tx, _actor_uuid,
ROUTING_EDIT, sem commit na route — boundary no get_session).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.services.phase_config_service import PhaseConfigService, _N_MAX
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/plan/phases",
    tags=["Q.135 Phase Config"],
)

_require_routing_edit = PermissionDependency([Permission.ROUTING_EDIT])


def _actor_uuid(user_id: str) -> Optional[UUID]:
    try:
        return UUID(user_id)
    except (ValueError, TypeError):
        return None


# ─── Schemas ─────────────────────────────────────────────────────────────────


class PhaseConfigOverrides(BaseModel):
    team_size_override: Optional[int] = Field(
        None, ge=1, description="Nº de operadores por op (NULL = baseline)"
    )
    num_stations_override: Optional[int] = Field(
        None, ge=1, le=_N_MAX, description="Nº estações paralelas (NULL = p95 ERP)"
    )
    allowed_worker_ids: Optional[List[str]] = Field(
        None, description="Whitelist de funcionario_id (NULL = todos os competentes)"
    )
    note: Optional[str] = Field(None, max_length=500)


class PhaseConfigBaselines(BaseModel):
    capable_worker_ids: List[str] = Field(
        description="Operadores com skill nesta fase (de offp_eq)"
    )
    affinity_worker_ids: List[str] = Field(
        description="Operadores com afinidade registada (governance.phase_operator_affinity)"
    )
    suggested_stations: int = Field(
        description="N estações sugeridas pelo p95 da concorrência real"
    )
    team_size_default: int = Field(
        description="Team size padrão do routing template (1 na maioria das fases)"
    )
    expected_duration_h: Optional[float] = Field(
        None, description="Duração esperada em horas (do histórico real ou calibração)"
    )
    canonical_rank: Optional[int] = Field(
        None, description="Posição canónica da fase no NELO_PHASE_ORDER"
    )
    typical_prev_phase: Optional[str] = Field(
        None, description="Fase anterior típica na sequência canónica"
    )
    typical_next_phase: Optional[str] = Field(
        None, description="Fase seguinte típica na sequência canónica"
    )


class PhaseConfigOut(BaseModel):
    phase_id: str
    overrides: PhaseConfigOverrides
    baselines: PhaseConfigBaselines


class PhaseConfigIn(PhaseConfigOverrides):
    """Body do PUT — mesmos campos que os overrides."""


# ─── helpers de baseline ────────────────────────────────────────────────────


async def _get_baselines(
    session: AsyncSession,
    tenant_id: UUID,
    phase_id: str,
) -> PhaseConfigBaselines:
    """Recolhe dados de baseline sem hits extras à BD (reutiliza loaders existentes)."""
    capable: List[str] = []
    affinity: List[str] = []
    stations = 1
    team_size_default = 1
    expected_h: Optional[float] = None
    canonical_rank: Optional[int] = None
    typical_prev: Optional[str] = None
    typical_next: Optional[str] = None
    # Q.135 fix — OFFP_FP_ID / FP_ID são INTEIROS no ERP; o phase_id chega como
    # string ("18"). Ligar como texto a uma coluna integer rebenta no asyncpg
    # (sem cast implícito text→int) → o except engolia tudo e dava null. Quando
    # o phase_id é numérico, liga-se como int.
    phase_int: Optional[int] = int(phase_id) if str(phase_id).isdigit() else None

    # 1. skill_matrix: operadores com skill real (factory_raw.offp_eq)
    try:
        from src.plan.cpo.state import _load_skills_db
        skill_matrix = await _load_skills_db(session, tenant_id)
        capable = sorted(skill_matrix.get(phase_id, set()))
    except Exception as exc:
        logger.debug("baselines: skill_matrix load skipped: %s", exc)

    # 2. afinidade (governance.phase_operator_affinity) — best-effort
    try:
        aff_sql = text(
            "SELECT DISTINCT employee_id::text AS eid "
            "FROM governance.phase_operator_affinity "
            "WHERE tenant_id = :tenant AND phase_id = :phase"
        )
        rows = (await session.execute(
            aff_sql, {"tenant": str(tenant_id), "phase": phase_id}
        )).mappings().all()
        affinity = sorted(str(r["eid"]) for r in rows)
    except Exception as exc:
        logger.debug("baselines: affinity load skipped: %s", exc)

    # 3. N estações sugeridas (p95 concorrência real)
    try:
        from src.plan.services.phase_workcenters import derive_phase_stations
        ps = await derive_phase_stations(session, tenant_id)
        if phase_id in ps:
            stations = ps[phase_id]
    except Exception as exc:
        logger.debug("baselines: phase_stations load skipped: %s", exc)

    # 4. team_size_default: routing_template_phase (geralmente 1 hoje)
    try:
        ts_sql = text(
            "SELECT COALESCE(MAX(rtp.team_size_default), 1) AS ts "
            "FROM plan.routing_template_phase rtp "
            "JOIN plan.model_routing_assignment mra "
            "  ON mra.primary_template_id = rtp.template_id "
            "WHERE mra.tenant_id = :tenant AND rtp.phase_id = :phase "
            "  AND rtp.tenant_id = :tenant"
        )
        ts_row = (await session.execute(
            ts_sql, {"tenant": str(tenant_id), "phase": phase_id}
        )).mappings().one_or_none()
        if ts_row:
            team_size_default = int(ts_row["ts"] or 1)
    except Exception as exc:
        logger.debug("baselines: team_size_default load skipped: %s", exc)

    # 5. duração esperada (calibração > mediana crua)
    try:
        from src.plan.cpo.state import (
            _load_phase_calibration_db,
            _load_historical_durations_routes_db,
            _CALIBRATION_MIN_OBS,
        )
        cal = await _load_phase_calibration_db(session, tenant_id)
        # escolhe o melhor valor calibrado disponível para qualquer modelo desta fase
        best_h: Optional[float] = None
        for (fid, _mid), (h, n_obs) in cal.items():
            if fid == phase_id and n_obs >= _CALIBRATION_MIN_OBS and h > 0:
                if best_h is None or h < best_h:
                    best_h = h
        if best_h is None:
            # Fonte AUTORITATIVA: a mesma mediana-por-fase do histórico real que o
            # CPO usa (state.historical_durations_by_fase) — lida com as datas-texto
            # do ERP de forma robusta, ao contrário de uma query inline frágil.
            _routes, _pair, by_fase = await _load_historical_durations_routes_db(
                session, tenant_id
            )
            v = by_fase.get(str(phase_id))
            if v and float(v) > 0:
                best_h = round(float(v), 2)
        expected_h = best_h
    except Exception as exc:
        logger.debug("baselines: expected_duration load skipped: %s", exc)

    # 6. rank canónico + fases antes/depois
    try:
        from src.plan.services.phase_classification import NELO_PHASE_ORDER, _norm
        # phase_id numérico → nome via fases_producao (FP_ID é INT); senão o
        # próprio phase_id já é o nome da fase.
        pn = ""
        if phase_int is not None:
            phase_name_sql = text(
                'SELECT "FP_NOME" AS nome FROM factory_raw.fases_producao '
                'WHERE "FP_ID" = :phase LIMIT 1'
            )
            pn_row = (await session.execute(
                phase_name_sql, {"phase": phase_int}
            )).one_or_none()
            if pn_row:
                pn = str(pn_row[0] or "")
        else:
            pn = str(phase_id)
        if pn:
            canonical_rank = NELO_PHASE_ORDER.get(_norm(pn))

        if canonical_rank is not None:
            inv: Dict[int, str] = {v: k for k, v in NELO_PHASE_ORDER.items()}
            prev_rank = canonical_rank - 1
            next_rank = canonical_rank + 1
            typical_prev = inv.get(prev_rank)
            typical_next = inv.get(next_rank)
    except Exception as exc:
        logger.debug("baselines: canonical_rank load skipped: %s", exc)

    return PhaseConfigBaselines(
        capable_worker_ids=capable,
        affinity_worker_ids=affinity,
        suggested_stations=stations,
        team_size_default=team_size_default,
        expected_duration_h=expected_h,
        canonical_rank=canonical_rank,
        typical_prev_phase=typical_prev,
        typical_next_phase=typical_next,
    )


def _overrides_from_row(row: Any) -> PhaseConfigOverrides:
    if row is None:
        return PhaseConfigOverrides()
    return PhaseConfigOverrides(
        team_size_override=row.team_size_override,
        num_stations_override=row.num_stations_override,
        allowed_worker_ids=row.allowed_worker_ids,
        note=row.note,
    )


# ─── GET /v1/plan/phases/{phase_id}/config ──────────────────────────────────


@router.get(
    "/{phase_id}/config",
    response_model=PhaseConfigOut,
    status_code=status.HTTP_200_OK,
)
async def get_phase_config(
    phase_id: str,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> PhaseConfigOut:
    """Overrides actuais + baselines da fase (READ-ONLY)."""
    svc = PhaseConfigService(session, tenant_id)
    row = await svc.get(phase_id)
    baselines = await _get_baselines(session, tenant_id, phase_id)
    return PhaseConfigOut(
        phase_id=phase_id,
        overrides=_overrides_from_row(row),
        baselines=baselines,
    )


# ─── PUT /v1/plan/phases/{phase_id}/config ──────────────────────────────────


@router.put(
    "/{phase_id}/config",
    response_model=PhaseConfigOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_routing_edit)],
)
async def put_phase_config(
    phase_id: str,
    body: PhaseConfigIn,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> PhaseConfigOut:
    """Upsert dos overrides de fase. Validações Spelke → 400 se violado."""
    # Para validar allowed_worker_ids ⊆ skill_matrix precisamos do skill_matrix
    known_workers: Optional[set] = None
    if body.allowed_worker_ids is not None:
        try:
            from src.plan.cpo.state import _load_skills_db
            skill_matrix = await _load_skills_db(session, tenant_id)
            known_workers = skill_matrix.get(phase_id, set())
        except Exception as exc:
            logger.warning("put_phase_config: skill_matrix load failed: %s", exc)

    # Para validação PAIR fase name
    phase_name = ""
    try:
        pn_sql = text(
            'SELECT "FP_NOME" AS nome FROM factory_raw.fases_producao '
            'WHERE "FP_ID" = :phase LIMIT 1'
        )
        pn_row = (await session.execute(pn_sql, {"phase": phase_id})).one_or_none()
        if pn_row:
            phase_name = str(pn_row[0] or "")
    except Exception as exc:  # best-effort — nome da fase não é crítico para validação
        logger.debug("put_phase_config: phase_name lookup skipped: %s", exc)

    svc = PhaseConfigService(session, tenant_id)
    try:
        row = await svc.upsert(
            phase_id=phase_id,
            team_size_override=body.team_size_override,
            num_stations_override=body.num_stations_override,
            allowed_worker_ids=body.allowed_worker_ids,
            note=body.note,
            actor=_actor_uuid(user_id),
            known_workers=known_workers,
            phase_name=phase_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    baselines = await _get_baselines(session, tenant_id, phase_id)
    return PhaseConfigOut(
        phase_id=phase_id,
        overrides=_overrides_from_row(row),
        baselines=baselines,
    )
