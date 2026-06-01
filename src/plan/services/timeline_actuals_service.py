"""Q.141 — Actuals da linha temporal: o que ACONTECEU (passado real) por intervalo.

Alimenta o lado PASSADO da timeline /overall (o futuro vem do plano CPO).
Read-only, best-effort (tabela ausente/erro → vazio, nunca 5xx — padrão
`/transport/ready`). Tenant-scoped na camada limpa (`plan.fases_of_history`,
RLS); `factory_raw.*` é o espelho ERP partilhado (NÃO filtrar por tenant).

Fonte das fases: `factory_raw.of_fp` (OFFP_DATAINICIO/DATAFIM, texto ISO) — o
registo REAL e POPULADO do ERP (~537k linhas, DATAFIM até hoje). NÃO se usa
`plan.fases_of_history` porque o espelho limpo está VAZIO neste deployment (o
ETL incremental ainda não correu). `of_fp` é tenant-agnóstico (espelho ERP
partilhado) → NÃO filtrar por tenant. Comparação por texto ISO (zero-padded →
ordem lexicográfica == cronológica), evitando casts que rebentam em linhas sujas.

Dimensões (Q.141.A–C):
* BARCOS & FASES — de `factory_raw.of_fp` (OFFP_DATAINICIO/FIM), nomes
  resolvidos via `factory_raw.{ordemfabrico,produto,fases_producao}` (Q.141.A).
* OPERADORES — `factory_raw.offp_eq ⋈ of_fp ⋈ entidade` (Q.141.B). NÃO se usa
  `fases_of_history.worker_id` porque o ETL grava-o SEMPRE NULL
  (`adapters/nelo/etl/phase_history.py`).
* EXPEDIÇÕES — `factory_raw.transp_of` (TROF_ENVIADO + TR_DATA) (Q.141.C).

As funções de SHAPING são puras (sem BD) → testáveis isoladamente, como
`plan_vs_actual._compute_report`.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import NAMESPACE_OID, UUID, uuid5

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Cap de linhas cruas devolvidas (intervalos largos agregam por dia — Q.141.D).
DEFAULT_CAP = 5000

# ── SQL ──────────────────────────────────────────────────────────────────────

# Fases que ARRANCARAM no intervalo [lower, upper) — ancoradas ao dia de início.
# Escolha deliberada (vs overlap COALESCE(fim, now)): muitas linhas de of_fp têm
# DATAFIM vazia por NÃO registarem fim (ex. "Entregue"/"Armazem"), não por
# estarem em curso; o overlap-até-agora arrastava lixo de 2024 para janelas de
# 2026. "O que aconteceu nestes dias" = o que começou nestes dias (inclui em
# curso, fim NULL). OFFP_DATA* são texto ISO → comparação lexicográfica ==
# cronológica. factory_raw partilhado → SEM filtro de tenant.
_FASES_BY_RANGE_SQL = text(
    """
    SELECT o."OFFP_ID"::text             AS offp_id,
           o."OFFP_OF_ID"::text          AS of_id,
           o."OFFP_FP_ID"::text          AS phase_id,
           o."OFFP_DATAINICIO"           AS fase_inicio,
           NULLIF(o."OFFP_DATAFIM", '')  AS fase_fim
    FROM factory_raw.of_fp o
    WHERE o."OFFP_OF_ID" IS NOT NULL
      AND o."OFFP_FP_ID" IS NOT NULL
      AND o."OFFP_DATAINICIO" IS NOT NULL
      AND o."OFFP_DATAINICIO" >= :lower
      AND o."OFFP_DATAINICIO" < :upper
    ORDER BY o."OFFP_DATAINICIO" DESC
    LIMIT :cap
    """
)

# OF_ID → (OF_P_ID modelo, P_NOME barco, is_boat). LEFT JOIN: of sem produto →
# barco None / is_boat False. Q.153.C0 — is_boat = predicado boats-only Q.136
# (P_QTDDECK>0 AND P_QTDCASCO>0), o MESMO que o CPO aplica na geração do plano,
# para o /overall poder focar barcos vs acessórios/straps nos realizados.
_NOMES_OF_SQL = text(
    """
    SELECT o."OF_ID"::text   AS of_id,
           o."OF_P_ID"::text AS modelo_id,
           p."P_NOME"        AS barco_nome,
           (p."P_QTDDECK" > 0 AND p."P_QTDCASCO" > 0) AS is_boat
    FROM factory_raw.ordemfabrico o
    LEFT JOIN factory_raw.produto p ON p."P_ID" = o."OF_P_ID"
    WHERE o."OF_ID"::text = ANY(:of_ids)
    """
)

# FP_ID → FP_NOME.
_NOMES_FASE_SQL = text(
    """
    SELECT "FP_ID"::text AS fase_id, "FP_NOME" AS fase_nome
    FROM factory_raw.fases_producao
    WHERE "FP_ID"::text = ANY(:fase_ids)
    """
)

# Q.141.B — operador(es) por fase-de-OF: of_fp.OFFP_ID → offp_eq → entidade.
# NÃO se usa plan.fases_of_history.worker_id porque o ETL grava-o SEMPRE NULL
# (src/adapters/nelo/etl/phase_history.py). Esta é a cadeia real (a mesma do
# sector_preference_service). OFFPEQ_CHEFE marca o líder da equipa.
_WORKERS_BY_OFFP_SQL = text(
    """
    SELECT eq."OFFPEQ_OFFP_ID"::text AS offp_id,
           eq."OFFPEQ_E_ID"::text    AS e_id,
           eq."OFFPEQ_CHEFE"         AS is_chefe,
           e."E_NOME"                AS nome
    FROM factory_raw.offp_eq eq
    LEFT JOIN factory_raw.entidade e ON e."E_ID" = eq."OFFPEQ_E_ID"
    WHERE eq."OFFPEQ_OFFP_ID"::text = ANY(:offp_ids)
      AND eq."OFFPEQ_E_ID" IS NOT NULL
    """
)

# Q.141.C — expedições REAIS: transp_of (TROF_ENVIADO) ⋈ transporte (TR_DATA),
# critério canónico do measure_contract.py (Q.82 §4). A data vive em
# `transporte.TR_DATA` (texto ISO), NÃO em OF_DATATRANSPORTE (morto desde 2009).
# transp_of.TROF_TR_ID → transporte.TR_ID.
_EXPEDICOES_SQL = text(
    """
    SELECT tof."TROF_OF_ID"::text AS of_id,
           t."TR_DATA"            AS transport_date,
           o."OF_P_ID"::text      AS modelo_id,
           p."P_NOME"             AS barco_nome
    FROM factory_raw.transp_of tof
    JOIN factory_raw.transporte t ON t."TR_ID" = tof."TROF_TR_ID"
    LEFT JOIN factory_raw.ordemfabrico o ON o."OF_ID" = tof."TROF_OF_ID"
    LEFT JOIN factory_raw.produto p ON p."P_ID" = o."OF_P_ID"
    WHERE tof."TROF_ENVIADO" = true
      AND t."TR_DATA" IS NOT NULL
      AND t."TR_DATA" <> ''
      AND t."TR_DATA" >= :lower
      AND t."TR_DATA" < :upper
    ORDER BY t."TR_DATA" ASC
    LIMIT :cap
    """
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _iso(value: Any) -> Optional[str]:
    """datetime/date → ISO string, ou None. Strings já-ISO passam tal e qual."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _day_bounds(from_d: date, to_d: date) -> Tuple[str, str]:
    """[from, to+1d) como strings ISO de DATA — compara lexicograficamente com o
    texto ISO completo de OFFP_DATA* ('2026-05-01' < '2026-05-01T08:00' < '2026-05-02')."""
    return from_d.isoformat(), (to_d + timedelta(days=1)).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _duration_min(start: Any, end: Any) -> Optional[float]:
    """Minutos entre start e end (ISO/datetime), ou None se faltar/inválido."""
    s, e = _parse_iso(start), _parse_iso(end)
    if s is None or e is None:
        return None
    delta = (e - s).total_seconds() / 60.0
    return round(delta, 1) if delta >= 0 else None


