"""Q.115.T — worker assignment mirror (ERP WorkerAssignment → hr.worker_phase_assignment).

Espelha as atribuicoes de operadores a fases de OF do SQL Server
(`dbo.WorkerAssignment`) para `hr.worker_phase_assignment`.

`assignment_type` e derivado pelo ETL:
  - `'actual'`  — quando `Iniciado_Em` esta preenchido (execucao real)
  - `'planned'` — quando so `Atribuido_Em` esta preenchido (planeamento)

Skip silencioso: quando `settings.sqlserver_enabled=False` devolve
`EtlRunResult(skipped=True)` — nunca e erro.

Cadencia:
  - Full sync diario 02:45 UTC
  - Incremental a cada 15 min via `_INCREMENTAL_MIRRORS`

TIMESTAMPTZ: datetimes naive do ERP tratados como UTC pelo `_as_utc`.
worker_id no ERP e int (entidade ERP), nao UUID — convertido para UUID
deterministico via uuid5 para matching com `hr.worker_phase_assignment`.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.adapters.nelo import services
from src.adapters.nelo.schemas import WorkerAssignmentRow
from src.hr.models.worker_phase_assignment import WorkerPhaseAssignment

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Look-back padrao no full sync diario.
_DEFAULT_LOOKBACK_DAYS = 365 * 3

_INCREMENTAL_LIMIT = 50_000
_FULL_LIMIT = 500_000

# Namespace UUID deterministico para converter int worker_id ERP → UUID.
# Permite re-runs idempotentes — mesmo worker_id ERP sempre da mesmo UUID.
_WORKER_NAMESPACE = uuid.UUID("b2c3d4e5-f6a7-8901-bcde-f12345678901")


def _worker_uuid(worker_id: int) -> UUID:
    """UUID deterministico para um worker_id ERP (int → uuid5)."""
    return uuid.uuid5(_WORKER_NAMESPACE, f"nelo:worker:{worker_id}")


def _as_utc(value: Any) -> Optional[datetime]:
    """Coerce um timestamp ERP para datetime tz-aware (UTC)."""
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
    """Normaliza valor para string UTF-8 (acentos PT-PT preservados)."""
    if value is None:
        return None
    return str(value).encode("utf-8", errors="replace").decode("utf-8")


def _derive_assignment_type(row: WorkerAssignmentRow) -> str:
    """Deriva `assignment_type` a partir dos campos ERP.

    Se `started_at` (Iniciado_Em) estiver preenchido → execucao real → 'actual'.
    Caso contrario (so atribuicao planeada) → 'planned'.
    """
    if row.started_at is not None:
        return "actual"
    return "planned"


def _map_row(row: WorkerAssignmentRow) -> Optional[Dict[str, Any]]:
    """Mapeia `WorkerAssignmentRow` para dict de colunas de `hr.worker_phase_assignment`.

    Devolve None se `worker_id` ou `assigned_at` forem None (linha invalida).
    """
    if row.worker_id is None or row.assigned_at is None:
        return None
    assigned_at = _as_utc(row.assigned_at)
    if assigned_at is None:
        return None
    return {
        "worker_id": _worker_uuid(row.worker_id),
        "of_id": _safe_str(row.of_id),
        "phase_id": _safe_str(row.phase_id),
        "assigned_at": assigned_at,
        "started_at": _as_utc(row.started_at),
        "ended_at": _as_utc(row.ended_at),
        "assignment_type": _derive_assignment_type(row),
    }


async def sync_worker_assignments(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror `dbo.WorkerAssignment` → `hr.worker_phase_assignment`.

    Q.115.T — ETL untapped. Skip silencioso se sqlserver_enabled=False.
    """
    from src.shared.config import settings

    if not getattr(settings, "sqlserver_enabled", False):
        logger.debug("worker_assignment skip — sqlserver_enabled=False")
        result = EtlRunResult("worker_assignment")
        result.status = "skipped"
        result.error = "sqlserver_disabled"
        return result

    limit = _INCREMENTAL_LIMIT if since is not None else _FULL_LIMIT

    async with EtlRunner(session, tenant_id, source="worker_assignment") as run:
        rows: List[WorkerAssignmentRow] = await services.list_worker_assignments(
            since=since,
            limit=limit,
        )
        run.count_read(len(rows))

        mapped = [m for m in (_map_row(r) for r in rows) if m is not None]
        run.count_skipped(len(rows) - len(mapped))

        await run.upsert(
            WorkerPhaseAssignment,
            mapped,
            key_fields=["worker_id", "of_id", "phase_id", "assigned_at"],
            update_fields=["started_at", "ended_at", "assignment_type"],
        )
        logger.info(
            "worker_assignment mirror — since=%s limit=%d lidas=%d mapeadas=%d",
            since, limit, len(rows), len(mapped),
        )
    return run.result


# Alias para compatibilidade com o orchestrador run_nelo_sync.
async def mirror_worker_assignment(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    return await sync_worker_assignments(
        session=session, tenant_id=tenant_id, since=since
    )


register_mirror("worker_assignment", mirror_worker_assignment)
