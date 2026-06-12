"""Q.67.6.B2 — sub-router para `/operations/{id}/worker-pairs` (Sprint Q.13.A).

Endpoint:
* GET /operations/{operation_id}/worker-pairs — top-N pair candidates.

Plan v4 §6.2 promises the manager sees alternative worker pairs BEFORE
confirming an assignment, with scores. This endpoint backs the
`<WorkerPairCard>` component on DragDropPlanner.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.plan.api._cpo_common import _tenant_id
from src.plan.cpo.commits import CommitsService
from src.plan.cpo.state import FactoryState
from src.shared.database import get_session

router = APIRouter()


# =============================================================================
# Response schemas
# =============================================================================

class WorkerPairItem(BaseModel):
    """One ranked pair candidate. The frontend §6.2 promise renders these
    side-by-side with their score so the manager sees, e.g.:

    "Paulo Gomes + Maria Silva (8.2) OU João Costa + Ana Reis (6.1)"
    """
    chefe_id: str = Field(..., description="ERP employee_id of the team leader")
    partner_id: Optional[str] = Field(
        default=None,
        description="ERP employee_id of the partner (null for solo fallback "
                    "in PREFERRED-only phases like Laminagem post-Q.8)",
    )
    score: float = Field(
        ..., ge=0.0, le=10.0,
        description="Display score 0-10 (higher is better). 10 = lowest cost "
                    "in the pool; 0 = highest cost. Rounded to 0.1.",
    )


class WorkerPairsResponse(BaseModel):
    operation_id: str
    phase_id: Optional[str] = None
    needs_pair: bool = Field(
        ..., description="True iff the phase is in PAIR_REQUIRED or "
                          "PAIR_PREFERRED — when False, the response is empty.",
    )
    pairs: List[WorkerPairItem]


# =============================================================================
# GET /operations/{operation_id}/worker-pairs (Sprint Q.13.A)
# =============================================================================

@router.get(
    "/operations/{operation_id}/worker-pairs",
    response_model=WorkerPairsResponse,
)
async def get_worker_pairs(
    operation_id: str,
    top_n: int = Query(default=3, ge=1, le=10),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Sprint Q.13.A — top-N pair candidates for an op.

    Plan v4 §6.2 promises the manager sees alternative worker pairs
    BEFORE confirming an assignment, with scores. This endpoint backs
    the `<WorkerPairCard>` component on DragDropPlanner.

    Resolves the op from the latest ScheduleCommit (so the operator
    is choosing between alternatives for an already-planned op, not
    a hypothetical one). The phase + skill pool are read from the
    loaded `FactoryState`. Returns `needs_pair=False` + empty pairs
    list when the op's phase doesn't need a pair (the frontend then
    renders the single-worker UI).
    """
    state = await FactoryState.load(db, tenant_id)
    commits = CommitsService(db, tenant_id)
    parent = await commits.get_latest()
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="no schedule commit yet — run /v1/plan/cpo/schedule first",
        )

    target_op = None
    for op_dict in (parent.operations or []):
        if str(op_dict.get("operation_id") or "") == operation_id:
            target_op = op_dict
            break
    if target_op is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"operation_id {operation_id!r} not found in latest commit",
        )

    # Build a thin SchedulingOperation just for pair_assignment lookup —
    # we only need phase_id + operation_id, not the full op.
    from src.plan.cpo.pair_assignment import (
        needs_pair_assignment,
        rank_pairs,
    )
    from src.plan.engines.scheduling_adapter import SchedulingOperation

    op = SchedulingOperation(
        operation_id=operation_id,
        order_id=str(target_op.get("order_id") or ""),
        product_id=str(target_op.get("product_id") or ""),
        sequence=int(target_op.get("sequence") or 0),
        operation_code=str(target_op.get("operation_code") or ""),
        duration_minutes=float(target_op.get("duration_minutes") or 0),
        machine_id=target_op.get("machine_id"),
        phase_id=str(target_op.get("phase_id") or ""),
    )

    needs = needs_pair_assignment(op, state)
    if not needs:
        return WorkerPairsResponse(
            operation_id=operation_id,
            phase_id=op.phase_id,
            needs_pair=False,
            pairs=[],
        )

    ranked = rank_pairs(op, state, top_n=top_n)
    return WorkerPairsResponse(
        operation_id=operation_id,
        phase_id=op.phase_id,
        needs_pair=True,
        pairs=[
            WorkerPairItem(
                chefe_id=str(p["chefe_id"]),
                partner_id=str(p["partner_id"]) if p["partner_id"] else None,
                score=float(p["score"]),
            )
            for p in ranked
        ],
    )


# =============================================================================
# GET /operations/{operation_id}/explain (Q.174.F8)
# =============================================================================

