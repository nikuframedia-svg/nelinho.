"""Q.155.B — "Melhores operadores por fase" (curado manual).

GET  /v1/plan/phases/{phase_id}/preferred-operators
  Lista curada (ordenada por rank) + sugestões (afinidade histórica com
  shrinkage) + flag is_capable por operador. READ.

PUT  /v1/plan/phases/{phase_id}/preferred-operators
  Substitui a lista curada (replace-all, ordem = rank). RBAC ROUTING_EDIT +
  audit_change na mesma tx. employee_code = E_ID do ERP (identidade do decoder).

Padrão: phase_config_admin.py (ROUTING_EDIT, audit, sem commit na route).
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.governance.audit_service import audit_change
from src.shared.auth.headers import require_tenant_header, require_user_header
from src.shared.auth.rbac import Permission, PermissionDependency
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/plan/phases", tags=["Q.155 Melhores por fase"])

_require_routing_edit = PermissionDependency([Permission.ROUTING_EDIT])

# Shrinkage Bayesiano: afinidade de poucas amostras é puxada p/ o neutro (0.5).
# Sem isto um operador de 5 ops saturava em 1.0 acima de um de 600 (flaw real).
_SHRINK_PRIOR = 0.5
_SHRINK_K = 20.0
_N_SUGGESTIONS = 8


def _actor_uuid(user_id: str) -> Optional[UUID]:
    try:
        return UUID(user_id)
    except (ValueError, TypeError):
        return None


def _phase_entity_id(phase_id: str) -> UUID:
    """UUID determinístico p/ auditar a lista de uma fase (entidade composta)."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"phase_preferred_operator:{phase_id}")


def _shrink(score: float, n: int) -> float:
    return (score * n + _SHRINK_PRIOR * _SHRINK_K) / (n + _SHRINK_K)


# ─── Q.163 — Catálogo canónico de fases (ordem FP_SEQUENCIA) ──────────────────

class PhaseCatalogItem(BaseModel):
    """Uma fase de produção do ERP (`factory_raw.fases_producao`)."""
    phase_id: str
    phase_name: str
    sequence: int
    is_production: bool


_PHASE_CATALOG_SQL = text(
    """
    SELECT "FP_ID"::text     AS phase_id,
           "FP_NOME"         AS phase_name,
           "FP_SEQUENCIA"    AS sequence,
           "FP_PRODUCAO"     AS is_production
    FROM factory_raw.fases_producao
    ORDER BY "FP_SEQUENCIA", "FP_ID"
    """
)


