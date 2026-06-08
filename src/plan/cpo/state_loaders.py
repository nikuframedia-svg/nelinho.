"""ProdPlan ONE — CPO FactoryState: loaders de BD + extractors do engine.

Extraido de state.py (saneamento 2026-06-04). Importa as primitivas de
state.py; e re-exportado por state.py (compat 100%). NAO importar daqui
directamente em codigo novo — usar `from src.plan.cpo.state import ...`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

# As primitivas de state.py (MoldInfo, normalize_phase_code, NELO_CURING_GAPS_SEED,
# REPAIR_PHASE_IDS) são importadas LAZY dentro das 4 funções que as usam — quebra o
# ciclo state<->state_loaders, permitindo `import state_loaders` standalone sem
# ImportError. Idioma Python canónico para ciclos de import (saneamento 2026-06-04).
if TYPE_CHECKING:  # só anotações (strings via __future__); NÃO corre em runtime → sem ciclo
    from src.plan.cpo.state import MoldInfo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers — extract from semantic engine's curated_data
# ---------------------------------------------------------------------------

def _safe_call(sq: Any, method: str, **kwargs) -> Optional[Dict[str, Any]]:
    try:
        fn = getattr(sq, method, None)
        if fn is None:
            return None
        result = fn(**kwargs)
        if isinstance(result, dict) and result.get("status") == "BLOCKED":
            return None
        return result
    except Exception as e:
        logger.debug(f"Semantic call {method} failed: {e}")
        return None


def _extract_skill_matrix(engine: Any) -> Dict[str, Set[str]]:
    """
    Build {fase_id: {funcionario_id, ...}} from CuratedSkillMatrix rows.
    Best-effort; returns {} if engine shape doesn't match.
    """
    try:
        active_id = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active_id, {}) if active_id else {}
        rows = scope.get("skill_matrix") or scope.get("CuratedSkillMatrix") or []
        matrix: Dict[str, Set[str]] = {}
        for row in rows:
            if not getattr(row, "apto", True):
                continue
            fase_id = str(getattr(row, "fase_id", ""))
            func_id = str(getattr(row, "funcionario_id", ""))
            if fase_id and func_id:
                matrix.setdefault(fase_id, set()).add(func_id)
        return matrix
    except Exception as e:
        logger.debug(f"skill matrix extraction failed: {e}")
        return {}


def _extract_molds(engine: Any) -> Tuple[Dict[str, List[MoldInfo]], Dict[str, MoldInfo]]:
    from src.plan.cpo.state import MoldInfo

    try:
        active_id = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active_id, {}) if active_id else {}
        rows = scope.get("molds") or scope.get("CuratedMold") or []
        by_model: Dict[str, List[MoldInfo]] = {}
        by_id: Dict[str, MoldInfo] = {}
        for row in rows:
            info = MoldInfo(
                molde_id=str(getattr(row, "molde_id", "")),
                modelo_id=str(getattr(row, "modelo_id", "")),
                pocket_count=int(getattr(row, "pocket_count", None) or getattr(row, "tamanho_id", 1) or 1),
                em_manutencao=bool(getattr(row, "em_manutencao", False)),
                tipo=str(getattr(row, "tipo", "")),
            )
            if info.molde_id:
                by_id[info.molde_id] = info
                if info.modelo_id:
                    by_model.setdefault(info.modelo_id, []).append(info)
        return by_model, by_id
    except Exception as e:
        logger.debug(f"mold extraction failed: {e}")
        return {}, {}


def _extract_durations(engine: Any) -> Dict[Tuple[str, str], float]:
    """
    Compute median horas_reais per (fase_id, modelo_id) from CuratedOrderPhase +
    CuratedOrder (to join modelo_id).
    """
    try:
        from statistics import median
    except ImportError:  # pragma: no cover
        return {}

    try:
        active_id = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active_id, {}) if active_id else {}
        phases = scope.get("order_phases") or scope.get("CuratedOrderPhase") or []
        orders = scope.get("orders") or scope.get("CuratedOrder") or []

        order_model: Dict[str, str] = {}
        for o in orders:
            oid = str(getattr(o, "of_id", ""))
            mid = str(getattr(o, "modelo_id", ""))
            if oid:
                order_model[oid] = mid

        buckets: Dict[Tuple[str, str], List[float]] = {}
        for p in phases:
            h_real = getattr(p, "horas_reais", None) or getattr(p, "horas_finais", None)
            if not h_real or h_real <= 0:
                continue
            fase_id = str(getattr(p, "fase_id", ""))
            of_id = str(getattr(p, "of_id", ""))
            modelo_id = order_model.get(of_id, "")
            if fase_id and modelo_id:
                buckets.setdefault((fase_id, modelo_id), []).append(float(h_real))

        return {k: float(median(v)) for k, v in buckets.items() if v}
    except Exception as e:
        logger.debug(f"duration extraction failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Q.126 — DB-backed real data from the live ERP mirror (factory_raw.*)
# ---------------------------------------------------------------------------
# The in-memory curated layer (SemanticQueriesInMemory, fed by the Excel
# `Folha_IA_extra.xlsx`) is empty in production, so the CPO fell back to the
# 2x synthetic buffer (RoutingResolver._standard_template). The ML was already
# repointed to factory_raw.of_fp (Q.124); these loaders do the same for the
# CPO. Tempos vêm SEMPRE do histórico real (axioma Spelke). Best-effort: any
# failure returns empties and never crashes load() nor flips loaded_ok.

# Duration of one phase execution, in hours, from the ISO-text timestamps.
_OFFP_DUR_H = (
    "EXTRACT(EPOCH FROM ("
    "CAST(NULLIF(op.\"OFFP_DATAFIM\", '')    AS timestamp) - "
    "CAST(NULLIF(op.\"OFFP_DATAINICIO\", '') AS timestamp)))/3600.0"
)
# Cleaning shared with build_duration_dataset (Q.124) PLUS a floor.
# Without the floor the Pintura phase (FP 18) collapses to a ~0.083h median
# because of ~1600 near-zero punch rows (verified in _audit/q126/); the floor
# restores the real 3.18h. The ceiling drops phases left open across days.
_OFFP_DUR_OK = (
    "NULLIF(op.\"OFFP_DATAINICIO\", '') IS NOT NULL "
    "AND NULLIF(op.\"OFFP_DATAFIM\", '') IS NOT NULL "
    "AND CAST(NULLIF(op.\"OFFP_DATAFIM\", '') AS timestamp) "
    "  > CAST(NULLIF(op.\"OFFP_DATAINICIO\", '') AS timestamp)"
)
# Duration bounds (hours): floor = drop sub-3-minute punch artifacts; ceiling
# = one week (phases left open across days are calendar artifacts, not work).
# Expressed as 24*7 so it reads as "1 semana", not a magic number.
_DUR_FLOOR_H = 0.05
_DUR_CEIL_H = 24.0 * 7

# Q.133.A2 — amostra mínima por (modelo, fase) para preferir o p50 calibrado
# sobre a mediana crua de of_fp (alinhado com o HAVING count>=5 do job).
_CALIBRATION_MIN_OBS = 5

# Q.131.F — horizonte de planeamento INTERATIVO (botão "Replanear"). O WIP real
# tem ~5300 OFs abertas; planear todas esgota o orçamento da GA logo na geração 1
# (sem optimização real) e demora demasiado para um clique. Planeamos as N ordens
# MAIS URGENTES (menor data de entrega) — rolling horizon. O Luis pediu ~200; é o
# nº onde a GA optimiza em segundos. Q.161.A — passou a ser só o DEFAULT (quando
# `plan_cap` não é passado); o robô de fundo passa um cap maior (não-interativo).
_OPEN_ORDERS_PLAN_CAP = 200

# Q.161.A — tecto de segurança quando se pede "planear todos os em-produção"
# (`plan_cap <= 0`): cobre os ~1209 em produção (nova+fila+reparações) com folga,
# mas impede um runaway caso a regra de scope alargue (a GA não deve afogar). O
# robô (job de fundo) corre com tempo maior, por isso pode planear o pool todo.
_OPEN_ORDERS_HARD_CAP = 5000

# Q.160 — fallback global da fila inter-fase (minutos), usado só quando NÃO há
# histórico suficiente em of_fp (tabela vazia, testes legacy). Igual ao seed
# `planning.queue_time.median_h` (5.2h). ANTES era a constante hardcoded ÚNICA
# (engine._DECODER_QUEUE_TIME_MIN, igual para todas as fases); agora a fila vem
# da mediana REAL por fase (queue_median_by_phase) e isto é só a rede final.
_QUEUE_FALLBACK_MIN = 5.2 * 60.0


async def _load_historical_durations_routes_db(
    session: Any,
    tenant_id: UUID,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[Tuple[str, str], float], Dict[str, float]]:
    """Q.126.B — real durations + routes from `factory_raw.of_fp` (ERP vivo).

    Returns ``(routes_by_model, durations_by_pair, durations_by_fase)``:
      * ``routes_by_model[str(OF_P_ID)]`` = ordered production-phase steps
        ``{fase_id, fase_nome, sequence, duration_hours}`` (ordered by
        ``FP_SEQUENCIA``, only ``FP_PRODUCAO=true``). Lets the resolver build
        a REAL route when the in-memory curated layer (Excel) is empty.
      * ``durations_by_pair[(str(fase), str(model))]`` = real median hours.
      * ``durations_by_fase[str(fase)]`` = real median per fase across all
        models — the 2nd-tier fallback before the 2x synthetic buffer.
    """
    empty: Tuple[Dict[str, List[Dict[str, Any]]], Dict[Tuple[str, str], float], Dict[str, float]] = ({}, {}, {})
    if session is None:
        return empty
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    pair_sql = text(
        f"""
        WITH d AS (
            SELECT ofb."OF_P_ID" AS model, op."OFFP_FP_ID" AS fase_id, {_OFFP_DUR_H} AS h
            FROM factory_raw.of_fp op
            JOIN factory_raw.ordemfabrico ofb ON ofb."OF_ID" = op."OFFP_OF_ID"
            WHERE {_OFFP_DUR_OK} AND ofb."OF_P_ID" IS NOT NULL
        )
        SELECT d.model::text AS model, d.fase_id::text AS fase_id,
               f."FP_NOME" AS fase_nome, f."FP_SEQUENCIA" AS seq,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY d.h) AS median_h
        FROM d
        JOIN factory_raw.fases_producao f ON f."FP_ID" = d.fase_id
        WHERE d.h > {_DUR_FLOOR_H} AND d.h <= {_DUR_CEIL_H} AND f."FP_PRODUCAO" = true
        GROUP BY d.model, d.fase_id, f."FP_NOME", f."FP_SEQUENCIA"
        HAVING count(*) >= 2
        ORDER BY d.model, f."FP_SEQUENCIA"
        """
    )
    fase_sql = text(
        f"""
        SELECT op."OFFP_FP_ID"::text AS fase_id,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY {_OFFP_DUR_H}) AS median_h
        FROM factory_raw.of_fp op
        WHERE {_OFFP_DUR_OK}
          AND {_OFFP_DUR_H} > {_DUR_FLOOR_H} AND {_OFFP_DUR_H} <= {_DUR_CEIL_H}
        GROUP BY op."OFFP_FP_ID"
        HAVING count(*) >= 5
        """
    )
    try:
        pair_rows = (await session.execute(pair_sql)).mappings().all()
        fase_rows = (await session.execute(fase_sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.126.B durations/routes DB load skipped: %s", exc)
        return empty

    by_pair: Dict[Tuple[str, str], float] = {}
    routes: Dict[str, List[Dict[str, Any]]] = {}
    for r in pair_rows:
        median_h = float(r["median_h"] or 0.0)
        if median_h <= 0:
            continue
        model = str(r["model"])
        fase_id = str(r["fase_id"])
        by_pair[(fase_id, model)] = median_h
        routes.setdefault(model, []).append(
            {
                "fase_id": fase_id,
                "fase_nome": str(r["fase_nome"] or fase_id),
                "sequence": int(r["seq"] or 0),
                "duration_hours": median_h,
            }
        )
    # Defensive: keep each route ordered by FP_SEQUENCIA even if the row
    # order ever changes (the SQL already ORDERs by it).
    for steps in routes.values():
        steps.sort(key=lambda s: s["sequence"])
    by_fase: Dict[str, float] = {
        str(r["fase_id"]): float(r["median_h"])
        for r in fase_rows
        if r["median_h"] and float(r["median_h"]) > 0
    }
    return routes, by_pair, by_fase


async def _load_phase_std_ref_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, Dict[str, float]]:
    """Q.165.D — TEMPO-PADRÃO de mão-de-obra por fase×classe-de-kayak, de
    `factory_raw.fases_producao.FP_VALOR_REF_K1/K2/K4` (horas, confirmado pelo
    dono). É o TOUCH-TIME real do ERP — ao contrário da mediana de of_fp
    (OFFP_DATAFIM-OFFP_DATAINICIO) que é FLOW-TIME (fase aberta, inclui secagem).
    Prova: 1 operador creditado 863 of_fp-h num dia; o rácio flow/ref isola as
    fases de secagem (Acabamento-Preparação 36×, Acabamento-Pintura 12×).

    Devolve ``{fase_id: {"K1": h, "K2": h, "K4": h}}`` só para fases de produção
    com algum valor > 0 (12 das 41). NUNCA usa FP_HORA_COEF nem os COEFICIENTE_X
    (sistema de €, CoeficienteX — invariante CLAUDE.md). `factory_raw` é
    tenant-agnóstico. Best-effort → ``{}``."""
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    sql = text(
        """
        SELECT "FP_ID"::text AS fase_id,
               "FP_VALOR_REF_K1" AS k1,
               "FP_VALOR_REF_K2" AS k2,
               "FP_VALOR_REF_K4" AS k4
        FROM factory_raw.fases_producao
        WHERE "FP_PRODUCAO" = true
          AND (COALESCE("FP_VALOR_REF_K1",0) > 0
            OR COALESCE("FP_VALOR_REF_K2",0) > 0
            OR COALESCE("FP_VALOR_REF_K4",0) > 0)
        """
    )
    try:
        rows = (await session.execute(sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.165.D phase_std_ref DB load skipped: %s", exc)
        return {}
    out: Dict[str, Dict[str, float]] = {}
    for r in rows:
        cls_map: Dict[str, float] = {}
        for col, cls in (("k1", "K1"), ("k2", "K2"), ("k4", "K4")):
            v = r[col]
            if v is not None and float(v) > 0:
                cls_map[cls] = float(v)
        if cls_map:
            out[str(r["fase_id"])] = cls_map
    return out


# Q.166.D — canoa/va'a → classe-K EQUIVALENTE (mesma contagem de lugares). O
# FP_VALOR_REF só tem colunas K1/K2/K4, mas o trabalho de um C1 (canoa 1 lugar) ≈ K1,
# C2≈K2, C4≈K4, V1 (va'a 1)≈K1, K5≈K4. Aproximação assumida (decisão do dono: derivar
# touch-time de dados reais; o tempo-padrão por lugar é o melhor proxy disponível).
_CANOE_CLASS_MAP: Dict[str, str] = {
    "K1": "K1", "K2": "K2", "K4": "K4",
    "C1": "K1", "C2": "K2", "C4": "K4", "V1": "K1", "K5": "K4",
}


async def _load_model_kayak_class_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, str]:
    """Q.165.D/Q.166.D — mapa modelo (P_ID = OF_P_ID) → classe de kayak {K1,K2,K4},
    derivado do prefixo de `produto.P_NOME` (ex.: "K1 Vanquish L WWR" → K1).

    Q.166.D — inclui canoas/va'a (C1/C2/C4/V1/K5) mapeadas à classe-K equivalente
    por contagem de lugares (`_CANOE_CLASS_MAP`), para o touch-time FP_VALOR_REF
    cobrir ~70% dos modelos (era ~45% só com K1/K2/K4). Modelos sem prefixo caem
    no fallback p25-flow. `factory_raw` tenant-agnóstico. Best-effort → ``{}``."""
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    sql = text(
        """
        SELECT "P_ID"::text AS model_id,
               upper(substring(trim("P_NOME") from '^(K1|K2|K4|C1|C2|C4|V1|K5)')) AS prefix
        FROM factory_raw.produto
        WHERE substring(trim("P_NOME") from '^(K1|K2|K4|C1|C2|C4|V1|K5)') IS NOT NULL
        """
    )
    try:
        rows = (await session.execute(sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.165.D model_kayak_class DB load skipped: %s", exc)
        return {}
    out: Dict[str, str] = {}
    for r in rows:
        cls = _CANOE_CLASS_MAP.get(str(r["prefix"]))
        if cls:
            out[str(r["model_id"])] = cls
    return out


async def _load_phase_p25_durations_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, float]:
    """Q.166.D — touch-time fallback por fase = p25 do flow-time de `factory_raw.of_fp`
    (horas). O p50/mediana é flow-time (fase aberta, inclui secagem/espera); o p25
    (conclusões rápidas, sem o barco "sentar-se") aproxima o TRABALHO real. É o tier
    abaixo do FP_VALOR_REF para fases/modelos sem tempo-padrão do ERP. count>=5 por
    fase. `factory_raw` tenant-agnóstico. Best-effort → ``{}``."""
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    sql = text(
        f"""
        SELECT op."OFFP_FP_ID"::text AS fase_id,
               percentile_cont(0.25) WITHIN GROUP (ORDER BY {_OFFP_DUR_H}) AS p25_h
        FROM factory_raw.of_fp op
        WHERE {_OFFP_DUR_OK}
          AND {_OFFP_DUR_H} > {_DUR_FLOOR_H} AND {_OFFP_DUR_H} <= {_DUR_CEIL_H}
        GROUP BY op."OFFP_FP_ID"
        HAVING count(*) >= 5
        """
    )
    try:
        rows = (await session.execute(sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.166.D phase_p25 DB load skipped: %s", exc)
        return {}
    return {
        str(r["fase_id"]): float(r["p25_h"])
        for r in rows if r["p25_h"] and float(r["p25_h"]) > 0
    }


async def _load_phase_catalog_db(
    session: Any,
    tenant_id: UUID,
) -> List[Dict[str, Any]]:
    """Q.164.C — catálogo canónico de fases de PRODUÇÃO de `factory_raw.fases_producao`
    (`FP_PRODUCAO=true`), ordenado por `FP_SEQUENCIA`.

    Q.166.D — cada item leva `boat_fraction` = fração de barcos (de `v_of_is_boat`)
    que historicamente passou pela fase (de `of_fp`). O `_canonical_route` usa-a para
    incluir só fases COMUNS (>= limiar), não as raras/especiais (ex. Acabamento 3,
    só ~36 barcos de sempre) — senão a rota-fallback over-inclui fases que quase
    nenhum barco faz e cria gargalos fantasma.

    Devolve ``[{fase_id, sequence, fase_nome}]``. É o ÚLTIMO fallback de rota do
    RoutingResolver: um modelo sem QUALQUER rota (sem histórico of_fp >=2 obs, sem
    template ERP, sem curada Excel) passa a assumir esta sequência-padrão com
    durações medianas REAIS por fase (`historical_durations_by_fase`) em vez de
    ficar `no_route` (barco invisível no plano). `factory_raw` é tenant-agnóstico
    (espelho ERP partilhado) → sem filtro de tenant. Best-effort → ``[]``."""
    if session is None:
        return []
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    # Q.166.D — boat_fraction: nº de barcos (v_of_is_boat) que passaram por cada fase
    # em of_fp / total de barcos. Identifica fases COMUNS vs raras p/ a rota canónica.
    sql = text(
        """
        WITH total AS (
            SELECT count(*)::float AS n FROM factory_raw.v_of_is_boat WHERE is_boat = true
        ),
        per_phase AS (
            SELECT op."OFFP_FP_ID"::text AS fase_id,
                   count(DISTINCT op."OFFP_OF_ID") AS n_boats
            FROM factory_raw.of_fp op
            JOIN factory_raw.v_of_is_boat vb ON vb.of_id = op."OFFP_OF_ID" AND vb.is_boat = true
            GROUP BY op."OFFP_FP_ID"
        )
        SELECT f."FP_ID"::text AS fase_id,
               f."FP_SEQUENCIA" AS seq,
               f."FP_NOME"      AS fase_nome,
               COALESCE(pp.n_boats, 0) / NULLIF((SELECT n FROM total), 0) AS boat_fraction
        FROM factory_raw.fases_producao f
        LEFT JOIN per_phase pp ON pp.fase_id = f."FP_ID"::text
        WHERE f."FP_PRODUCAO" = true
        ORDER BY f."FP_SEQUENCIA", f."FP_ID"
        """
    )
    try:
        rows = (await session.execute(sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.164.C phase_catalog DB load skipped: %s", exc)
        return []
    return [
        {
            "fase_id": str(r["fase_id"]),
            "sequence": int(r["seq"] or 0),
            "fase_nome": str(r["fase_nome"] or r["fase_id"]),
            "boat_fraction": float(r["boat_fraction"] or 0.0),
        }
        for r in rows
    ]


async def _load_phase_queue_medians_db(
    session: Any,
    tenant_id: UUID,
) -> Tuple[Dict[str, float], Optional[float]]:
    """Q.160 — mediana REAL da fila inter-fase por fase de DESTINO, de
    `factory_raw.of_fp`.

    A "fila" é o gap entre o FIM da fase anterior e o INÍCIO da fase seguinte do
    MESMO barco (`OFFP_OF_ID`), via `LAG`. Substitui a constante global 5.2h por
    uma mediana MEDIDA por fase — e é também o mapa de gargalos (que fase acumula
    WIP). Distingue-se da cura (`min_gap_hours`, física): isto é desperdício
    observado, calibrável.

    Devolve ``(by_phase_h, global_h)``:
      * ``by_phase_h[str(OFFP_FP_ID)]`` = mediana de horas de fila (n_obs >= 5).
      * ``global_h`` = mediana global de todas as gaps (fallback) ou ``None``.

    Mediana (`percentile_cont(0.5)`), NUNCA média — a distribuição é assimétrica
    (mediana ~5.2h vs p90 ~69h); a média seria arrastada pela cauda. Limpeza:
    descarta gaps negativos (ops sobrepostas/ruído) e > 1 semana (barco parado,
    não fila). Best-effort: session None / tabela ausente → ``({}, None)``.
    """
    if session is None:
        return {}, None
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    # gaps por barco via LAG; GROUPING SETS dá num só passe a mediana POR FASE
    # (dest_fase não-nulo) E a mediana GLOBAL (grouping () → dest_fase NULL).
    sql = text(
        """
        WITH gaps AS (
            SELECT op."OFFP_FP_ID" AS dest_fase,
                   EXTRACT(EPOCH FROM (
                       CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp)
                       - LAG(CAST(NULLIF(op."OFFP_DATAFIM", '') AS timestamp))
                           OVER (PARTITION BY op."OFFP_OF_ID"
                                 ORDER BY CAST(NULLIF(op."OFFP_DATAINICIO", '') AS timestamp))
                   )) / 3600.0 AS gap_h
            FROM factory_raw.of_fp op
            WHERE NULLIF(op."OFFP_DATAINICIO", '') IS NOT NULL
        )
        SELECT dest_fase::text AS fase_id,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY gap_h) AS median_h,
               count(*) AS n_obs
        FROM gaps
        WHERE gap_h IS NOT NULL AND gap_h >= 0 AND gap_h <= 24 * 7  -- ceil 1 semana
        GROUP BY GROUPING SETS ((dest_fase), ())
        HAVING count(*) >= 5
        """
    )
    try:
        rows = (await session.execute(sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.160 queue medians DB load skipped: %s", exc)
        return {}, None

    by_phase: Dict[str, float] = {}
    global_h: Optional[float] = None
    for r in rows:
        median_h = r["median_h"]
        if median_h is None or float(median_h) < 0:
            continue
        fase_id = r["fase_id"]
        if fase_id is None:  # grouping set () → mediana global
            global_h = float(median_h)
        else:
            by_phase[str(fase_id)] = float(median_h)
    return by_phase, global_h


async def _load_route_templates_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, List[Dict[str, Any]]]:
    """Q.131.G — routing master do ERP: rota por modelo (OF_P_ID) a partir de
    `plan.model_routing_assignment` JOIN `plan.routing_template_phase`. Espelha a
    tabela ERP PRODUTO_FASE (sequência de fases) e a `duration_p50_h` minerada
    de `of_fp` pelo job `time_mining` (Spelke: tempo real, NUNCA CoeficienteX).

    Fallback REAL para modelos sem ≥2 observações por fase em of_fp (cobre os
    ~27% que o histórico per-order não cobre). Keyed por `str(model_id)`=OF_P_ID,
    igual a `historical_routes_by_model`. p50 pode vir NULL (fases sem amostra) —
    o resolver decide a duração (p50 → mediana-por-fase → ordem em unplanned).

    Best-effort: session None / tabela ausente / outra BD → `{}`. NOTA: estas
    são tabelas `TenantBase` (tenant-scoped), ao contrário de factory_raw.* —
    daí o filtro explícito de tenant."""
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    sql = text(
        """
        SELECT mra.model_id::text          AS model_id,
               rtp.seq                      AS seq,
               rtp.phase_id::text           AS phase_id,
               rtp.phase_name               AS phase_name,
               rtp.duration_p50_h           AS duration_p50_h,
               rtp.requires_mold            AS requires_mold,
               rtp.team_size_default        AS team_size_default
        FROM plan.model_routing_assignment mra
        JOIN plan.routing_template_phase rtp
          ON rtp.template_id = mra.primary_template_id
        JOIN factory_raw.fases_producao fp
          ON fp."FP_ID"::text = rtp.phase_id::text
        WHERE mra.tenant_id = :tenant AND rtp.tenant_id = :tenant
          AND fp."FP_PRODUCAO" = true
        ORDER BY mra.model_id, rtp.seq
        """
    )
    try:
        rows = (await session.execute(
            sql, {"tenant": str(tenant_id)}
        )).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.131.G route_templates DB load skipped: %s", exc)
        return {}

    templates: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        p50 = r["duration_p50_h"]
        templates.setdefault(str(r["model_id"]), []).append({
            "fase_id": str(r["phase_id"]),
            "fase_nome": str(r["phase_name"] or r["phase_id"]),
            "sequence": int(r["seq"] or 0),
            "duration_p50_h": float(p50) if p50 is not None else None,
            "requires_mold": bool(r["requires_mold"]),
            "team_size_default": int(r["team_size_default"] or 1),
        })
    for steps in templates.values():
        steps.sort(key=lambda s: s["sequence"])
    return templates


async def _load_phase_calibration_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[Tuple[str, str], Tuple[float, int]]:
    """Q.133.A2 — p50 CALIBRADO por (fase_id, modelo) do job phase_calibration
    (`plan.phase_duration_calibration`). Devolve `{(fase,modelo): (p50_horas,
    n_obs)}`. Best-effort: session None / tabela ausente → `{}`. Tenant-scoped
    (PK composto inclui tenant_id). p50 vem em minutos → converte para horas."""
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    sql = text(
        """
        SELECT phase_id::text AS fase_id, modelo::text AS modelo, p50_min, n_obs
        FROM plan.phase_duration_calibration
        WHERE tenant_id = :tenant AND p50_min > 0
        """
    )
    try:
        rows = (await session.execute(
            sql, {"tenant": str(tenant_id)}
        )).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.133.A2 phase_calibration DB load skipped: %s", exc)
        return {}
    out: Dict[Tuple[str, str], Tuple[float, int]] = {}
    for r in rows:
        out[(str(r["fase_id"]), str(r["modelo"]))] = (
            float(r["p50_min"]) / 60.0,
            int(r["n_obs"]),
        )
    return out


async def _load_molds_db(
    session: Any,
    tenant_id: UUID,
) -> Tuple[Dict[str, List[MoldInfo]], Dict[str, MoldInfo]]:
    """Q.126.C — real molds from `factory_raw.of_fp.OFFP_OF_ID_MLD` joined to
    the model (`OF_P_ID`) via `ordemfabrico`. 1186 (mold, model) pairs vs only
    6 from ordemfabrico alone (verified in _audit/q126/). Best-effort."""
    from src.plan.cpo.state import MoldInfo

    if session is None:
        return {}, {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    sql = text(
        """
        SELECT DISTINCT op."OFFP_OF_ID_MLD"::text AS molde_id,
                        ofb."OF_P_ID"::text        AS modelo_id
        FROM factory_raw.of_fp op
        JOIN factory_raw.ordemfabrico ofb ON ofb."OF_ID" = op."OFFP_OF_ID"
        WHERE op."OFFP_OF_ID_MLD" IS NOT NULL AND op."OFFP_OF_ID_MLD" <> 0
          AND ofb."OF_P_ID" IS NOT NULL
        """
    )
    try:
        rows = (await session.execute(sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.126.C molds DB load skipped: %s", exc)
        return {}, {}
    by_model: Dict[str, List[MoldInfo]] = {}
    by_id: Dict[str, MoldInfo] = {}
    for r in rows:
        molde_id = str(r["molde_id"])
        modelo_id = str(r["modelo_id"])
        if not molde_id or molde_id == "0":
            continue
        info = by_id.get(molde_id)
        if info is None:
            info = MoldInfo(molde_id=molde_id, modelo_id=modelo_id, pocket_count=1)
            by_id[molde_id] = info
        by_model.setdefault(modelo_id, []).append(info)
    return by_model, by_id


async def _load_skills_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, Set[str]]:
    """Q.126.D — real skill matrix from `factory_raw.offp_eq` (crew records)
    joined to `of_fp` (phase). ``skill_matrix[str(fase_id)] = {str(E_ID)}``.
    483 (fase, worker) pairs across 40 phases verified. A PARTIAL matrix is
    safe: the decoder schedules a phase as manual when it has no workers in
    the matrix (decoder_resources.py:356), never infeasible."""
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    sql = text(
        """
        SELECT DISTINCT o."OFFP_FP_ID"::text   AS fase_id,
                        eq."OFFPEQ_E_ID"::text AS func_id
        FROM factory_raw.offp_eq eq
        JOIN factory_raw.of_fp o ON o."OFFP_ID" = eq."OFFPEQ_OFFP_ID"
        LEFT JOIN core.employees e
               ON e.employee_code = eq."OFFPEQ_E_ID"::text
              -- Q.161.B BUGFIX — CAST explícito: `.bindparams(tenant_id=str(...))`
              -- força o tipo VARCHAR no protocolo asyncpg, e `uuid = varchar` é
              -- inválido em PG → a query rebenta e ABORTA a tx do load inteiro
              -- (open_orders=0). O cast resolve sem depender da inferência.
              AND e.tenant_id = CAST(:tenant_id AS uuid)
        WHERE eq."OFFPEQ_E_ID" IS NOT NULL
          AND o."OFFP_FP_ID" IS NOT NULL
          AND (e.employee_code IS NULL OR e.status = 'ACTIVE')
        """
    )
    # bind tenant_id so the LEFT JOIN is scoped correctly
    sql = sql.bindparams(tenant_id=str(tenant_id))
    try:
        rows = (await session.execute(sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.126.D skills DB load skipped: %s", exc)
        return {}
    matrix: Dict[str, Set[str]] = {}
    for r in rows:
        fase_id = str(r["fase_id"])
        func_id = str(r["func_id"])
        if fase_id and func_id:
            matrix.setdefault(fase_id, set()).add(func_id)
    return matrix


async def _load_qualified_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, Set[str]]:
    """Q.158.B — gate DECLARADO de polivalência (a "matriz definida na
    Entidade_Fase" do Nuno): ``hr.employee_skills.is_certified = True``, keyed
    ``fase_id`` (skill_code = FP_ID) → ``{employee_code (= E_ID)}``. Só ACTIVE.

    Inerte enquanto o mirror Q.158.A não correr (``is_certified`` default False
    → {} → o gate não se aplica, back-compat exacto). Quando a matriz declarada
    existe, É a verdade (axioma 5: competência real declarada, não inventada).
    O histórico ``of_fp`` deixa de ser o gate e alimenta só o ranking.

    Q.167.G — exclui qualificações EXPIRADAS (``certification_expiry`` =
    ``EFP_DATAFIM`` no passado): a associação entidade↔fase terminou, logo a
    pessoa já não pode fazer a fase. ``NULL`` = qualificação ainda activa."""
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    sql = text(
        """
        SELECT DISTINCT s.skill_code     AS fase_id,
                        e.employee_code  AS func_id
        FROM hr.employee_skills es
        JOIN hr.skills s        ON s.id = es.skill_id
        JOIN core.employees e   ON e.id = es.employee_id
        -- Q.161.B BUGFIX — CAST explícito (ver _load_skills_db): bindparams
        -- str força VARCHAR → `uuid = varchar` aborta a tx do load.
        WHERE es.tenant_id = CAST(:t AS uuid)
          AND es.is_certified = true
          AND e.status = 'ACTIVE'
          AND s.skill_code IS NOT NULL
          AND e.employee_code IS NOT NULL
          -- Q.167.G — qualificação EXPIRADA (EFP_DATAFIM no passado) não gateia:
          -- quem já não faz a fase não pode entrar no pool (axioma 5 — competência
          -- real, não histórica). NULL = ainda activa.
          AND (es.certification_expiry IS NULL OR es.certification_expiry >= CURRENT_DATE)
        """
    ).bindparams(t=str(tenant_id))
    try:
        rows = (await session.execute(sql)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — tabela ausente / outage
        logger.debug("Q.158.B qualified gate load skipped: %s", exc)
        return {}
    matrix: Dict[str, Set[str]] = {}
    for r in rows:
        fase_id = str(r["fase_id"])
        func_id = str(r["func_id"])
        if fase_id and func_id:
            matrix.setdefault(fase_id, set()).add(func_id)
    return matrix


def _apply_qualification_gate(
    history: Dict[str, Set[str]],
    qualified: Dict[str, Set[str]],
) -> Dict[str, Set[str]]:
    """Q.158.B — aplica o gate declarado (Entidade_Fase) por fase.

    Para cada fase com qualificações declaradas, o pool elegível É o conjunto
    qualificado (a Entidade_Fase = quem PODE). Fases sem dados declarados
    mantêm o histórico (partial-safe, nunca regride a vazio). ``qualified``
    vazio → devolve o histórico intacto (back-compat exacto). Função pura."""
    if not qualified:
        return history
    merged: Dict[str, Set[str]] = dict(history)
    for fase_id, pool in qualified.items():
        merged[fase_id] = set(pool)
    return merged


async def _load_active_operators_db(
    session: Any,
    tenant_id: UUID,
) -> Set[str]:
    """Q.160 — set canónico de "operador ativo" (employee_code = E_ID::text).

    Lê `factory_raw.v_active_operators` (E_ACTIVO + trabalho nos últimos 2 meses,
    ~107). Verifica a existência da view via information_schema ANTES de a ler,
    para não abortar a transação se ela faltar (dev/test sem sync) → devolve
    ``set()`` nesse caso. Set vazio = filtro inerte (back-compat exacto)."""
    if session is None:
        return set()
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    try:
        exists = (
            await session.execute(
                text(
                    "SELECT 1 FROM information_schema.views "
                    "WHERE table_schema = 'factory_raw' "
                    "AND table_name = 'v_active_operators'"
                )
            )
        ).scalar()
        if not exists:
            return set()
        rows = (
            await session.execute(
                text("SELECT e_id::text AS code FROM factory_raw.v_active_operators")
            )
        ).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — outage / missing table
        logger.debug("Q.160 active operators load skipped: %s", exc)
        return set()
    return {str(r["code"]) for r in rows if r["code"]}


def _apply_active_operator_filter(
    matrix: Dict[str, Set[str]],
    active: Set[str],
) -> Dict[str, Set[str]]:
    """Q.160 — restringe cada pool de fase aos operadores ATIVOS (últimos 2 meses).

    Filtro **input-only**, estritamente mais restritivo (axioma 5 — nunca alarga
    o pool). Guarda de não-vazio: se a interseção esvaziar uma fase que TINHA
    operadores, mantém o pool original (ex.: Injeção, sem trabalho em 60d) — e
    mesmo que esvaziasse, o decoder agenda a fase como manual, nunca inviável.
    ``active`` vazio → devolve a matriz intacta (back-compat exacto). Função pura.
    """
    if not active:
        return matrix
    filtered: Dict[str, Set[str]] = {}
    for fase_id, pool in matrix.items():
        narrowed = pool & active
        filtered[fase_id] = narrowed if narrowed else set(pool)
    return filtered


async def _load_sector_preferences_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[Tuple[str, str], float]:
    """Q.140.F — preferência por (employee_code, fase_id) ∈ [0,1] para o CPO.

    Deriva do nível por sector (override manual > derivado do histórico real
    > semente ERP), via `SectorPreferenceService.phase_preference_map`. Keyed
    por `employee_code` (= a chave do skill_matrix do CPO) — o serviço já
    resolve o gap UUID↔employee_code internamente. Best-effort: serviço/tabela
    ausente ou vazia → {} (back-compat exacto: o decoder usa skill_count).
    NUNCA usa € (CoeficienteX) — só nível/qualidade/afinidade.
    """
    if session is None:
        return {}
    try:
        from src.workforce.sector_preference_service import (
            SectorPreferenceService,
        )
    except ImportError as exc:  # pragma: no cover — workforce ausente
        logger.debug("Q.140.F sector preferences skipped (import): %s", exc)
        return {}
    try:
        return await SectorPreferenceService(session, tenant_id).phase_preference_map()
    except Exception as exc:  # pragma: no cover — best-effort
        logger.warning("Q.140.F sector preferences load failed: %s", exc)
        return {}


async def _load_boat_complexity_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, float]:
    """Q.155.D — ICB [0,1] por product_id (= P_ID = op.model_id) do barco.

    Best-effort: tabela ausente / session None → {} (sem boost, back-compat)."""
    if session is None:
        return {}
    try:
        from sqlalchemy import text

        rows = (
            await session.execute(
                text(
                    "SELECT product_id, complexity_score "
                    "FROM governance.boat_complexity WHERE tenant_id = :t"
                ),
                {"t": str(tenant_id)},
            )
        ).all()
        return {str(r[0]): float(r[1]) for r in rows}
    except Exception as exc:  # pragma: no cover — best-effort
        logger.debug("Q.155.D boat_complexity load skipped: %s", exc)
        return {}


async def _load_phase_preferred_operators_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, List[str]]:
    """Q.155.D — melhores curados por fase: phase_id → [employee_code,…] (rank).

    Best-effort: tabela ausente / session None → {} (cai no sector/skill)."""
    if session is None:
        return {}
    try:
        from sqlalchemy import text

        rows = (
            await session.execute(
                text(
                    "SELECT phase_id, employee_code FROM "
                    "governance.phase_preferred_operator "
                    "WHERE tenant_id = :t ORDER BY phase_id, rank"
                ),
                {"t": str(tenant_id)},
            )
        ).all()
        out: Dict[str, List[str]] = {}
        for phase_id, code in rows:
            out.setdefault(str(phase_id), []).append(str(code))
        return out
    except Exception as exc:  # pragma: no cover — best-effort
        logger.debug("Q.155.D phase_preferred_operators load skipped: %s", exc)
        return {}


async def _load_open_orders_db(
    session: Any,
    tenant_id: UUID,
    scope: str = "boats_only",
    staleness_months: int | None = None,
    plan_cap: int | None = None,
) -> List[Dict[str, Any]]:
    """Q.126.B — real WIP from `factory_raw.ordemfabrico`: open orders
    (`OF_DATAFIM` NULL) whose current phase (`OF_FP_ID`) is a production phase
    (`FP_PRODUCAO=true`, which already excludes Entregue/Armazem/Embalado/...).
    ``modelo_id=OF_P_ID``, deadline = COALESCE of the real date columns.
    Best-effort, capped. Only used when no curated open_orders are present.

    Q.157.B (corrigido) — a data-alvo é 95% preenchida e 53% FUTURA nos BARCOS
    (``OF_PLANO_DATA_PREVISTA`` 95%/48%, COALESCE 95%/53%; ``OF_DATAENTREGA`` 0%).
    A medição "0.5%" anterior era na população errada — todas as OFs abertas, 99%
    acessórios. Por isso a selecção é: **barcos com prazo planeado FUTURO primeiro**
    (por prazo asc = mais urgente), depois os restantes (sem prazo futuro / data-
    lixo no passado) **FIFO por antiguidade de criação** (``OF_DATA``). O
    ``data_entrega_prevista`` (COALESCE de datas reais) alimenta o
    backward-scheduling como due_date — os 53% com prazo futuro são honrados.

    Q.136.A — `scope` (config `planning.scope`): `boats_only` (default) planeia
    SÓ barcos (raiz de `PRODUTO_TIPO` = Kayak TP_ID=1 AND OF_ID<10M); sem isto
    ~56% do WIP são acessórios/componentes (Banco/Leme/Strap…). `all` =
    comportamento legacy (LEFT JOIN não dropa nada → back-compat exacto).

    Q.157.H — critério deck+casco substituído por join a
    `factory_raw.v_of_is_boat` (is_boat = raiz=Kayak AND OF_ID<10M). Valida
    811/811 barcos reais + exclui pagaias TP331 (OF_ID≥10M).

    Q.136.B — devolve `current_fase_id` (= `OF_FP_ID`) para o RoutingResolver
    truncar a rota à fase atual (não re-planear fases já feitas).

    Q.158 — regra EXATA da NELO de "em produção" (query real do `/OrdemFabrico`,
    verificada na BD MAR-KAYAKS): a OF só entra se a **fase atual** (`OF_FP_ID`)
    tiver uma operação POR TERMINAR em `of_fp` (`OFFP_DATAFIM` NULL) E a OF tiver
    cliente de encomenda (`OF_E_ID_ENC` → `entidade`). Substitui a heurística de
    staleness por meses (Q.158.G): o EXISTS é o gate canónico — exclui zombies
    (open sem op aberta na fase atual) e inclui reparações em OFs já fechadas
    (sem depender de `OF_DATAFIM`). Scope ≈ 1209 (= origem NELO: nova+fila+
    reparações). Input-only e estritamente alinhado com a fábrica (axioma Spelke
    5: só muda o pool de entrada, não decoder/fitness/safety_net).

    Q.158 — `is_reparacao` (`OF_FP_ID IN {14,76,77}`) viaja em cada ordem para
    lane/UI/prioridade. O decoder trunca a rota à fase atual (`current_fase_id`/
    `completed_fase_ids`), pelo que uma reparação (sem rota forward) agenda só a
    op aberta dessa fase.

    Q.158.G — `staleness_months` fica como guarda secundária OPCIONAL (config,
    default 0/OFF — superado pelo EXISTS). Quando truthy, adiciona o predicado de
    vida recente (atividade em `of_fp` OU criação) — só reduz o pool, nunca
    alarga. `0`/`None` ⇒ ausente (o caso normal pós-Q.158).

    Q.161.A — `plan_cap` separa o horizonte por contexto: `None` (default) ⇒ o
    horizonte interativo de 200 (botão "Replanear", responsivo); `<= 0` ⇒ TODOS os
    em-produção (tecto `_OPEN_ORDERS_HARD_CAP` para a GA não afogar) — usado pelo
    robô de fundo, que corre com `time_limit` maior; `> 0` ⇒ esse valor (clamp ao
    tecto). Não muda o predicado (input-only, Spelke 5) — só quantas ordens entram.

    Q.161.A — REPARAÇÕES primeiro: a prioridade `is_reparacao` (fase em {14,76,77})
    entra no `ORDER BY` ANTES do `LIMIT` (`repair_rank`), senão as reparações —
    prazo passado/ausente, criação antiga — caíam sempre abaixo do cap e nunca eram
    planeadas. Barco de cliente que volta para reparação fica no topo do horizonte."""
    from src.plan.cpo.state import REPAIR_PHASE_IDS

    # Q.161.A — fragmento SQL dos ids de fase de reparação (DRY com REPAIR_PHASE_IDS).
    _repair_ids_sql = ", ".join(str(int(x)) for x in sorted(REPAIR_PHASE_IDS, key=int))

    if session is None:
        return []
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    # Q.157.H — critério raiz=Kayak AND OF_ID<10M (via v_of_is_boat).
    # Substitui o critério deck+casco que perdia C1/Nacra/Prepreg e incluía pagaias.
    # scope="boats_only": JOIN INNER a v_of_is_boat filtrando is_boat=true.
    # scope="all": sem join extra → back-compat exacto (não dropa órfãos).
    # Q.157.H / Q.167.D — scope:
    #   "boats_only"      → só barcos (INNER v_of_is_boat).
    #   "boats_and_molds" → barcos UNION moldes-em-reparação (opt-in). O ramo dos
    #                       barcos é BYTE-IDÊNTICO ao boats_only → zero regressão.
    #   "all"             → sem join extra (back-compat).
    if scope in ("boats_only", "boats_and_molds"):
        boats_join = (
            "JOIN factory_raw.v_of_is_boat vb"
            ' ON vb.of_id = ofb."OF_ID" AND vb.is_boat = true'
        )
    else:
        boats_join = ""

    # Q.167.D — moldes em reparação entram como ramo UNION separado (decisão Luís:
    # moldes no scope). Molde = P_TP_ID=82 (v_of_is_mold); em reparação = fase atual
    # em {13,14} com op aberta (= getMoldesAReparar, 23 live). São route-truncated
    # single-op (como as reparações de barco); operadores de molde existem na
    # skill-matrix (fase 14 = 23 activos) → o axioma skill-match atribui o reparador
    # certo. NÃO exige cliente de encomenda (moldes não são encomendas). `is_mold`
    # viaja para lane/UI; `repair_rank=0` (prioridade de reparação).
    molds_union = ""
    if scope == "boats_and_molds":
        molds_union = """
          UNION ALL
          SELECT ofb."OF_ID"::text   AS of_id,
                 ofb."OF_P_ID"::text AS modelo_id,
                 ofb."OF_FP_ID"::text AS current_fase_id,
                 0 AS repair_rank,
                 COALESCE(NULLIF(ofb."OF_DATAENTREGA", ''),
                          NULLIF(ofb."OF_TR_DATA_PREVISTA", ''),
                          NULLIF(ofb."OF_PLANO_DATA_PREVISTA", '')) AS data_entrega_prevista,
                 NULLIF(ofb."OF_DATA", '') AS of_data_sort,
                 true AS is_mold
          FROM factory_raw.ordemfabrico ofb
          JOIN factory_raw.fases_producao f ON f."FP_ID" = ofb."OF_FP_ID"
          JOIN factory_raw.v_of_is_mold vm ON vm.of_id = ofb."OF_ID" AND vm.is_mold = true
          WHERE ofb."OF_P_ID" IS NOT NULL
            AND f."FP_PRODUCAO" = true
            AND ofb."OF_FP_ID" IN (13, 14)
            AND EXISTS (
              SELECT 1 FROM factory_raw.of_fp op
              WHERE op."OFFP_OF_ID" = ofb."OF_ID"
                AND op."OFFP_FP_ID" = ofb."OF_FP_ID"
                AND NULLIF(op."OFFP_DATAFIM", '') IS NULL
            )"""

    # Q.158.G — predicado de WIP ACTIVO (só quando staleness_months truthy):
    # actividade recente em of_fp OU criação recente. GREATEST(...,'epoch') p/ datas
    # vazias/sentinela não rebentarem o ::timestamp; NULLIF tira ''→NULL.
    staleness_pred = ""
    if staleness_months:
        staleness_pred = """
            AND (
              EXISTS (
                SELECT 1 FROM factory_raw.of_fp op
                WHERE op."OFFP_OF_ID" = ofb."OF_ID"
                  AND GREATEST(
                        COALESCE(NULLIF(op."OFFP_DATAINICIO", '')::timestamp, 'epoch'::timestamp),
                        COALESCE(NULLIF(op."OFFP_DATAFIM", '')::timestamp, 'epoch'::timestamp)
                      ) >= now() - make_interval(months => :staleness_months)
              )
              OR NULLIF(ofb."OF_DATA", '')::timestamp
                   >= now() - make_interval(months => :staleness_months)
            )"""
    sql = text(
        f"""
        -- Q.158 — inclui done_fase_ids: array de OFFP_FP_ID::text com
        -- OFFP_DATAFIM preenchido para este barco. Fonte de verdade para
        -- o RoutingResolver não re-planear fases já concluídas.
        WITH done AS (
          SELECT op."OFFP_OF_ID"::text AS of_id,
                 array_agg(op."OFFP_FP_ID"::text) AS done_fase_ids
          FROM factory_raw.of_fp op
          WHERE op."OFFP_DATAFIM" IS NOT NULL
          GROUP BY op."OFFP_OF_ID"
        )
        SELECT q.of_id, q.modelo_id, q.current_fase_id,
               q.data_entrega_prevista, q.is_mold,
               COALESCE(done.done_fase_ids, ARRAY[]::text[]) AS done_fase_ids
        FROM (
          SELECT ofb."OF_ID"::text   AS of_id,
                 ofb."OF_P_ID"::text AS modelo_id,
                 ofb."OF_FP_ID"::text AS current_fase_id,
                 -- Q.161.A — reparação (fase {14,76,77}) = prioridade 0 no ORDER
                 -- BY, ANTES do LIMIT: garante que barcos de cliente que voltam
                 -- para reparação entram no horizonte (senão caíam abaixo do cap).
                 CASE WHEN ofb."OF_FP_ID" IN ({_repair_ids_sql}) THEN 0 ELSE 1 END
                   AS repair_rank,
                 -- NULLIF: '' (vazio) → NULL, senão o ::timestamp do ORDER BY rebenta.
                 COALESCE(NULLIF(ofb."OF_DATAENTREGA", ''),
                          NULLIF(ofb."OF_TR_DATA_PREVISTA", ''),
                          NULLIF(ofb."OF_PLANO_DATA_PREVISTA", '')) AS data_entrega_prevista,
                 NULLIF(ofb."OF_DATA", '') AS of_data_sort,
                 false AS is_mold
          FROM factory_raw.ordemfabrico ofb
          JOIN factory_raw.fases_producao f ON f."FP_ID" = ofb."OF_FP_ID"
          -- Q.158 — INNER JOIN: a OF tem de ter cliente de encomenda (a regra
          -- da NELO exige-o; barcos de stock sem cliente caem fora).
          JOIN factory_raw.entidade cli ON cli."E_ID" = ofb."OF_E_ID_ENC"
          {boats_join}
          WHERE ofb."OF_P_ID" IS NOT NULL
            AND f."FP_PRODUCAO" = true
            -- Q.158 — regra EXATA NELO (CROSS APPLY do /OrdemFabrico): operação
            -- POR TERMINAR na FASE ATUAL. Gate canónico — sem OF_DATAFIM, sem
            -- staleness. Exclui zombies (open sem op na fase atual); inclui
            -- reparações em OFs já fechadas (que voltaram).
            AND EXISTS (
              SELECT 1 FROM factory_raw.of_fp op
              WHERE op."OFFP_OF_ID" = ofb."OF_ID"
                AND op."OFFP_FP_ID" = ofb."OF_FP_ID"
                AND NULLIF(op."OFFP_DATAFIM", '') IS NULL
            ){staleness_pred}{molds_union}
        ) q
        LEFT JOIN done ON done.of_id = q.of_id
        ORDER BY
          -- Q.161.A — REPARAÇÕES primeiro (repair_rank 0), antes de qualquer prazo:
          -- barco de cliente de volta para reparação não pode cair abaixo do cap.
          q.repair_rank ASC,
          -- Q.157.B (corrigido): a data-alvo NÃO é 99.5% nula nos BARCOS — é 95%
          -- preenchida, 53% futura (medi antes na população errada: todas as OFs,
          -- 99% acessórios). Por isso: barcos com PRAZO PLANEADO FUTURO primeiro
          -- (por prazo asc = mais urgente), depois os restantes (sem prazo futuro,
          -- ou data-lixo no passado) FIFO por antiguidade de criação (OF_DATA).
          CASE WHEN q.data_entrega_prevista IS NOT NULL
                    AND q.data_entrega_prevista::timestamp > now() THEN 0 ELSE 1 END,
          CASE WHEN q.data_entrega_prevista IS NOT NULL
                    AND q.data_entrega_prevista::timestamp > now()
               THEN q.data_entrega_prevista::timestamp END ASC,
          q.of_data_sort ASC
        LIMIT :plan_cap
        """
    )
    # Q.161.A — cap efetivo por contexto (ver docstring):
    #   None       → 200 (horizonte interativo, default)
    #   <= 0       → todos os em-produção (tecto de segurança da GA)
    #   > 0        → esse valor (clamp ao tecto)
    if plan_cap is None:
        effective_cap = _OPEN_ORDERS_PLAN_CAP
    elif plan_cap <= 0:
        effective_cap = _OPEN_ORDERS_HARD_CAP
    else:
        effective_cap = min(int(plan_cap), _OPEN_ORDERS_HARD_CAP)
    params: Dict[str, Any] = {"plan_cap": effective_cap}
    if staleness_months:
        params["staleness_months"] = int(staleness_months)
    try:
        rows = (await session.execute(sql, params)).mappings().all()
    except SQLAlchemyError as exc:  # pragma: no cover — DB outage / missing table
        logger.debug("Q.126.B open_orders DB load skipped: %s", exc)
        return []
    # Q.136.A — visibilidade: scope=boats_only exclui acessórios/componentes (e
    # barcos sem match em `produto`, ex. catálogo incompleto) — não é silencioso.
    # Q.158 — gate canónico = regra em-produção (EXISTS); staleness é guarda
    # opcional (off por defeito) e também aparece aqui quando ligada.
    logger.info(
        "open_orders DB: scope=%s staleness=%s cap=%d → %d ordens",
        scope, f"{staleness_months}m" if staleness_months else "off",
        effective_cap, len(rows),
    )
    return [
        {
            "of_id": str(r["of_id"]),
            "order_id": str(r["of_id"]),
            "modelo_id": str(r["modelo_id"]),
            "current_fase_id": (
                str(r["current_fase_id"]) if r["current_fase_id"] is not None else None
            ),
            # Q.158 — reparação = fase atual em {14,76,77} (barco entregue/em-uso
            # que voltou). Lane/UI/prioridade; o decoder agenda a op aberta da
            # fase atual (rota truncada).
            "is_reparacao": (
                str(r["current_fase_id"]) in REPAIR_PHASE_IDS
                if r["current_fase_id"] is not None
                else False
            ),
            # Q.167.D — molde em reparação (scope=boats_and_molds). Default false
            # (barcos). Lane/UI + permite ao decoder/UI distinguir molde de barco.
            "is_mold": bool(r["is_mold"]),
            # Q.158 — fases já concluídas (OFFP_DATAFIM preenchido); lista de
            # fase_id (texto). O RoutingResolver usa-as para nunca re-planear
            # trabalho já feito. Pode ser None quando PostgreSQL devolve NULL
            # para ARRAY[]::text[] em alguns drivers (tratado no resolver).
            "completed_fase_ids": list(r["done_fase_ids"]) if r["done_fase_ids"] else [],
        }
        for r in rows
    ]


async def _load_phase_transition_gaps(
    session: Any,
    tenant_id: UUID,
) -> Dict[Tuple[str, str], float]:
    """Load curing/drying gaps from the DB, fall back to the seed.

    Returns a dict keyed by (from_phase_code, to_phase_code) — both
    normalized via `normalize_phase_code`.
    """
    from src.plan.cpo.state import NELO_CURING_GAPS_SEED, normalize_phase_code

    seed: Dict[Tuple[str, str], float] = {
        (normalize_phase_code(a), normalize_phase_code(b)): float(h)
        for (a, b, h, _reason, _n) in NELO_CURING_GAPS_SEED
    }

    if session is None:
        return seed

    try:
        from sqlalchemy import select

        from src.plan.models.phase_gap import PhaseTransitionGap

        stmt = (
            select(PhaseTransitionGap)
            .where(PhaseTransitionGap.tenant_id == tenant_id)
            .where(PhaseTransitionGap.active.is_(True))
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    except Exception as exc:  # pragma: no cover — defensive (table absent etc.)
        logger.debug(f"phase_transition_gap DB load failed, using seed: {exc}")
        return seed

    if not rows:
        return seed

    db_gaps: Dict[Tuple[str, str], float] = {}
    for row in rows:
        key = (
            normalize_phase_code(row.from_phase_code),
            normalize_phase_code(row.to_phase_code),
        )
        if not key[0] or not key[1]:
            continue
        db_gaps[key] = float(row.min_gap_hours)

    # Seed entries the DB didn't override — this lets partial overrides
    # per tenant work without losing the physical NELO defaults.
    merged: Dict[Tuple[str, str], float] = dict(seed)
    merged.update(db_gaps)
    return merged


async def _load_confirmed_preference_rules(
    session: Any,
    tenant_id: UUID,
) -> List[Dict[str, Any]]:
    """Return the CONFIRMED PreferenceRule rows for this tenant as plain
    dicts. Swallows any failure (missing schema on a fresh test DB,
    governance module not installed, etc.) and returns an empty list so
    the scheduler boot path stays resilient.
    """
    if session is None:
        return []
    try:
        from sqlalchemy import and_, select

        from src.governance.models import (
            PreferenceRule,
            PreferenceRuleStatus,
        )

        stmt = select(PreferenceRule).where(
            and_(
                PreferenceRule.tenant_id == tenant_id,
                PreferenceRule.status == PreferenceRuleStatus.CONFIRMED.value,
            )
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()
    except Exception as exc:  # pragma: no cover — defensive (table absent etc.)
        logger.debug(f"preference_rule DB load skipped: {exc}")
        return []

    return [
        {
            "id": str(r.id),
            "type": r.type,
            "description": r.description,
            "predicate": dict(r.predicate or {}),
            "confidence": float(r.confidence),
        }
        for r in rows
    ]


def _extract_error_rates(engine: Any) -> Dict[str, float]:
    """
    Compute per-phase error rate: count of CuratedQualityEvent per fase_id,
    divided by CuratedOrderPhase count for that phase. Best-effort, returns
    empty dict if shape doesn't match.
    """
    try:
        active_id = getattr(engine, "_active_ingestion_id", None)
        curated = getattr(engine, "_curated_data", {}) or {}
        scope = curated.get(active_id, {}) if active_id else {}

        errors = scope.get("quality_events") or scope.get("CuratedQualityEvent") or []
        phases = scope.get("order_phases") or scope.get("CuratedOrderPhase") or []

        phase_counts: Dict[str, int] = {}
        for p in phases:
            fid = str(getattr(p, "fase_id", ""))
            if fid:
                phase_counts[fid] = phase_counts.get(fid, 0) + 1

        error_counts: Dict[str, int] = {}
        for e in errors:
            fid = str(getattr(e, "fase_id", "") or getattr(e, "fase_culpada_id", ""))
            if fid:
                error_counts[fid] = error_counts.get(fid, 0) + 1

        rates: Dict[str, float] = {}
        for fid, n_phase in phase_counts.items():
            n_err = error_counts.get(fid, 0)
            if n_phase > 0:
                rates[fid] = min(1.0, n_err / n_phase)
        return rates
    except Exception as e:
        logger.debug(f"error rate extraction failed: {e}")
        return {}


# ---------------------------------------------------------------------------
# Q.135.F3 — phase config overrides loader
# ---------------------------------------------------------------------------


async def _load_plan_exclusions_db(
    session: Any,
    tenant_id: UUID,
) -> Set[str]:
    """Q.153.C1 — order_ids excluídos/adiados do plano (plan.plan_exclusion).

    Devolve o conjunto de `order_id` (str) a EXCLUIR do plano. Best-effort:
    session None / tabela ausente → ``set()`` (back-compat). Espelha o padrão
    de `_load_phase_config_db`.
    """
    if session is None:
        return set()
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    sql = text(
        """
        SELECT order_id::text AS order_id
        FROM plan.plan_exclusion
        WHERE tenant_id = :tenant
        """
    )
    try:
        rows = (await session.execute(
            sql, {"tenant": str(tenant_id)}
        )).mappings().all()
    except SQLAlchemyError as exc:
        logger.debug("Q.153.C1 plan_exclusion DB load skipped: %s", exc)
        return set()
    return {str(r["order_id"]) for r in rows}


async def _load_phase_config_db(
    session: Any,
    tenant_id: UUID,
) -> Dict[str, Dict[str, Any]]:
    """Q.135.F3 — overrides de configuração de fase de `plan.phase_config`.

    Devolve ``{fase_id: {"team_size_override": int|None,
                          "num_stations_override": int|None,
                          "allowed_worker_ids": list[str]|None}}``.
    Best-effort: session None / tabela ausente → ``{}`` (back-compat).
    Espelha o padrão de `_load_phase_calibration_db`.
    """
    if session is None:
        return {}
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    sql = text(
        """
        SELECT phase_id::text            AS phase_id,
               team_size_override        AS team_size_override,
               num_stations_override     AS num_stations_override,
               allowed_worker_ids        AS allowed_worker_ids
        FROM plan.phase_config
        WHERE tenant_id = :tenant
        """
    )
    try:
        rows = (await session.execute(
            sql, {"tenant": str(tenant_id)}
        )).mappings().all()
    except SQLAlchemyError as exc:
        logger.debug("Q.135.F3 phase_config DB load skipped: %s", exc)
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        out[str(r["phase_id"])] = {
            "team_size_override": r["team_size_override"],
            "num_stations_override": r["num_stations_override"],
            "allowed_worker_ids": list(r["allowed_worker_ids"]) if r["allowed_worker_ids"] else None,
        }
    return out
