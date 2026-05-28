"""Q.115.T — phase history mirror (ERP FasesOf → plan.fases_of_history).

Espelha o historico LIMPO de execucao de fases por OF do SQL Server
(`dbo.FasesOf`, ~2.6M linhas) para `plan.fases_of_history`.

`duration_min` e calculado em Python: `(fase_fim - fase_inicio).total_seconds() / 60`.
Quando `fase_fim` e None (fase em curso), `duration_min` fica None.

Watermark incremental: lê o max `fase_inicio` do ultimo `core.etl_run`
bem-sucedido para `phase_history` e usa-o como `since` no fetch.

Skip silencioso: quando `settings.sqlserver_enabled=False` devolve
`EtlRunResult(skipped=True)` — nunca e erro.

Cadencia:
  - Full sync diario 02:30 UTC (3 anos de historico, `since=None`)
  - Incremental a cada 15 min via `_INCREMENTAL_MIRRORS`

TIMESTAMPTZ: datetimes naive do ERP sao tratados como UTC pelo `_as_utc`.
Encoding UTF-8: colunas string passam por `_safe_str` que normaliza.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.adapters.nelo import services
from src.adapters.nelo.schemas import FasesOfHistoryRow
from src.plan.models.fases_of_history import FasesOfHistory

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Look-back padrao no full sync diario: 3 anos de historico de fases.
_DEFAULT_LOOKBACK_DAYS = 365 * 3

# Cap de linhas por execucao incremental (15 min). Full sync usa limit maior.
_INCREMENTAL_LIMIT = 50_000
_FULL_LIMIT = 500_000


def _as_utc(value: Any) -> Optional[datetime]:
    """Coerce um timestamp ERP para datetime tz-aware (UTC).

    O SQL Server devolve datetimes naive — assumimos UTC (NELO Vila do Conde,
    servidor ERP configurado em UTC). `None` e passado directamente.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day, 0, 0, 0)
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _safe_str(value: Any) -> Optional[str]:
    """Normaliza um valor de coluna para string UTF-8 segura.

    NELO Vila do Conde pode ter problemas de charset (CP1252 vs UTF-8).
    Encoding/decoding explicito garante que acentos PT-PT sao preservados.
    """
    if value is None:
        return None
    s = str(value)
    # round-trip encode/decode para expurgar bytes invalidos
    return s.encode("utf-8", errors="replace").decode("utf-8")


def _calc_duration_min(
    fase_inicio: Optional[datetime],
    fase_fim: Optional[datetime],
) -> Optional[Decimal]:
    """Duracao em minutos entre inicio e fim da fase.

    Calcula em Python (nao SQL GENERATED) porque `fase_fim` e nullable.
    Devolve None se qualquer dos timestamps for None ou se a diferenca
    for negativa (dados sujos do ERP).
    """
    if fase_inicio is None or fase_fim is None:
        return None
    delta = fase_fim - fase_inicio
    minutes = delta.total_seconds() / 60.0
    if minutes < 0:
        return None
    return Decimal(str(round(minutes, 2)))


def _map_row(row: FasesOfHistoryRow, source_run_id: Optional[str]) -> Dict[str, Any]:
    """Mapeia `FasesOfHistoryRow` para dict de colunas de `plan.fases_of_history`."""
    fase_inicio = _as_utc(row.fase_inicio)
    fase_fim = _as_utc(row.fase_fim)
    return {
        "of_id": _safe_str(row.of_id),
        "phase_id": _safe_str(row.phase_id),
        "fase_inicio": fase_inicio,
        "fase_fim": fase_fim,
        "duration_min": _calc_duration_min(fase_inicio, fase_fim),
        "worker_id": None,   # worker_id no ERP e int (entidade), nao UUID
        "mold_id": _safe_str(row.mold_id),
        "source_run_id": source_run_id,
    }


async def sync_phase_history(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror `dbo.FasesOf` → `plan.fases_of_history`.

    Q.115.T — ETL untapped. Skip silencioso se sqlserver_enabled=False.
    """
    from src.shared.config import settings

    if not getattr(settings, "sqlserver_enabled", False):
        logger.debug("phase_history skip — sqlserver_enabled=False")
        result = EtlRunResult("phase_history")
        result.status = "skipped"
        result.error = "sqlserver_disabled"
        return result

    limit = _INCREMENTAL_LIMIT if since is not None else _FULL_LIMIT

    async with EtlRunner(session, tenant_id, source="phase_history") as run:
        rows: List[FasesOfHistoryRow] = await services.list_phase_history(
            since=since,
            limit=limit,
        )
        run.count_read(len(rows))

        # source_run_id: permite rastrear de que corrida ETL veio cada linha
        source_run_id = (
            f"phase_history:{since.isoformat() if since else 'full'}"
        )
        mapped = [_map_row(r, source_run_id) for r in rows]

        await run.upsert(
            FasesOfHistory,
            mapped,
            key_fields=["of_id", "phase_id", "fase_inicio"],
            update_fields=["fase_fim", "duration_min", "mold_id", "source_run_id"],
        )
        logger.info(
            "phase_history mirror — since=%s limit=%d lidas=%d",
            since, limit, len(rows),
        )
    return run.result


# Alias para compatibilidade com o contrato do orchestrador run_nelo_sync
# (espera funcoes com assinatura session/tenant_id/since).
async def mirror_phase_history(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    return await sync_phase_history(session=session, tenant_id=tenant_id, since=since)


register_mirror("phase_history", mirror_phase_history)
