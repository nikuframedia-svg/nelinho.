"""
ProdPlan ONE — Copilot quality summary reader (Sprint Q.34.A.2)
================================================================

`build_quality_summary` lê os eventos de retrabalho directamente da
tabela relacional `quality.rework_entry` — populada pelo mirror ETL do
ERP (`src/adapters/nelo/etl/quality.py`).

Porquê: o `context_builder._build_quality_snapshot` lia a camada Factory
Data Product (`SemanticQueriesInMemory`), que arranca vazia. Há 3659
erros reais em Postgres que o copiloto nunca via.

Q.35.3.2 — duas correcções de honestidade:
  - As fases vinham como IDs (`phase_id_rework` = "40", "42"). O nome
    legível está em `context->>'phase_name'` (cobertura 3655/3659).
  - `cost_estimate_eur`/`hours_lost` só estão preenchidos em 4 de 3659
    registos. Somar tudo e chamar-lhe "custo total" (€610) enganava — o
    reader passa a expor a SOMA CONHECIDA + a contagem de registos que a
    suportam, para o copiloto poder dizer "€610 conhecido em 4 de 3659".

Determinístico, read-only, tenant-scoped.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ReworkEntry

logger = logging.getLogger(__name__)

_TOP_PHASES = 10
_TOP_CODES = 5


async def build_quality_summary(
    session: AsyncSession,
    tenant_id: UUID,
    window_start: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Resumo de qualidade a partir de `quality.rework_entry`.

    `window_start` (tz-aware) filtra por `detected_at` — a coluna é
    `DateTime(timezone=True)`, por isso NÃO se aplica o workaround
    naive `.replace(tzinfo=None)` usado noutros sítios.

    `has_data` é False quando não há erros para o tenant ou a query
    falha.
    """
    query_hash = hashlib.sha256(
        f"quality_summary_{tenant_id}_{window_start}".encode()
    ).hexdigest()[:16]
    try:
        rw = ReworkEntry
        conds = [rw.tenant_id == tenant_id]
        if window_start is not None:
            conds.append(rw.detected_at >= window_start)

        # Q.35.3.2 — uma só query para todos os counts/sums: total,
        # resolvidos, e a COBERTURA de custo/horas (contagem de registos
        # com valor não-nulo) ao lado da soma desses valores.
        agg = (await session.execute(
            select(
                func.count(),
                func.count(rw.resolved_at),
                func.count(rw.cost_estimate_eur),
                func.count(rw.hours_lost),
                func.sum(rw.cost_estimate_eur),
                func.sum(rw.hours_lost),
            ).where(*conds)
        )).all()
        row = agg[0] if agg else (0, 0, 0, 0, None, None)
        total = int(row[0] or 0)
        resolved = int(row[1] or 0)
        cost_known_count = int(row[2] or 0)
        hours_known_count = int(row[3] or 0)
        cost_sum = float(row[4]) if row[4] is not None else 0.0
        hours_sum = float(row[5]) if row[5] is not None else 0.0

        if total == 0:
            return {
                "has_data": False,
                "source": "db.rework_entry",
                "query_hash": query_hash,
            }

        # Erros por fase de retrabalho (top N). O nome legível vive no
        # JSONB `context->>'phase_name'`; cai para o ID quando falta.
        phase_label = func.coalesce(
            rw.context["phase_name"].astext, rw.phase_id_rework
        )
        phase_rows = (await session.execute(
            select(phase_label, func.count().label("n"))
            .where(*conds)
            .group_by(phase_label)
            .order_by(func.count().desc())
            .limit(_TOP_PHASES)
        )).all()
        errors_by_phase = [
            {"phase": p or "?", "errors": int(n)} for p, n in phase_rows
        ]

        # Erros por categoria de causa raiz.
        rc_rows = (await session.execute(
            select(rw.root_cause_category, func.count().label("n"))
            .where(*conds)
            .group_by(rw.root_cause_category)
            .order_by(func.count().desc())
        )).all()
        errors_by_root_cause = {
            (rc or "desconhecida"): int(n) for rc, n in rc_rows
        }

        # Códigos de erro mais frequentes (top N).
        code_rows = (await session.execute(
            select(rw.error_code, func.count().label("n"))
            .where(*conds)
            .group_by(rw.error_code)
            .order_by(func.count().desc())
            .limit(_TOP_CODES)
        )).all()
        top_error_codes = [
            {"code": c or "?", "errors": int(n)} for c, n in code_rows
        ]

        return {
            "has_data": True,
            "source": "db.rework_entry",
            "query_hash": query_hash,
            "total_errors": total,
            "unresolved_errors": max(0, total - resolved),
            "errors_by_phase": errors_by_phase,
            "errors_by_root_cause": errors_by_root_cause,
            "top_error_codes": top_error_codes,
            # Q.35.3.2 — soma CONHECIDA + cobertura. NÃO é o custo de todos
            # os 3659 erros: a maioria não tem custo registado no ERP.
            "cost_estimate_eur_known": cost_sum,
            "cost_known_count": cost_known_count,
            "hours_lost_known": hours_sum,
            "hours_known_count": hours_known_count,
        }
    except Exception as exc:
        logger.warning(f"build_quality_summary falhou: {exc}")
        return {
            "has_data": False,
            "source": "unavailable",
            "query_hash": query_hash,
        }