@router.get("/catalog", response_model=List[PhaseCatalogItem])
async def list_phase_catalog(
    _tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[PhaseCatalogItem]:
    """Q.163 — catálogo canónico de fases (`factory_raw.fases_producao`) ordenado
    por `FP_SEQUENCIA`. O /overall usa-o para mostrar a vista "Por Fase" pela ORDEM
    REAL de produção (em vez de alfabético por id) e rotular com o nome canónico.
    `factory_raw` é partilhado → sem filtro de tenant. Best-effort → [] se falhar.
    """
    try:
        rows = (await session.execute(_PHASE_CATALOG_SQL)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — tabela ausente/dev
        logger.warning("phase catalog query failed: %s", exc)
        return []
    return [
        PhaseCatalogItem(
            phase_id=str(r["phase_id"]),
            phase_name=str(r["phase_name"] or r["phase_id"]),
            sequence=int(r["sequence"]) if r["sequence"] is not None else 0,
            is_production=bool(r["is_production"]),
        )
        for r in rows
    ]


# ─── Schemas ─────────────────────────────────────────────────────────────────


class PreferredOperatorItem(BaseModel):
    employee_code: str
    employee_name: str
    rank: int
    note: Optional[str] = None
    is_capable: bool


class SuggestionItem(BaseModel):
    employee_code: str
    employee_name: str
    score: float = Field(description="Afinidade com shrinkage [0,1]")
    sample_count: int
    is_capable: bool


class PreferredOperatorsOut(BaseModel):
    phase_id: str
    curated: List[PreferredOperatorItem]
    suggestions: List[SuggestionItem]


class PhaseListItem(BaseModel):
    phase_id: str
    phase_name: str


class PreferredOperatorIn(BaseModel):
    employee_code: str
    note: Optional[str] = Field(None, max_length=500)


class PreferredOperatorsPut(BaseModel):
    operators: List[PreferredOperatorIn] = Field(
        default_factory=list,
        description="Lista ordenada (rank = posição+1). Lista vazia limpa a curadoria.",
    )


# ─── helpers ─────────────────────────────────────────────────────────────────


async def _capable_codes(session: AsyncSession, tenant_id: UUID, phase_id: str) -> set:
    """employee_codes com skill real nesta fase (skill_matrix do CPO)."""
    try:
        from src.plan.cpo.state import _load_skills_db

        skill_matrix = await _load_skills_db(session, tenant_id)
        return set(skill_matrix.get(phase_id, set()))
    except Exception as exc:  # best-effort — sem skill_matrix, ninguém marcado capaz
        logger.debug("preferred-operators: skill_matrix load skipped: %s", exc)
        return set()


async def _build_out(
    session: AsyncSession, tenant_id: UUID, phase_id: str
) -> PreferredOperatorsOut:
    capable = await _capable_codes(session, tenant_id, phase_id)

    # 1. curada (ordenada por rank) — nome via core.employees por código
    curated_rows = (
        await session.execute(
            text(
                """
                SELECT ppo.employee_code AS code, ppo.rank AS rank, ppo.note AS note,
                       COALESCE(e.employee_name, ppo.employee_code) AS name
                FROM governance.phase_preferred_operator ppo
                LEFT JOIN core.employees e
                  ON e.employee_code = ppo.employee_code AND e.tenant_id = ppo.tenant_id
                WHERE ppo.tenant_id = :t AND ppo.phase_id = :p
                ORDER BY ppo.rank
                """
            ),
            {"t": str(tenant_id), "p": phase_id},
        )
    ).mappings().all()
    curated = [
        PreferredOperatorItem(
            employee_code=str(r["code"]),
            employee_name=str(r["name"]),
            rank=int(r["rank"]),
            note=r["note"],
            is_capable=str(r["code"]) in capable,
        )
        for r in curated_rows
    ]
    curated_codes = {c.employee_code for c in curated}

    # 2. sugestões = afinidade (operator_id = Employee.id) com shrinkage, exclui curados
    aff_rows = (
        await session.execute(
            text(
                """
                SELECT e.employee_code AS code,
                       COALESCE(e.employee_name, e.employee_code) AS name,
                       a.score AS score, a.sample_count AS n
                FROM governance.phase_operator_affinity a
                JOIN core.employees e ON e.id = a.operator_id
                WHERE a.tenant_id = :t AND a.phase_id = :p
                """
            ),
            {"t": str(tenant_id), "p": phase_id},
        )
    ).mappings().all()
    scored = sorted(
        (
            (
                str(r["code"]),
                str(r["name"]),
                _shrink(float(r["score"]), int(r["n"] or 0)),
                int(r["n"] or 0),
            )
            for r in aff_rows
            if str(r["code"]) not in curated_codes
        ),
        key=lambda t: (-t[2], t[0]),
    )
    suggestions = [
        SuggestionItem(
            employee_code=code,
            employee_name=name,
            score=round(shrunk, 4),
            sample_count=n,
            is_capable=code in capable,
        )
        for (code, name, shrunk, n) in scored[:_N_SUGGESTIONS]
    ]

    return PreferredOperatorsOut(phase_id=phase_id, curated=curated, suggestions=suggestions)


# ─── GET (lista de fases de produção, para o seletor) ────────────────────────


@router.get("", response_model=List[PhaseListItem], status_code=status.HTTP_200_OK)
async def list_production_phases(
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> List[PhaseListItem]:
    """Fases de produção (FP_PRODUCAO=true) — id + nome, para o seletor."""
    try:
        rows = (
            await session.execute(
                text(
                    'SELECT "FP_ID"::text AS id, "FP_NOME" AS name '
                    "FROM factory_raw.fases_producao "
                    'WHERE "FP_PRODUCAO" = true ORDER BY "FP_NOME"'
                )
            )
        ).mappings().all()
    except Exception as exc:  # dev sem factory_raw → lista vazia (UI mostra empty)
        logger.debug("list_production_phases skipped: %s", exc)
        return []
    return [
        PhaseListItem(phase_id=str(r["id"]), phase_name=str(r["name"] or r["id"]))
        for r in rows
    ]


# ─── GET (melhores de uma fase) ──────────────────────────────────────────────


@router.get(
    "/{phase_id}/preferred-operators",
    response_model=PreferredOperatorsOut,
    status_code=status.HTTP_200_OK,
)
async def get_preferred_operators(
    phase_id: str,
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> PreferredOperatorsOut:
    return await _build_out(session, tenant_id, phase_id)


# ─── PUT (replace-all) ───────────────────────────────────────────────────────


@router.put(
    "/{phase_id}/preferred-operators",
    response_model=PreferredOperatorsOut,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_require_routing_edit)],
)
async def put_preferred_operators(
    phase_id: str,
    body: PreferredOperatorsPut,
    tenant_id: UUID = Depends(require_tenant_header),
    user_id: str = Depends(require_user_header),
    session: AsyncSession = Depends(get_session),
) -> PreferredOperatorsOut:
    actor = _actor_uuid(user_id)

    # snapshot antigo (para o audit)
    old = (
        await session.execute(
            text(
                "SELECT employee_code, rank FROM governance.phase_preferred_operator "
                "WHERE tenant_id = :t AND phase_id = :p ORDER BY rank"
            ),
            {"t": str(tenant_id), "p": phase_id},
        )
    ).mappings().all()
    old_codes = [str(r["employee_code"]) for r in old]

    # replace-all: apaga e reinsere com rank = posição+1 (dedup preservando ordem)
    await session.execute(
        text(
            "DELETE FROM governance.phase_preferred_operator "
            "WHERE tenant_id = :t AND phase_id = :p"
        ),
        {"t": str(tenant_id), "p": phase_id},
    )
    seen: set = set()
    new_codes: List[str] = []
    rank = 0
    for item in body.operators:
        code = str(item.employee_code).strip()
        if not code or code in seen:
            continue
        seen.add(code)
        rank += 1
        new_codes.append(code)
        await session.execute(
            text(
                """
                INSERT INTO governance.phase_preferred_operator
                    (tenant_id, phase_id, employee_code, rank, note, set_by, set_at)
                VALUES (:t, :p, :code, :rank, :note, :actor, now())
                """
            ),
            {
                "t": str(tenant_id),
                "p": phase_id,
                "code": code,
                "rank": rank,
                "note": item.note,
                "actor": str(actor) if actor else None,
            },
        )

    await audit_change(
        session,
        tenant_id=tenant_id,
        entity_type="phase_preferred_operator",
        entity_id=_phase_entity_id(phase_id),
        action="UPDATE",
        old_values={"phase_id": phase_id, "operators": old_codes},
        new_values={"phase_id": phase_id, "operators": new_codes},
        actor_id=actor,
        reason=f"Melhores operadores da fase {phase_id} actualizados",
    )

    return await _build_out(session, tenant_id, phase_id)