def worker_uuid(e_id: str) -> UUID:
    """UUID determinístico do operador a partir do E_ID do ERP (uuid5)."""
    return uuid5(NAMESPACE_OID, f"operator:{e_id}")


# ── Shaping puro (testável sem BD) ───────────────────────────────────────────

def shape_actuals_items(
    history_rows: List[Dict[str, Any]],
    barco_by_of: Dict[str, Optional[str]],
    modelo_by_of: Dict[str, Optional[str]],
    fase_by_id: Dict[str, Optional[str]],
    is_boat_by_of: Optional[Dict[str, Optional[bool]]] = None,
) -> List[Dict[str, Any]]:
    """Converte linhas cruas de fases_of_history em items canónicos da timeline.

    Item: {of_id, barco_nome, modelo_id, phase_id, phase_nome, worker_id,
    worker_nome, start, end, duration_min, is_boat, source}. `worker_*` ficam
    None aqui (preenchidos em Q.141.B via offp_eq). Fase em curso → end None.
    Nome de fase em falta → cai no próprio phase_id (padrão plan_vs_actual).
    Q.153.C0 — `is_boat` (boats-only Q.136) quando conhecido, senão None (o
    /overall trata None como "desconhecido", não esconde por omissão).
    """
    boat_map = is_boat_by_of or {}
    items: List[Dict[str, Any]] = []
    for r in history_rows:
        of_id = str(r.get("of_id")) if r.get("of_id") is not None else None
        phase_id = str(r.get("phase_id")) if r.get("phase_id") is not None else None
        inicio, fim = r.get("fase_inicio"), r.get("fase_fim")
        dur = r.get("duration_min")
        # of_fp não traz duração; deriva-se de start/end quando ambos existem.
        dur_min = float(dur) if dur is not None else _duration_min(inicio, fim)
        offp_id = str(r.get("offp_id")) if r.get("offp_id") is not None else None
        items.append(
            {
                "id": offp_id,
                "offp_id": offp_id,
                "of_id": of_id,
                "barco_nome": barco_by_of.get(of_id),
                "modelo_id": modelo_by_of.get(of_id),
                "phase_id": phase_id,
                "phase_nome": fase_by_id.get(phase_id) or phase_id,
                "worker_id": None,
                "worker_nome": None,
                "start": _iso(inicio),
                "end": _iso(fim),
                "duration_min": dur_min,
                "is_boat": boat_map.get(of_id),
                "source": "fase",
            }
        )
    return items


