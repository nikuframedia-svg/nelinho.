"""Q.155.A — job diário: Índice de Complexidade do Barco (ICB) por produto.

Fonte (mirror Postgres, sem ERP live): factory_raw.produto + produto_componente
(peças) + movimento (tinta) + of_fp/ordemfabrico (fases). Destino:
governance.boat_complexity (UPSERT idempotente).

3 sinais reais, complementares (validados contra a BD MAR-KAYAKS):
  1. peças    = nº de componentes na BOM (COMP_ELIMINADO IS NULL)
  2. tinta    = kg de gelcoat/resina/esmalte (MOV_TPMOV_ID=11, UNI kg) por OF
  3. processo = nº médio de fases distintas por OF (of_fp)

Cada sinal é normalizado por percentil entre os modelos com histórico estável
(≥5 OFs/12m); ICB = 0.40·peças + 0.30·tinta + 0.30·processo. Barcos prepreg têm
tinta≈0 estrutural (carbono pré-impregnado) → redistribui o peso da tinta p/
peças+fases (senão saíam "simples" por engano).

Corre às 04:25 UTC (depois do boat_potential às 04:20).
"""
from __future__ import annotations

import bisect
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List
from uuid import UUID

from sqlalchemy import text

from src.shared.database import get_session_context

logger = logging.getLogger(__name__)

_HISTORY_DAYS = 365
_MIN_OFS_QUALIFY = 5  # histórico estável p/ os percentis de referência

# Pesos do ICB (validados: sinais complementares, blend robusto).
_W_COMPONENTS = 0.40
_W_PAINT = 0.30
_W_PHASES = 0.30
# Prepreg: sem tinta molhada → redistribui o peso da tinta p/ peças+fases.
_W_PREPREG_COMPONENTS = 0.55
_W_PREPREG_PHASES = 0.45


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _pctile_ranker(values: List[float]) -> Callable[[float], float]:
    """Devolve f(x) = fração dos `values` ≤ x ∈ [0,1] (rank percentil empírico).

    Lista vazia → 0.5 (neutro). Determinístico.
    """
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return lambda _x: 0.5
    return lambda x: bisect.bisect_right(ordered, x) / n


def _icb_score(
    pc_components: float,
    pc_paint: float,
    pc_phases: float,
    *,
    is_prepreg: bool,
) -> float:
    """Combina os 3 percentis no ICB ∈ [0,1]. Prepreg ignora a tinta."""
    if is_prepreg:
        score = _W_PREPREG_COMPONENTS * pc_components + _W_PREPREG_PHASES * pc_phases
    else:
        score = (
            _W_COMPONENTS * pc_components
            + _W_PAINT * pc_paint
            + _W_PHASES * pc_phases
        )
    return _clamp(score)


