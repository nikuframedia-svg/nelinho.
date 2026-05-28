"""Q.115.H — RunbookService: aprendizagem de runbooks a partir do histórico.

Função principal: `learn_runbook_from_history(tenant_id, error_code)`.
Lê os últimos 180d de `quality.rework_entry`, agrupa por `root_cause_category`,
constrói `steps_md` a partir das acções subsequentes observadas e faz UPSERT
em `quality.runbook` com `source="learned"` + `approved_by=NULL`.

Runbooks ficam pendentes de aprovação humana (invariante Q.17).
Confidence threshold ≥ 0.8 para o dispatcher poder usar (Q.115.H spec).
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.quality.models.rework import ReworkEntry
from src.quality.models.runbook import ErrorTypeRunbookLink, Runbook

_log = logging.getLogger(__name__)

# Mínimo de amostras para criar um runbook — proteção contra ruído.
MIN_SAMPLES = 10
# Janela de histório em dias.
HISTORY_DAYS = 180


async def learn_runbook_from_history(
    session: AsyncSession,
    tenant_id: UUID,
    error_code: str,
) -> Optional[Runbook]:
    """Aprende um runbook a partir do histórico de retrabalho.

    Devolve o Runbook persistido (novo ou actualizado) ou None quando
    há amostras insuficientes (silent skip — log info).

    Os passos são derivados da `rework_op_id` mais frequente por posição
    de entrada (proxy para "acção típica"). Confidence = consenso dos
    clusters / total de entradas com `root_cause_category` definido.

    Audit: cada UPSERT escreve `audit_trace_id` com o timestamp UTC.
    A linha é escrita na mesma transacção que o chamador controla (sem
    commit interno — responsabilidade do chamador).
    """
    since = datetime.now(timezone.utc) - timedelta(days=HISTORY_DAYS)

    # 1. Busca entradas do período
    rows_result = await session.execute(
        select(ReworkEntry)
        .where(
            and_(
                ReworkEntry.tenant_id == tenant_id,
                ReworkEntry.error_code == error_code,
                ReworkEntry.detected_at >= since,
            )
        )
        .order_by(ReworkEntry.detected_at)
    )
    entries: list[ReworkEntry] = list(rows_result.scalars().all())

    if len(entries) < MIN_SAMPLES:
        _log.info(
            "learn_runbook: amostras insuficientes tenant=%s error_code=%s "
            "count=%d min=%d — skip",
            tenant_id, error_code, len(entries), MIN_SAMPLES,
        )
        return None

    # 2. Agrupa por root_cause_category
    categorized = [e for e in entries if e.root_cause_category]
    if not categorized:
        _log.info(
            "learn_runbook: nenhuma entrada com root_cause_category "
            "tenant=%s error_code=%s — skip",
            tenant_id, error_code,
        )
        return None

    cause_counter: Counter[str] = Counter(
        e.root_cause_category for e in categorized  # type: ignore[arg-type]
    )
    dominant_cause, dominant_count = cause_counter.most_common(1)[0]

    # 3. Acções típicas: rework_op_id das entradas com a causa dominante
    cluster_entries = [
        e for e in categorized if e.root_cause_category == dominant_cause
    ]
    ops_counter: Counter[str] = Counter(
        e.rework_op_id for e in cluster_entries if e.rework_op_id
    )

    # Constrói passos em PT-PT, por frequência decrescente
    steps: list[str] = []
    for op_id, count in ops_counter.most_common(5):
        pct = int(100 * count / len(cluster_entries))
        steps.append(f"Executar operação `{op_id}` (observado em {pct}% dos casos).")

    if not steps:
        # Fallback: sem op_id, usa fases de retrabalho
        phase_counter: Counter[str] = Counter(
            e.phase_id_rework for e in cluster_entries if e.phase_id_rework
        )
        for phase, count in phase_counter.most_common(5):
            pct = int(100 * count / len(cluster_entries))
            steps.append(f"Retrabalhar na fase `{phase}` (observado em {pct}% dos casos).")

    if not steps:
        _log.info(
            "learn_runbook: sem acções observáveis tenant=%s error_code=%s — skip",
            tenant_id, error_code,
        )
        return None

    steps_numbered = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))
    steps_md = (
        f"## Procedimento para erro {error_code}\n\n"
        f"**Causa típica:** {dominant_cause}\n\n"
        f"### Passos:\n\n"
        f"{steps_numbered}\n\n"
        f"---\n"
        f"*Gerado automaticamente a partir de {dominant_count} ocorrências "
        f"nos últimos {HISTORY_DAYS} dias. Requer aprovação humana antes de activar.*"
    )

    # 4. Confidence: fracção de entradas categorized que pertencem ao cluster dominante
    confidence = dominant_count / len(categorized)

    # 5. UPSERT: verifica se já existe runbook learned para este error_code + tenant
    existing_result = await session.execute(
        select(Runbook).where(
            and_(
                Runbook.tenant_id == tenant_id,
                Runbook.error_code == error_code,
                Runbook.source == "learned",
            )
        )
    )
    runbook = existing_result.scalar_one_or_none()

    audit_trace = f"learn_runbook:{datetime.now(timezone.utc).isoformat()}"

    if runbook is None:
        runbook = Runbook(
            id=uuid4(),
            tenant_id=tenant_id,
            error_code=error_code,
            steps_md=steps_md,
            source="learned",
            confidence=confidence,
            approved_by=None,
            approved_at=None,
            audit_trace_id=audit_trace,
        )
        session.add(runbook)
    else:
        # Actualiza apenas campos derivados — nunca toca approved_by/approved_at
        runbook.steps_md = steps_md
        runbook.confidence = confidence
        runbook.audit_trace_id = audit_trace

    # 6. Liga via error_type_runbook_link (UPSERT: elimina link antigo e recria)
    await session.execute(
        delete(ErrorTypeRunbookLink).where(
            and_(
                ErrorTypeRunbookLink.tenant_id == tenant_id,
                ErrorTypeRunbookLink.error_code == error_code,
                ErrorTypeRunbookLink.runbook_id == runbook.id,
            )
        )
    )
    link = ErrorTypeRunbookLink(
        tenant_id=tenant_id,
        error_code=error_code,
        runbook_id=runbook.id,
        priority=1,
    )
    session.add(link)

    _log.info(
        "learn_runbook: persistido tenant=%s error_code=%s confidence=%.3f "
        "steps=%d dominant_cause=%r",
        tenant_id, error_code, confidence, len(steps), dominant_cause,
    )
    return runbook


async def approve_runbook(
    session: AsyncSession,
    tenant_id: UUID,
    runbook_id: UUID,
    approved_by: str,
    notes: Optional[str] = None,
) -> Runbook:
    """Aprova um runbook e escreve audit_trace_id na mesma transacção.

    Raises ValueError se o runbook não existir ou pertencer a outro tenant.
    """
    result = await session.execute(
        select(Runbook).where(
            and_(Runbook.id == runbook_id, Runbook.tenant_id == tenant_id)
        )
    )
    runbook = result.scalar_one_or_none()
    if runbook is None:
        raise ValueError(f"Runbook {runbook_id} não encontrado para tenant {tenant_id}")

    runbook.approved_by = approved_by
    runbook.approved_at = datetime.now(timezone.utc)
    runbook.audit_trace_id = (
        f"approve_runbook:{approved_by}:{datetime.now(timezone.utc).isoformat()}"
        + (f":{notes}" if notes else "")
    )
    _log.info(
        "approve_runbook: runbook=%s tenant=%s approved_by=%s",
        runbook_id, tenant_id, approved_by,
    )
    return runbook