def attach_workers(
    items: List[Dict[str, Any]],
    worker_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Preenche worker_nome/worker_id por offp_id (Q.141.B), in-place.

    A equipa (1+ operadores) é agregada num item só (espelha o /overall, que faz
    `workers[0]` + nomes juntos): `worker_nome` = nomes juntos por " + " (chefe
    primeiro), `worker_id` = uuid5 do E_ID do chefe (ou do 1.º). Fases sem
    operador (ex. Cura) ficam com worker_* None — enriquecimento, nunca filtro.
    """
    by_offp: Dict[str, List[Dict[str, Any]]] = {}
    for w in worker_rows:
        offp = str(w.get("offp_id")) if w.get("offp_id") is not None else None
        if offp is None or w.get("e_id") is None:
            continue
        by_offp.setdefault(offp, []).append(w)
    for it in items:
        crew = by_offp.get(it.get("offp_id"))
        if not crew:
            continue
        # Chefe primeiro, depois ordem estável por e_id.
        crew_sorted = sorted(crew, key=lambda w: (not bool(w.get("is_chefe")), str(w.get("e_id"))))
        nomes = [str(w.get("nome") or w.get("e_id")) for w in crew_sorted]
        it["worker_nome"] = " + ".join(nomes)
        it["worker_id"] = str(worker_uuid(str(crew_sorted[0]["e_id"])))
    return items


def shape_expeditions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Q.141.C — items de expedição (barcos que SAÍRAM) de transp_of⋈transporte."""
    out: List[Dict[str, Any]] = []
    for r in rows:
        of_id = str(r.get("of_id")) if r.get("of_id") is not None else None
        out.append(
            {
                "of_id": of_id,
                "barco_nome": r.get("barco_nome"),
                "modelo_id": r.get("modelo_id"),
                "transport_date": _iso(r.get("transport_date")),
                "source": "transp_of",
            }
        )
    return out


def _group_key_label(item: Dict[str, Any], group_by: str) -> Tuple[str, str]:
    if group_by == "fase":
        return (item.get("phase_id") or "?", item.get("phase_nome") or item.get("phase_id") or "?")
    if group_by == "operador":
        # NULs (fases sem operador) numa lane única, sempre ordenada no fim.
        return (item.get("worker_id") or "sem-operador", item.get("worker_nome") or "Sem operador")
    return (item.get("of_id") or "?", item.get("barco_nome") or item.get("of_id") or "?")


def aggregate_by_day(
    items: List[Dict[str, Any]], group_by: str, *, sample_size: int = 5,
) -> List[Dict[str, Any]]:
    """Q.141.D — agrega items por (group × dia) para intervalos grandes (mês).

    `group_by` ∈ {barco, fase, operador}. Cada lane: {group_key, group_label,
    ops_total, days:[{date, ops_count, total_duration_min}], sample:[item,…]}.
    Dias sem ops NÃO aparecem (não se inventa). Ordenado por ops_total desc.
    """
    lanes: Dict[str, Dict[str, Any]] = {}
    for it in items:
        key, label = _group_key_label(it, group_by)
        lane = lanes.setdefault(
            key, {"group_key": key, "group_label": label, "_days": {}, "sample": [], "ops_total": 0}
        )
        day = (it.get("start") or "")[:10]
        d = lane["_days"].setdefault(day, {"date": day, "ops_count": 0, "total_duration_min": 0.0})
        d["ops_count"] += 1
        if it.get("duration_min"):
            d["total_duration_min"] += float(it["duration_min"])
        lane["ops_total"] += 1
        if len(lane["sample"]) < sample_size:
            lane["sample"].append(it)

    out: List[Dict[str, Any]] = []
    for lane in lanes.values():
        days = sorted(lane["_days"].values(), key=lambda x: x["date"])
        for dd in days:
            dd["total_duration_min"] = round(dd["total_duration_min"], 1)
        out.append(
            {
                "group_key": lane["group_key"],
                "group_label": lane["group_label"],
                "ops_total": lane["ops_total"],
                "days": days,
                "sample": lane["sample"],
            }
        )
    out.sort(key=lambda lvl: (-lvl["ops_total"], lvl["group_label"] or ""))
    return out


# ── Service ──────────────────────────────────────────────────────────────────

class TimelineActualsService:
    """O que aconteceu (passado real) por intervalo. Read-only."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self.session = session
        self.tenant_id = tenant_id

    async def _fetch_phase_rows(
        self, from_d: date, to_d: date, cap: int,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Linhas de fases_of_history no intervalo + flag `truncated`."""
        if self.session is None:
            return [], False
        lower, upper = _day_bounds(from_d, to_d)
        try:
            rows = (
                await self.session.execute(
                    _FASES_BY_RANGE_SQL,
                    {"lower": lower, "upper": upper, "cap": cap + 1},
                )
            ).mappings().all()
        except SQLAlchemyError as exc:  # pragma: no cover — tabela ausente/dev
            logger.warning("timeline actuals: fases query failed: %s", exc)
            return [], False
        truncated = len(rows) > cap
        return [dict(r) for r in rows[:cap]], truncated

    async def _resolve_names(
        self, of_ids: List[str], fase_ids: List[str],
    ) -> Tuple[
        Dict[str, Optional[str]],
        Dict[str, Optional[str]],
        Dict[str, Optional[str]],
        Dict[str, Optional[bool]],
    ]:
        """(barco_by_of, modelo_by_of, fase_by_id, is_boat_by_of) — best-effort.

        Q.153.C0 — `is_boat_by_of` (boats-only Q.136) vem da mesma query de nomes.
        """
        barco_by_of: Dict[str, Optional[str]] = {}
        modelo_by_of: Dict[str, Optional[str]] = {}
        fase_by_id: Dict[str, Optional[str]] = {}
        is_boat_by_of: Dict[str, Optional[bool]] = {}
        if self.session is None:
            return barco_by_of, modelo_by_of, fase_by_id, is_boat_by_of
        if of_ids:
            try:
                rows = (
                    await self.session.execute(_NOMES_OF_SQL, {"of_ids": of_ids})
                ).mappings().all()
                for r in rows:
                    barco_by_of[str(r["of_id"])] = r.get("barco_nome")
                    modelo_by_of[str(r["of_id"])] = r.get("modelo_id")
                    ib = r.get("is_boat")
                    is_boat_by_of[str(r["of_id"])] = None if ib is None else bool(ib)
            except SQLAlchemyError as exc:  # pragma: no cover
                logger.warning("timeline actuals: of-names query failed: %s", exc)
        if fase_ids:
            try:
                rows = (
                    await self.session.execute(_NOMES_FASE_SQL, {"fase_ids": fase_ids})
                ).mappings().all()
                for r in rows:
                    fase_by_id[str(r["fase_id"])] = r.get("fase_nome")
            except SQLAlchemyError as exc:  # pragma: no cover
                logger.warning("timeline actuals: fase-names query failed: %s", exc)
        return barco_by_of, modelo_by_of, fase_by_id, is_boat_by_of

    async def actuals_items(
        self, from_d: date, to_d: date, *, cap: int = DEFAULT_CAP,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Items canónicos das fases realizadas no intervalo + `truncated`.

        Q.141.A — só fases/barcos; operadores (Q.141.B) e expedições (Q.141.C)
        entram a seguir. Best-effort → ([], False) quando não há dados.
        """
        rows, truncated = await self._fetch_phase_rows(from_d, to_d, cap)
        if not rows:
            return [], truncated
        of_ids = sorted({str(r["of_id"]) for r in rows if r.get("of_id")})
        fase_ids = sorted({str(r["phase_id"]) for r in rows if r.get("phase_id")})
        barco_by_of, modelo_by_of, fase_by_id, is_boat_by_of = await self._resolve_names(
            of_ids, fase_ids
        )
        items = shape_actuals_items(
            rows, barco_by_of, modelo_by_of, fase_by_id, is_boat_by_of
        )
        # Q.141.B — enriquecer com operadores reais (offp_eq+entidade).
        offp_ids = sorted({str(r["offp_id"]) for r in rows if r.get("offp_id")})
        worker_rows = await self._fetch_workers(offp_ids)
        items = attach_workers(items, worker_rows)
        return items, truncated

    async def _fetch_workers(self, offp_ids: List[str]) -> List[Dict[str, Any]]:
        """Operadores por OFFP_ID (offp_eq ⋈ entidade). Best-effort → []."""
        if self.session is None or not offp_ids:
            return []
        try:
            rows = (
                await self.session.execute(_WORKERS_BY_OFFP_SQL, {"offp_ids": offp_ids})
            ).mappings().all()
        except SQLAlchemyError as exc:  # pragma: no cover
            logger.warning("timeline actuals: workers query failed: %s", exc)
            return []
        return [dict(r) for r in rows]

    async def expeditions(
        self, from_d: date, to_d: date, *, cap: int = DEFAULT_CAP,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Barcos que SAÍRAM no intervalo (transp_of⋈transporte). Best-effort."""
        if self.session is None:
            return [], False
        lower, upper = _day_bounds(from_d, to_d)
        try:
            rows = (
                await self.session.execute(
                    _EXPEDICOES_SQL, {"lower": lower, "upper": upper, "cap": cap + 1},
                )
            ).mappings().all()
        except SQLAlchemyError as exc:  # pragma: no cover — tabela ausente/dev
            logger.warning("timeline actuals: expeditions query failed: %s", exc)
            return [], False
        truncated = len(rows) > cap
        return shape_expeditions([dict(r) for r in rows[:cap]]), truncated