async def _boat_complexity_job(tenant_id: UUID) -> None:
    """Calcula e persiste o ICB por produto-barco. Idempotente (UPSERT)."""
    started = datetime.now(timezone.utc)
    # OF_DATA/MOV_DATA são TEXT ISO no mirror → comparamos com ::timestamp
    # (naive) contra um cutoff naive (sem tz) para o asyncpg não rejeitar.
    cutoff = (started - timedelta(days=_HISTORY_DAYS)).replace(tzinfo=None)

    try:
        async with get_session_context() as session:
            # ── 1. Universo de barcos + nº de peças (BOM) + flag prepreg ─────
            comp_rows = (
                await session.execute(
                    text(
                        """
                        SELECT p."P_ID"::text AS pid,
                               COALESCE(p."P_NOME", '') AS pname,
                               COUNT(c."COMP_ID") AS n_components,
                               (p."P_NOME" ILIKE '%prepreg%') AS is_prepreg
                        FROM factory_raw.produto p
                        LEFT JOIN factory_raw.produto_componente c
                          ON c."COMP_P_ID" = p."P_ID" AND c."COMP_ELIMINADO" IS NULL
                        WHERE p."P_QTDDECK" > 0 AND p."P_QTDCASCO" > 0
                          AND p."P_NOME" NOT ILIKE '%teste%'
                          AND p."P_NOME" NOT ILIKE '%demo%'
                          AND p."P_NOME" NOT ILIKE '%molde%'
                          AND p."P_NOME" NOT ILIKE '%prototip%'
                        GROUP BY p."P_ID", p."P_NOME"
                        """
                    )
                )
            ).all()

            if not comp_rows:
                logger.info("boat_complexity_job: sem barcos tenant=%s", tenant_id)
                return

            name: Dict[str, str] = {}
            prepreg: Dict[str, bool] = {}
            n_components: Dict[str, int] = {}
            for r in comp_rows:
                name[r.pid] = r.pname
                prepreg[r.pid] = bool(r.is_prepreg)
                n_components[r.pid] = int(r.n_components or 0)

            # ── 2. Fases distintas/OF + nº de OFs (12m) ───────────────────────
            phase_rows = (
                await session.execute(
                    text(
                        """
                        SELECT o."OF_P_ID"::text AS pid,
                               COUNT(DISTINCT o."OF_ID") AS n_ofs,
                               AVG(dp.dphases::float) AS avg_phases
                        FROM factory_raw.ordemfabrico o
                        JOIN (
                          SELECT f."OFFP_OF_ID" AS ofid,
                                 COUNT(DISTINCT f."OFFP_FP_ID") AS dphases
                          FROM factory_raw.of_fp f
                          GROUP BY f."OFFP_OF_ID"
                        ) dp ON dp.ofid = o."OF_ID"
                        WHERE o."OF_DATA" IS NOT NULL
                          AND o."OF_DATA"::timestamp >= :cutoff
                          AND o."OF_P_ID" IS NOT NULL
                        GROUP BY o."OF_P_ID"
                        """
                    ),
                    {"cutoff": cutoff},
                )
            ).all()
            n_ofs: Dict[str, int] = {}
            avg_phases: Dict[str, float] = {}
            for r in phase_rows:
                n_ofs[r.pid] = int(r.n_ofs or 0)
                avg_phases[r.pid] = float(r.avg_phases or 0.0)

            # ── 3. Tinta consumida (kg) por produto (12m) → kg/OF ─────────────
            paint_rows = (
                await session.execute(
                    text(
                        """
                        SELECT o."OF_P_ID"::text AS pid,
                               SUM(m."MOV_QUANTIDADE")::float AS paint_kg
                        FROM factory_raw.movimento m
                        JOIN factory_raw.ordemfabrico o ON o."OF_ID" = m."MOV_OF_ID"
                        JOIN factory_raw.produto pm ON pm."P_ID" = m."MOV_P_ID"
                        WHERE m."MOV_TPMOV_ID" = 11
                          AND m."MOV_DATA" IS NOT NULL
                          AND m."MOV_DATA"::timestamp >= :cutoff
                          AND pm."P_UNI_ID" = 7
                          AND (
                                pm."P_TP_ID" IN (57, 76, 288)
                                OR (pm."P_TP_ID" = 102 AND (
                                      pm."P_NOME" ILIKE '%esmalte%'
                                      OR pm."P_NOME" ILIKE '%verniz%'
                                      OR pm."P_NOME" ILIKE '%spray%'
                                      OR pm."P_NOME" ILIKE '%base mix%'
                                      OR pm."P_NOME" ILIKE '%clear%'
                                      OR pm."P_NOME" ILIKE '%tinta%'
                                      OR pm."P_NOME" ILIKE '%primário%'
                                      OR pm."P_NOME" ILIKE '%primario%'
                                ))
                              )
                        GROUP BY o."OF_P_ID"
                        """
                    ),
                    {"cutoff": cutoff},
                )
            ).all()
            paint_kg_per_of: Dict[str, float] = {}
            for r in paint_rows:
                ofs = n_ofs.get(r.pid, 0)
                paint_kg_per_of[r.pid] = (float(r.paint_kg or 0.0) / ofs) if ofs > 0 else 0.0

            # ── 4. Percentis de referência (só modelos com histórico estável) ─
            qualifying = [pid for pid in name if n_ofs.get(pid, 0) >= _MIN_OFS_QUALIFY]
            rank_comp = _pctile_ranker([float(n_components.get(p, 0)) for p in qualifying])
            rank_paint = _pctile_ranker([paint_kg_per_of.get(p, 0.0) for p in qualifying])
            rank_phases = _pctile_ranker([avg_phases.get(p, 0.0) for p in qualifying])

            # ── 5. ICB para TODOS os barcos + rank + UPSERT ───────────────────
            scored = []
            for pid in name:
                score = _icb_score(
                    rank_comp(float(n_components.get(pid, 0))),
                    rank_paint(paint_kg_per_of.get(pid, 0.0)),
                    rank_phases(avg_phases.get(pid, 0.0)),
                    is_prepreg=prepreg.get(pid, False),
                )
                scored.append((pid, score))
            scored.sort(key=lambda t: (-t[1], t[0]))  # desc, tie-break por pid

            now_ts = datetime.now(timezone.utc)
            for idx, (pid, score) in enumerate(scored, start=1):
                await session.execute(
                    text(
                        """
                        INSERT INTO governance.boat_complexity
                            (tenant_id, product_id, product_name, complexity_score,
                             rank, n_components, paint_kg_per_of, n_distinct_phases,
                             n_ofs, last_computed_at)
                        VALUES
                            (:tid, :pid, :pname, :score, :rank, :ncomp, :pkg, :phases,
                             :nofs, :ts)
                        ON CONFLICT (tenant_id, product_id)
                        DO UPDATE SET
                            product_name = EXCLUDED.product_name,
                            complexity_score = EXCLUDED.complexity_score,
                            rank = EXCLUDED.rank,
                            n_components = EXCLUDED.n_components,
                            paint_kg_per_of = EXCLUDED.paint_kg_per_of,
                            n_distinct_phases = EXCLUDED.n_distinct_phases,
                            n_ofs = EXCLUDED.n_ofs,
                            last_computed_at = EXCLUDED.last_computed_at
                        """
                    ),
                    {
                        "tid": tenant_id,
                        "pid": pid,
                        "pname": name.get(pid, ""),
                        "score": float(score),
                        "rank": idx,
                        "ncomp": int(n_components.get(pid, 0)),
                        "pkg": float(paint_kg_per_of.get(pid, 0.0)),
                        "phases": float(avg_phases.get(pid, 0.0)),
                        "nofs": int(n_ofs.get(pid, 0)),
                        "ts": now_ts,
                    },
                )

            await session.commit()

        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        logger.info(
            "boat_complexity_job: tenant=%s barcos=%s qualificados=%s elapsed_ms=%s",
            tenant_id, len(scored), len(qualifying), elapsed_ms,
        )

    except Exception as exc:
        logger.error(
            "boat_complexity_job tenant=%s falhou: %s", tenant_id, exc, exc_info=True
        )
