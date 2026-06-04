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


async def _nelo_erp_raw_full_nightly_job() -> None:
    """Q.157.0 — full-copy nocturno das tabelas `factory_raw` de baixa velocidade.

    O job incremental de 5 min (`_nelo_erp_raw_incremental_job`) só toca as
    tabelas com PK+watermark (ordemfabrico/of_fp/movimento/of_checklist) e
    **salta** as de full-copy (produto/fases_producao/moldes/entidade/
    produto_fase/produto_componente/offp_eq/apontamento_trabalho). O comentário
    do q75 assumia um "full mirror nocturno" para essas — que nunca chegou a ser
    registado no scheduler, por isso ficavam DIAS stale (offp_eq/produto a 3 dias
    no audit de 2026-06-02). Este job fecha esse gap.

    Cada tabela é refrescada via `_mirror_table` (TRUNCATE+COPY atómico, DROP-free
    → seguro com as marts/VIEWs dependentes) e o `_synced_at` volta a `now()`.
    Corre 02:30 UTC (depois do mirror curado das 02:00, antes da calibração das
    06:40). No-op quando ``sqlserver_enabled=False``.
    """
    from src.shared.config import settings

    if not settings.sqlserver_enabled:
        logger.debug("nelo_erp_raw_full_nightly skipped — sqlserver_enabled=False")
        return

    from scripts.q75_setup_raw_mirror import RAW_TABLES
    from scripts.q75_setup_raw_mirror import setup as raw_setup

    # Só as tabelas que o incremental NÃO cobre (sem PK+watermark single-col).
    # Q.158.F — inclui também as tabelas com `keep_open_col` (ex. ORDEMFABRICO):
    # o incremental relê as abertas mas NÃO apanha fechos (OF_DATAACTUALIZACAO é
    # 96.8% null → o watermark nunca dispara para uma OF que fechou). Uma cópia
    # completa nocturna (TRUNCATE+COPY, ~20s/348k rows) corrige fechos + re-inclui
    # barcos abertos antigos. O incremental de 5 min mantém os novos frescos.
    full_only = [
        t.nelo_name for t in RAW_TABLES
        if not t.supports_incremental or t.keep_open_col
    ]
    started = datetime.utcnow()
    try:
        results = await raw_setup(incremental=False, only=full_only)
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        failed = [r["table"] for r in results if r.get("status") != "ok"]
        copied = sum(r.get("rows", 0) for r in results)
        logger.info(
            "nelo_erp_raw_full_nightly tables=%s rows=%s failed=%s elapsed_ms=%s",
            [r["table"] for r in results], copied, failed or "none", elapsed_ms,
        )
    except Exception as exc:
        logger.error("nelo_erp_raw_full_nightly failed: %s", exc, exc_info=True)


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


async def _nelo_erp_customers_job() -> None:
    """Q.125 — popula/refresca `core.customers` a partir de `factory_raw.entidade`
    (tipo Cliente, E_ENT_ID=2). O mirror `master` nunca espelhava clientes →
    core.customers estava a 0. Refresca entidade do NELO + upsert. 5/5 min.
    No-op quando ``sqlserver_enabled=False``.
    """
    from src.shared.config import settings

    if not settings.sqlserver_enabled:
        logger.debug("nelo_erp_customers skipped — sqlserver_enabled=False")
        return

    from scripts.setup_customers_from_entidade import setup as customers_setup

    started = datetime.utcnow()
    try:
        report = await customers_setup()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "nelo_erp_customers total=%s new=%s elapsed_ms=%s",
            report.get("customers_after"), report.get("customers_new"), elapsed_ms,
        )
    except Exception as exc:
        logger.error("nelo_erp_customers failed: %s", exc, exc_info=True)


async def _nelo_erp_production_orders_job() -> None:
    """Q.131.C — espelha `plan.production_orders` de `factory_raw.ordemfabrico`
    (WIP real: OF não-terminada em fase de produção). A lista de ordens lia 12
    ordens DEMO; este mirror torna-a 0 demo, keyed por `OF_P_ID` (casa com o
    routing real). Postgres-interno (lê o factory_raw já espelhado) → corre
    sempre; a própria função faz no-op se o WIP estiver vazio (dev/test).
    """
    from scripts.q131_setup_production_orders_mirror import setup as po_setup

    started = datetime.utcnow()
    try:
        report = await po_setup()
        elapsed_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        logger.info(
            "nelo_erp_production_orders wip=%s orders=%s->%s pruned=%s elapsed_ms=%s",
            report.get("wip_real"), report.get("orders_before"),
            report.get("orders_after"), report.get("pruned"), elapsed_ms,
        )
    except Exception as exc:
        logger.error("nelo_erp_production_orders failed: %s", exc, exc_info=True)

    # Q.143.B — com as ordens frescas, deriva os camiões reais (upcoming) das
    # production_orders. Idempotente e preserva drag-drop manual. Best-effort:
    # uma falha aqui não compromete o mirror acima.
    from src.shared.database import get_session_context
    from src.plan.services.transport_batch_service import TransportBatchService

    tenant_id = UUID("00000000-0000-0000-0000-000000000001")  # dev tenant
    tb_started = datetime.utcnow()
    try:
        async with get_session_context() as session:
            svc = TransportBatchService(session, tenant_id)
            summary = await svc.refresh_from_orders()
            await session.commit()
        tb_elapsed_ms = int((datetime.utcnow() - tb_started).total_seconds() * 1000)
        logger.info(
            "transport_batch_refresh created=%s touched=%s assigned=%s "
            "overflow=%s elapsed_ms=%s",
            summary["batches_created"], summary["batches_touched"],
            summary["orders_assigned"], summary["overflow"], tb_elapsed_ms,
        )
    except Exception as exc:
        logger.error("transport_batch_refresh failed: %s", exc, exc_info=True)


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
