"""Q.66.A.4 — jobs de sync ERP->Postgres (NELO adapters).

Movidos de `src.shared.scheduler` sem alterações de comportamento.
A constante `_INCREMENTAL_MIRRORS` permanece module-level (tests Q.54.A
inspeccionam-na via `scheduler._INCREMENTAL_MIRRORS` através do shim).
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

logger = logging.getLogger(__name__)


async def _nelo_erp_sync_job() -> None:
    """Q.25.D — sync nocturno ERP->Postgres (mirrors leves).

    Corre os mirrors ETL Q.20 excepto `time_mining` (o minerador
    historico pesado tem cadencia propria — ``_nelo_erp_time_mining_job``).
    GLOBAL e idempotente. No-op quando ``sqlserver_enabled=False``, por
    isso ligar o flag em runtime nao exige reiniciar o scheduler.
    """
    from src.shared.config import settings

    if not settings.sqlserver_enabled:
        logger.debug("nelo_erp_sync skipped — sqlserver_enabled=False")
        return

    from src.adapters.nelo.etl.sync import run_nelo_sync

    started = datetime.utcnow()
    try:
        results = await run_nelo_sync(exclude=["time_mining"])
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        failed = [r.source for r in results if r.status != "ok"]
        logger.info(
            "nelo_erp_sync mirrors=%s failed=%s elapsed_ms=%s",
            [r.source for r in results], failed or "none", elapsed_ms,
        )
    except Exception as exc:
        logger.error("nelo_erp_sync failed: %s", exc, exc_info=True)


#: Mirrors operacionais leves que o sync incremental Q.54.A corre de
#: 5/5 min. Master/molds/skills mudam devagar (cadência nocturna chega);
#: time_mining é pesado (cadência semanal). Estes três espelham dados
#: que mudam ao longo do dia — stock, calendário, qualidade.
#: Q.115.T: phase_history e worker_assignment adicionados ao incremental
#: (15 min em vez de 5 — tabelas de alta cardinalidade).
_INCREMENTAL_MIRRORS = ["stock", "calendar", "quality"]
_INCREMENTAL_MIRRORS_PHASE = ["phase_history", "worker_assignment"]


async def _nelo_erp_incremental_sync_job() -> None:
    """Q.54.A — sync incremental ERP->Postgres de 5/5 min.

    Corre só os mirrors operacionais leves (``stock``, ``calendar``,
    ``quality``) — os que mudam ao longo do dia. Para cada um, lê de
    ``core.etl_run`` o watermark (último ``finished_at`` com sucesso) e
    passa-o como ``since``, por isso a janela relida é curta em vez do
    look-back inteiro.

    GLOBAL e idempotente. No-op quando ``sqlserver_enabled=False``. Um
    mirror que falha não aborta os outros (``run_nelo_sync`` já trata).
    Só usa mirrors registados — não inventa ``purchase_orders`` nem
    ``suppliers`` (não existem).
    """
    from src.shared.config import settings

    if not settings.sqlserver_enabled:
        logger.debug("nelo_erp_incremental_sync skipped — sqlserver_enabled=False")
        return

    from src.adapters.nelo.etl.sync import (
        last_sync_watermarks,
        registered_mirrors,
        run_nelo_sync,
        _load_mirror_modules,
    )
    from src.shared.database import get_session_context

    # Garante que os módulos-mirror estão importados antes de filtrar.
    _load_mirror_modules()
    known = set(registered_mirrors())
    selected = [m for m in _INCREMENTAL_MIRRORS if m in known]
    if not selected:
        logger.warning(
            "nelo_erp_incremental_sync — nenhum mirror operacional "
            "registado (esperados=%s)", _INCREMENTAL_MIRRORS,
        )
        return

    tenant_id = UUID("00000000-0000-0000-0000-000000000001")  # dev tenant
    started = datetime.utcnow()
    try:
        async with get_session_context() as session:
            watermarks = await last_sync_watermarks(
                session, tenant_id, selected,
            )
        results = await run_nelo_sync(
            only=selected, tenant_id=tenant_id, since=watermarks,
        )
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        failed = [r.source for r in results if r.status != "ok"]
        logger.info(
            "nelo_erp_incremental_sync mirrors=%s watermarks=%s "
            "failed=%s elapsed_ms=%s",
            [r.source for r in results],
            {k: v.isoformat() for k, v in watermarks.items()},
            failed or "none", elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "nelo_erp_incremental_sync failed: %s", exc, exc_info=True,
        )


async def _nelo_erp_phase_history_incremental_job() -> None:
    """Q.115.T — sync incremental phase_history + worker_assignment (15 min).

    Alta cardinalidade — corre separado dos outros incrementais para nao
    bloquear stock/calendar/quality. Watermark por mirror via core.etl_run.
    No-op quando ``sqlserver_enabled=False``.
    """
    from src.shared.config import settings

    if not settings.sqlserver_enabled:
        logger.debug(
            "nelo_erp_phase_history_incremental skipped — sqlserver_enabled=False"
        )
        return

    from src.adapters.nelo.etl.sync import (
        _load_mirror_modules,
        last_sync_watermarks,
        registered_mirrors,
        run_nelo_sync,
    )
    from src.shared.database import get_session_context

    _load_mirror_modules()
    known = set(registered_mirrors())
    selected = [m for m in _INCREMENTAL_MIRRORS_PHASE if m in known]
    if not selected:
        logger.warning(
            "nelo_erp_phase_history_incremental — nenhum mirror registado "
            "(esperados=%s)", _INCREMENTAL_MIRRORS_PHASE,
        )
        return

    tenant_id = UUID("00000000-0000-0000-0000-000000000001")  # dev tenant
    started = datetime.utcnow()
    try:
        async with get_session_context() as session:
            watermarks = await last_sync_watermarks(session, tenant_id, selected)
        results = await run_nelo_sync(
            only=selected, tenant_id=tenant_id, since=watermarks,
        )
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        failed = [r.source for r in results if r.status not in ("ok", "skipped")]
        logger.info(
            "nelo_erp_phase_history_incremental mirrors=%s watermarks=%s "
            "failed=%s elapsed_ms=%s",
            [r.source for r in results],
            {k: v.isoformat() for k, v in watermarks.items()},
            failed or "none", elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "nelo_erp_phase_history_incremental failed: %s", exc, exc_info=True,
        )


async def _nelo_erp_raw_incremental_job() -> None:
    """Q.125 — refresh incremental de 5/5 min das tabelas `factory_raw` de alta
    velocidade (ordemfabrico/of_fp/movimento/of_checklist/transporte) por upsert
    da janela recente. Alimenta o dashboard/copiloto — as marts são VIEWs live
    sobre `factory_raw`, logo ficam frescas sem re-correr `setup_marts_*`.

    DROP-free (upsert por PK) → sem janela de leitura vazia para as views.
    No-op quando ``sqlserver_enabled=False``.
    """
    from src.shared.config import settings

    if not settings.sqlserver_enabled:
        logger.debug("nelo_erp_raw_incremental skipped — sqlserver_enabled=False")
        return

    from scripts.q75_setup_raw_mirror import setup as raw_setup

    started = datetime.utcnow()
    try:
        results = await raw_setup(incremental=True)
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        failed = [r["table"] for r in results if r.get("status") != "ok"]
        new = sum(r.get("rows_inserted", 0) for r in results)
        logger.info(
            "nelo_erp_raw_incremental tables=%s new=%s failed=%s elapsed_ms=%s",
            [r["table"] for r in results], new, failed or "none", elapsed_ms,
        )
    except Exception as exc:
        logger.error("nelo_erp_raw_incremental failed: %s", exc, exc_info=True)


async def _nelo_erp_comercial_job() -> None:
    """Q.125 — refresh de 5/5 min do espelho Comercial (PHC: faturação,
    entidades). Full refresh ATÓMICO (TRUNCATE+COPY, DROP-free) — seguro com as
    marts de faturação dependentes. Tabelas ≤100k → ~1-2 s. No-op se
    ``sqlserver_enabled=False``.
    """
    from src.shared.config import settings

    if not settings.sqlserver_enabled:
        logger.debug("nelo_erp_comercial skipped — sqlserver_enabled=False")
        return

    from scripts.q102_setup_comercial_mirror import setup as comercial_setup

    started = datetime.utcnow()
    try:
        report = await comercial_setup()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        mirror = report.get("mirror", [])
        failed = [r["table"] for r in mirror if r.get("status") != "ok"]
        logger.info(
            "nelo_erp_comercial tables=%s failed=%s elapsed_ms=%s",
            [r["table"] for r in mirror], failed or "none", elapsed_ms,
        )
    except Exception as exc:
        logger.error("nelo_erp_comercial failed: %s", exc, exc_info=True)


async def _nelo_erp_logistica_job() -> None:
    """Q.125 — refresh de 5/5 min do espelho Logística (transportes, expedições).
    Full refresh ATÓMICO (TRUNCATE+COPY, DROP-free). No-op se
    ``sqlserver_enabled=False``.
    """
    from src.shared.config import settings

    if not settings.sqlserver_enabled:
        logger.debug("nelo_erp_logistica skipped — sqlserver_enabled=False")
        return

    from scripts.q104_setup_logistica_mirror import setup as logistica_setup

    started = datetime.utcnow()
    try:
        report = await logistica_setup()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        mirror = report.get("mirror", report) if isinstance(report, dict) else report
        failed = [r["table"] for r in mirror if r.get("status") != "ok"]
        logger.info(
            "nelo_erp_logistica tables=%s failed=%s elapsed_ms=%s",
            [r["table"] for r in mirror], failed or "none", elapsed_ms,
        )
    except Exception as exc:
        logger.error("nelo_erp_logistica failed: %s", exc, exc_info=True)


async def _nelo_erp_time_mining_job() -> None:
    """Q.25.D — mineracao historica de tempos (o mirror pesado, semanal).

    `time_mining` percorre ~3 anos de `OF_FP` (~680k linhas) para refrescar
    as duracoes P50/P90 de `plan.routing_template_phase`. Cadencia semanal
    — as duracoes mudam devagar. No-op quando ``sqlserver_enabled=False``.
    """
    from src.shared.config import settings

    if not settings.sqlserver_enabled:
        logger.debug("nelo_erp_time_mining skipped — sqlserver_enabled=False")
        return

    from src.adapters.nelo.etl.sync import run_nelo_sync

    started = datetime.utcnow()
    try:
        results = await run_nelo_sync(only=["time_mining"])
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        for r in results:
            logger.info(
                "nelo_erp_time_mining status=%s read=%s upd=%s skip=%s elapsed_ms=%s",
                r.status, r.rows_read, r.rows_updated, r.rows_skipped, elapsed_ms,
            )
    except Exception as exc:
        logger.error("nelo_erp_time_mining failed: %s", exc, exc_info=True)