@router.get("/operations/{operation_id}/explain")
async def explain_operation(
    operation_id: str,
    sha: Optional[str] = Query(
        default=None,
        description="ScheduleCommit sha; default = último commit",
    ),
    top_n: int = Query(default=3, ge=1, le=10),
    tenant_id: UUID = Depends(_tenant_id),
    db: AsyncSession = Depends(get_session),
):
    """Q.174.F8 — "Porquê estes operadores?" para uma op planeada.

    Re-deriva os FATORES da escolha com a mesma fórmula do decoder
    (`explain_pick_workers`, drift-guarded por property test): rank de
    curado da fase (Q.155.D), nível por sector (Q.140.G), skill,
    disponibilidade, carga no plano (Q.164.A) e ausências (Q.174.F4).
    A carga e o "livre a partir de" são reconstruídos do PRÓPRIO commit
    (as ops atribuídas a cada operador antes desta), por isso a leitura
    é fiel ao plano publicado — não um número inventado (invariante #8).
    """
    from src.plan.cpo.decoder_resources import (
        _MIN_POOL_FOR_MATCHING,
        explain_pick_workers,
    )

    state = await FactoryState.load(db, tenant_id)
    commits = CommitsService(db, tenant_id)
    commit = (
        await commits.get_by_sha(sha) if sha else await commits.get_latest()
    )
    if commit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="sem ScheduleCommit — corre /v1/plan/cpo/schedule primeiro",
        )

    ops = list(commit.operations or [])
    target = next(
        (o for o in ops
         if str(o.get("operation_id") or "") == operation_id),
        None,
    )
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"operação {operation_id!r} não está neste commit",
        )

    fase_id = str(target.get("phase_id") or "")
    chosen = [str(w) for w in (target.get("workers") or [])]
    start_s = str(target.get("start_time") or "")
    try:
        op_start = datetime.fromisoformat(start_s)
    except ValueError:
        op_start = None
    dur_h = max(0.0, float(target.get("duration_minutes") or 0)) / 60.0

    pool = state.workers_for(fase_id) if fase_id else set()
    if not pool:
        return {
            "operation_id": operation_id,
            "phase_id": fase_id,
            "order_id": str(target.get("order_id") or ""),
            "commit_sha": commit.commit_sha256,
            "chosen": chosen,
            "pool_size": 0,
            "candidates": [],
            "explain_pt": (
                "Fase sem mão-de-obra no plano (cura/espera ou sem "
                "operadores qualificados na skill matrix) — não houve "
                "escolha de operador para explicar."
            ),
        }

    # Reconstrução fiel do estado do loop A PARTIR DO COMMIT: carga total
    # por operador + "livre a partir de" (fim da última op dele que começa
    # antes desta). Aproximação honesta — é o plano publicado, não o estado
    # interno exato do decoder durante o run.
    worker_load_h: dict = {}
    worker_free_at: dict = {}
    for o in ops:
        try:
            o_start = datetime.fromisoformat(str(o.get("start_time") or ""))
            o_end = datetime.fromisoformat(str(o.get("end_time") or ""))
        except ValueError:
            continue
        o_dur_h = max(0.0, float(o.get("duration_minutes") or 0)) / 60.0
        for w in (o.get("workers") or []):
            w = str(w)
            worker_load_h[w] = worker_load_h.get(w, 0.0) + o_dur_h
            if op_start is not None and o_start < op_start:
                prev = worker_free_at.get(w)
                if prev is None or o_end > prev:
                    worker_free_at[w] = o_end

    # ICB do barco (mesma isenção de fase fina que o decoder, Q.155.D).
    order_id = str(target.get("order_id") or "")
    model_id = next(
        (str(r.get("modelo_id") or "") for r in (state.open_orders or [])
         if str(r.get("order_id") or "") == order_id),
        "",
    )
    op_complexity = 0.0
    if model_id and len(pool) > _MIN_POOL_FOR_MATCHING:
        op_complexity = state.boat_complexity(model_id)

    quality_weight = 0.3  # default do Chromosome (o valor do run não é persistido)
    earliest = op_start or datetime.now().replace(tzinfo=None)  # noqa: DTZ005
    candidates = explain_pick_workers(
        pool,
        worker_free_at,
        earliest,
        state=state,
        quality_weight=quality_weight,
        fase_id=fase_id or None,
        op_complexity=op_complexity,
        worker_load_h=worker_load_h,
        op_duration_h=dur_h,
    )
    for c in candidates:
        c["escolhido"] = c["worker_id"] in chosen

    alternatives = [
        c for c in candidates if not c["escolhido"]
    ][:top_n]

    # Frase curta e factual sobre o 1º escolhido (se existir no breakdown).
    explain_pt = ""
    first = next((c for c in candidates if c["escolhido"]), None)
    if first is not None:
        partes = []
        if first["rank_curado"] is not None:
            partes.append("curado nesta fase (página Melhores por fase)")
        if first["horas_ate_livre"] <= 0.01:
            partes.append("livre no arranque da op")
        else:
            partes.append(f"livre {first['horas_ate_livre']:.0f}h depois")
        partes.append(f"carga no plano {first['carga_plano_h']:.0f}h")
        if op_complexity > 0:
            partes.append(f"barco com ICB {op_complexity:.2f} puxa os melhores")
        explain_pt = (
            f"{first['worker_id']}: " + ", ".join(partes) + "."
        )
    elif chosen:
        explain_pt = (
            "Operador atribuído manualmente ou fora do pool atual da fase "
            "(skill matrix mudou desde o commit)."
        )

    return {
        "operation_id": operation_id,
        "phase_id": fase_id,
        "order_id": order_id,
        "model_id": model_id or None,
        "commit_sha": commit.commit_sha256,
        "start_time": start_s or None,
        "team_size": len(chosen),
        "pool_size": len(pool),
        "op_complexity_icb": round(op_complexity, 4),
        "quality_weight": quality_weight,
        "chosen": chosen,
        "candidates": candidates[: max(top_n, len(chosen) + top_n)],
        "alternatives": alternatives,
        "explain_pt": explain_pt,
        "legenda_pt": {
            "combined": "pontuação final (skill×peso + disponibilidade×(1-peso) "
                        "+ bónus curado − penalização de carga)",
            "rank_curado": "posição na lista 'Melhores por fase' (1.0 = topo)",
            "skill_score": "nível/experiência na fase, normalizado ao pool",
            "horas_ate_livre": "horas até estar livre no arranque da op "
                               "(inclui ausências ENT_MOV/override)",
            "carga_plano_h": "horas totais atribuídas a este operador neste plano",
        },
    }
