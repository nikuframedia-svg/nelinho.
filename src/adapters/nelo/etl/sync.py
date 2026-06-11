"""Q.20.A — ERP→Postgres sync orchestration.

One place that knows how to: check ``settings.sqlserver_enabled``,
health-check the NELO adapter, and run the registered mirror functions.
Both the CLI (``scripts/sync_nelo_erp.py``) and the scheduler job
(``nelo_erp_sync``) call :func:`run_nelo_sync`.

Mirror modules (``master_data``, ``molds``, ``skills``, ``quality``,
``time_mining``) register themselves here via :func:`register_mirror`
when imported. :func:`_load_mirror_modules` imports them on demand so a
mirror added in a later sub-sprint is picked up automatically.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Awaitable, Callable, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from src.shared.time import utc_now

from .runner import EtlRunResult

#: ``since`` aceita uma única data (igual para todos os mirrors) ou um
#: dict {mirror: data} — watermark por mirror (Q.54.A, sync incremental).
SinceArg = Union[date, Dict[str, date], None]

logger = logging.getLogger(__name__)

# A mirror reads from the NELO adapter and writes operational rows. It
# owns its own EtlRunner; the orchestrator hands it a session, tenant and
# an optional ``since`` watermark, and gets back the run tally.
MirrorFn = Callable[..., Awaitable[EtlRunResult]]

_MIRRORS: Dict[str, MirrorFn] = {}


def register_mirror(name: str, fn: MirrorFn) -> None:
    """Register a mirror under ``name`` (the ``--only`` selector value)."""
    _MIRRORS[name] = fn


def registered_mirrors() -> List[str]:
    return sorted(_MIRRORS)


def _load_mirror_modules() -> None:
    """Import the mirror modules so their ``register_mirror`` calls fire.

    Each is optional during the incremental Q.20.B…F rollout — a missing
    module is logged at debug level, not an error.
    """
    for mod in (
        "master_data",       # Q.20.B
        "molds",             # Q.20.C
        "skills",            # Q.20.D
        "quality",           # Q.20.E — só `error_catalog` (vocabulário); já NÃO rework
        # Q.167.E — `checklist` é agora a FONTE ÚNICA de defeitos do ERP (RCA
        # canónico OF_CHECKLIST: causer≠detector em 78,5% das linhas). O `quality`
        # (OF_FP) deixou de escrever `rework_entry` e a migração q167e apagou as
        # linhas stale erp_of_fp → a tabela fica single-source POR CONSTRUÇÃO
        # (checklist + retrabalho humano via POST /rework). Os leitores não
        # precisam de filtrar por source — não há stale a dupla-contar.
        "checklist",         # Q.167.E
        "time_mining",       # Q.20.F
        "stock",             # Q.52.K
        "calendar",          # Q.53.B
        "inventory_ledger",  # Q.64.A — desbloqueia shortage-risks
        "material_master",   # Q.64.B — alimenta ShortageDetector
        "purchase_orders",   # Q.64.D — desbloqueia tab Entregas
        "bonus_payout",      # Q.173.AS — CoeficienteX (€) → profit.phase_bonus_payout
        # Q.173.B — phase_history e worker_assignment DESLIGADOS: consultavam
        # dbo.FasesOf / dbo.WorkerAssignment, tabelas que só existem no
        # fake-ERP de teste (o ERP real usa OF_FP/OFFP_EQ) → 9/9 corridas em
        # erro permanente e destinos sempre a 0 (auditoria 2026-06-11). Os
        # consumidores reais já leem factory_raw.of_fp/offp_eq (Q.150).
        # Repontar é decisão pendente do Luis — ver DELETION_LOG.md.
    ):
        try:
            __import__(f"src.adapters.nelo.etl.{mod}")
        except ImportError:  # pragma: no cover - defensive
            logger.debug("etl mirror module not present yet: %s", mod)


def _since_for(since: SinceArg, mirror: str) -> Optional[date]:
    """Resolve o watermark ``since`` para um mirror concreto.

    ``since`` pode ser ``None``, uma data única (aplicada a todos) ou um
    dict ``{mirror: data}`` — neste caso um mirror sem entrada recebe
    ``None`` e usa o seu look-back por defeito.
    """
    if since is None:
        return None
    if isinstance(since, dict):
        return since.get(mirror)
    return since


def _failed_result(name: str, exc: Exception) -> EtlRunResult:
    """Tally in-memory de um mirror falhado (loga e devolve)."""
    logger.error("nelo_sync mirror=%s failed: %s", name, exc, exc_info=True)
    failed = EtlRunResult(name)
    failed.status = "error"
    failed.error = f"{type(exc).__name__}: {exc}"
    return failed


async def _persist_error_run(
    session, tenant_id: UUID, failed: EtlRunResult, started_at,
) -> None:
    """Grava o ``core.etl_run`` de uma corrida falhada (Q.168 F4.E).

    O ``EtlRunner`` escreve o status='error' na MESMA sessão do mirror, mas
    o rollback que descarta as escritas parciais descarta também esse
    registo — sem esta re-gravação, as corridas falhadas eram invisíveis na
    BD (a página de sync e qualquer auditoria só viam sucessos).
    Best-effort: se a própria escrita de auditoria falhar (BD em baixo),
    loga e não aborta os mirrors seguintes.
    """
    from src.core.models.etl_run import EtlRun

    try:
        session.add(EtlRun(
            tenant_id=tenant_id,
            source=failed.source,
            status="error",
            started_at=started_at,
            finished_at=utc_now(),
            error=failed.error,
        ))
        await session.commit()
    except (SQLAlchemyError, OSError) as audit_exc:
        logger.warning(
            "nelo_sync mirror=%s — falha a persistir etl_run de erro: %s",
            failed.source, audit_exc,
        )


async def _alert_etl_failure(
    session, tenant_id: UUID, failed: EtlRunResult,
) -> None:
    """Q.173.C — alerta visível no copiloto quando um mirror ETL falha.

    A auditoria 2026-06-11 encontrou mirrors a falhar 100% das corridas
    durante semanas (phase_history/worker_assignment, 9/9 'error') com o
    erro visível apenas em ``core.etl_run`` — onde ninguém olha. Cria um
    ``CopilotAlert`` WARN por mirror, dedupado enquanto existir um ACTIVE
    para o mesmo mirror (o resolve manual reabre a vigilância). Best-effort:
    nunca aborta o sync.
    """
    from sqlalchemy import select

    from src.copilot.alerts.models import (
        CODE_ETL_SYNC_FAILED,
        STATUS_ACTIVE,
        CopilotAlert,
    )

    try:
        rows = await session.execute(
            select(CopilotAlert)
            .where(CopilotAlert.tenant_id == tenant_id)
            .where(CopilotAlert.code == CODE_ETL_SYNC_FAILED)
            .where(CopilotAlert.status == STATUS_ACTIVE)
        )
        # Dedup por mirror em Python (portável: evita JSONB @> nos fakes;
        # re-verifica status porque os fakes de teste ignoram o WHERE).
        for alert in rows.scalars().all():
            if (
                alert.status == STATUS_ACTIVE
                and alert.code == CODE_ETL_SYNC_FAILED
                and (alert.context or {}).get("source") == failed.source
            ):
                return
        session.add(CopilotAlert(  # noqa: audit_coverage  # alerta, nao estado gov (padrao AlertsEngine)
            tenant_id=tenant_id,
            severity="WARN",
            code=CODE_ETL_SYNC_FAILED,
            title=f"Sync ERP falhou: {failed.source}",
            message_pt=(
                f"O espelho ETL '{failed.source}' falhou a última corrida: "
                f"{(failed.error or 'erro desconhecido')[:300]} — os dados "
                "deste espelho podem estar desatualizados."
            ),
            context={"source": failed.source, "error": failed.error},
            entity_refs=[failed.source],
            status=STATUS_ACTIVE,
        ))
        await session.commit()
    except (SQLAlchemyError, OSError) as alert_exc:
        logger.warning(
            "nelo_sync mirror=%s — falha a criar alerta ETL_SYNC_FAILED: %s",
            failed.source, alert_exc,
        )


async def run_nelo_sync(
    *,
    only: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    tenant_id: Optional[UUID] = None,
    since: SinceArg = None,
) -> List[EtlRunResult]:
    """Run the ERP→Postgres sync.

    * ``only`` — subset of mirror names; ``None`` runs every registered one.
    * ``exclude`` — mirror names to drop (e.g. the heavy ``time_mining``
      is excluded from the nightly job).
    * ``tenant_id`` — defaults to the dev tenant.
    * ``since`` — watermark forwarded to incremental mirrors (quality,
      time_mining…). Uma única data aplica-se a todos; um dict
      ``{mirror: data}`` dá um watermark por mirror (sync incremental
      Q.54.A).

    Returns one :class:`EtlRunResult` per mirror that ran. A single
    failing mirror is recorded (``status='error'``) and the others still
    run — one bad table never aborts the whole sync.
    """
    from src.adapters.nelo.services import close_engine, health_check
    from src.shared.config import settings
    from src.shared.database import async_session_factory

    if tenant_id is None:
        tenant_id = UUID("00000000-0000-0000-0000-000000000001")  # dev tenant

    if not getattr(settings, "sqlserver_enabled", False):
        logger.warning(
            "nelo_sync skipped — settings.sqlserver_enabled is False. "
            "Set it (and sqlserver_url) to run the ERP sync."
        )
        return []

    _load_mirror_modules()
    selected = list(only) if only else registered_mirrors()
    if exclude:
        selected = [m for m in selected if m not in set(exclude)]
    unknown = [m for m in selected if m not in _MIRRORS]
    if unknown:
        raise ValueError(
            f"unknown mirror(s): {unknown}; known: {registered_mirrors()}"
        )

    results: List[EtlRunResult] = []
    try:
        snapshot = await health_check()
        logger.info(
            "nelo_sync — ERP reachable: open_orders=%d movements_30d=%d",
            snapshot.open_orders_count, snapshot.movements_last_30d,
        )

        if not selected:
            logger.info("nelo_sync — no mirrors registered/selected.")
            return []

        for name in selected:
            started_at = utc_now()
            try:
                async with async_session_factory() as session:
                    try:
                        result = await _MIRRORS[name](
                            session=session,
                            tenant_id=tenant_id,
                            since=_since_for(since, name),
                        )
                    except Exception as exc:
                        # Q.168 F4.E — antes, a exceção saía do `async with`
                        # sem commit: o rollback implícito do close descartava
                        # também o etl_run status='error' que o EtlRunner
                        # tinha escrito+flushed → corrida falhada SEM registo
                        # de auditoria na BD. Rollback explícito (descarta as
                        # escritas parciais do mirror) e re-grava o registo de
                        # erro numa transacção limpa, best-effort.
                        await session.rollback()
                        failed = _failed_result(name, exc)
                        results.append(failed)
                        await _persist_error_run(
                            session, tenant_id, failed, started_at,
                        )
                        await _alert_etl_failure(session, tenant_id, failed)
                        continue
                    await session.commit()
                results.append(result)
                logger.info("nelo_sync mirror=%s %r", name, result)
            except Exception as exc:
                # Falha fora do mirror (abrir a sessão / commit final) —
                # sem sessão utilizável só fica o registo in-memory.
                results.append(_failed_result(name, exc))
    finally:
        await close_engine()

    return results


async def last_sync_watermarks(
    session,
    tenant_id: UUID,
    mirrors: List[str],
) -> Dict[str, date]:
    """Watermark por mirror — a data do último ``core.etl_run`` com sucesso.

    Para o sync incremental (Q.54.A): cada mirror que suporta ``since``
    arranca a janela na data em que terminou da última vez, em vez de
    reler sempre o look-back inteiro. Lê o ``MAX(finished_at)`` por
    ``source`` entre as corridas ``status='ok'``.

    Um mirror que nunca correu (ou nunca correu com sucesso) não entra no
    dict — o mirror cai no seu look-back por defeito, que é o
    comportamento certo para um primeiro arranque.
    """
    from sqlalchemy import func, select

    from src.core.models.etl_run import EtlRun

    if not mirrors:
        return {}

    stmt = (
        select(EtlRun.source, func.max(EtlRun.finished_at))
        .where(EtlRun.tenant_id == tenant_id)
        .where(EtlRun.source.in_(list(mirrors)))
        .where(EtlRun.status == "ok")
        .where(EtlRun.finished_at.isnot(None))
        .group_by(EtlRun.source)
    )
    rows = (await session.execute(stmt)).all()
    out: Dict[str, date] = {}
    for source, finished_at in rows:
        if finished_at is not None:
            # `finished_at` é datetime tz-aware; o `since` dos mirrors é
            # uma data — converter aqui evita o bug tz-aware vs naive.
            out[str(source)] = finished_at.date()
    return out
