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
from uuid import UUID

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
    SELECT o."OFFP_OF_ID"::text          AS of_id,
           o."OFFP_FP_ID"::text          AS phase_id,
           o."OFFP_DATAINICIO"           AS fase_inicio,
           NULLIF(o."OFFP_DATAFIM", '')  AS fase_fim
    FROM factory_raw.of_fp o
    WHERE o."OFFP_OF_ID" IS NOT NULL
      AND o."OFFP_FP_ID" IS NOT NULL
      AND o."OFFP_DATAINICIO" IS NOT NULL
      AND o."OFFP_DATAINICIO" >= :lower
      AND o."OFFP_DATAINICIO" < :upper
    ORDER BY o."OFFP_DATAINICIO" ASC
    LIMIT :cap
    """
)

# OF_ID → (OF_P_ID modelo, P_NOME barco). LEFT JOIN: of sem produto → barco None.
_NOMES_OF_SQL = text(
    """
    SELECT o."OF_ID"::text   AS of_id,
           o."OF_P_ID"::text AS modelo_id,
           p."P_NOME"        AS barco_nome
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


# ── Shaping puro (testável sem BD) ───────────────────────────────────────────

def shape_actuals_items(
    history_rows: List[Dict[str, Any]],
    barco_by_of: Dict[str, Optional[str]],
    modelo_by_of: Dict[str, Optional[str]],
    fase_by_id: Dict[str, Optional[str]],
) -> List[Dict[str, Any]]:
    """Converte linhas cruas de fases_of_history em items canónicos da timeline.

    Item: {of_id, barco_nome, modelo_id, phase_id, phase_nome, worker_id,
    worker_nome, start, end, duration_min, source}. `worker_*` ficam None aqui
    (preenchidos em Q.141.B via offp_eq). Fase em curso → end None. Nome de fase
    em falta → cai no próprio phase_id (padrão plan_vs_actual).
    """
    items: List[Dict[str, Any]] = []
    for r in history_rows:
        of_id = str(r.get("of_id")) if r.get("of_id") is not None else None
        phase_id = str(r.get("phase_id")) if r.get("phase_id") is not None else None
        inicio, fim = r.get("fase_inicio"), r.get("fase_fim")
        dur = r.get("duration_min")
        # of_fp não traz duração; deriva-se de start/end quando ambos existem.
        dur_min = float(dur) if dur is not None else _duration_min(inicio, fim)
        items.append(
            {
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
                "source": "fase",
            }
        )
    return items


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
    ) -> Tuple[Dict[str, Optional[str]], Dict[str, Optional[str]], Dict[str, Optional[str]]]:
        """(barco_by_of, modelo_by_of, fase_by_id) — best-effort, em lote."""
        barco_by_of: Dict[str, Optional[str]] = {}
        modelo_by_of: Dict[str, Optional[str]] = {}
        fase_by_id: Dict[str, Optional[str]] = {}
        if self.session is None:
            return barco_by_of, modelo_by_of, fase_by_id
        if of_ids:
            try:
                rows = (
                    await self.session.execute(_NOMES_OF_SQL, {"of_ids": of_ids})
                ).mappings().all()
                for r in rows:
                    barco_by_of[str(r["of_id"])] = r.get("barco_nome")
                    modelo_by_of[str(r["of_id"])] = r.get("modelo_id")
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
        return barco_by_of, modelo_by_of, fase_by_id

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
        barco_by_of, modelo_by_of, fase_by_id = await self._resolve_names(of_ids, fase_ids)
        items = shape_actuals_items(rows, barco_by_of, modelo_by_of, fase_by_id)
        return items, truncated
