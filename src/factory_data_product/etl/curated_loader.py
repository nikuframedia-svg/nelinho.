"""Q.36.C — `curated_loader`: relacional ERP → `factory_curated.*`.

Transforma as fontes relacionais do ERP MAR-KAYAKS nas 3 tabelas
curadas que os detectores causais consomem:

* ``OF_FP``        (``OperationRow``)     → ``CuratedOrderPhase``
* ``OFFP_EQ``      (``OperationCrewRow``) → ``CuratedAllocation``
* ``OF_CHECKLIST`` (``ChecklistRow``)     → ``CuratedQualityEvent``

Contrato de chaves (verificado em `repository.py`):

* ``fase_of_id`` é idêntico entre ``order_phase`` e ``allocation`` —
  ambos usam o ``OFFP_ID`` da operação;
* ``(of_id, fase_id)`` é idêntico entre ``order_phase`` e
  ``quality_event``;
* nenhuma business key sai como ``""`` — linhas sem chave são deixadas
  de fora (o detector prefere menos dados a dados corruptos);
* ``erro_tipo`` do ``quality_event`` contém uma das keywords de
  ``erro_tree._MOLD_TYPED_ERROR_KEYWORDS`` quando o defeito é de molde —
  é assim que o ``MoldDetector`` conta os erros "mold-typed".

As funções ``operations_to_order_phases`` / ``crew_to_allocations`` /
``checklist_to_quality_events`` são **puras** (sem DB, sem ERP) — só
recebem schemas Pydantic do adaptador e devolvem dicts de colunas ORM.
``load_curated`` orquestra: cria 1 ``IngestionRun`` (audit, axioma 7) e
faz full-refresh das 3 tabelas numa transacção.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete

from src.adapters.nelo.schemas import ChecklistRow, OperationCrewRow, OperationRow
from src.explain.diagnostics.erro_tree import _MOLD_TYPED_ERROR_KEYWORDS
from src.factory_data_product.ingest.gravidade import map_gravidade_to_severity
from src.factory_data_product.models.curated import (
    CuratedAllocation,
    CuratedOrderPhase,
    CuratedQualityEvent,
)
from src.factory_data_product.models.meta import (
    IngestionRun,
    IngestionStatus,
    QualityGateStatus,
    SourceType,
)

logger = logging.getLogger(__name__)

# Keyword canónica injectada no ``erro_tipo`` quando um defeito é de
# molde mas o texto livre do ERP não contém nenhuma das keywords que o
# ``MoldDetector`` procura. "deformação" está em
# ``_MOLD_TYPED_ERROR_KEYWORDS`` — usá-la garante que o detector conta a
# linha como mold-typed.
_MOLD_TYPED_TAG = "deformação"

# Keywords (texto livre do ERP) que marcam um defeito como de molde
# quando a flag ``OFCH_MOLDE_REPARAR`` não está activa.
_MOLD_TEXT_KEYWORDS = (
    "molde", "interior enrugado", "molde baço", "molde baco",
    "deformação", "deformacao", "bolha", "desmold",
)


# ─── helpers ────────────────────────────────────────────────────────────


def _as_date(value: Any) -> Optional[date]:
    """Coage um timestamp do ERP para ``date`` (as colunas curadas são
    ``Date``, não ``DateTime``)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _elapsed_hours(start: Any, end: Any) -> Optional[Decimal]:
    """Horas decorridas entre o início e o fim de uma operação.

    O tempo real vem sempre do histórico (``OFFP_DATAINICIO`` →
    ``OFFP_DATAFIM``) — nunca de coeficientes standard. ``None`` quando
    uma das datas falta ou o intervalo é negativo (dado sujo)."""
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return None
    delta = end - start
    if delta.total_seconds() < 0:
        return None
    return Decimal(str(round(delta.total_seconds() / 3600.0, 4)))


def _is_mold_defect(chk: ChecklistRow) -> bool:
    """Um defeito é de molde se a flag ``OFCH_MOLDE_REPARAR`` estiver
    activa ou se o texto livre casar uma keyword de molde."""
    if chk.mold_repair:
        return True
    text = f"{chk.description or ''} {chk.description_en or ''}".lower()
    return any(kw in text for kw in _MOLD_TEXT_KEYWORDS)


def _erro_tipo(chk: ChecklistRow) -> str:
    """``erro_tipo`` para o ``CuratedQualityEvent``.

    Quando o defeito é de molde, garante que o resultado contém uma
    keyword de ``_MOLD_TYPED_ERROR_KEYWORDS`` — o ``MoldDetector``
    conta os erros mold-typed por keyword. Se o texto livre já tem uma
    keyword (ex. "interior enrugado"), usa-se tal e qual; senão prefixa-se
    a tag canónica para o detector reconhecer.
    """
    descr = (chk.description or "").strip()
    if not _is_mold_defect(chk):
        return descr[:100] if descr else "defeito-nao-especificado"
    low = descr.lower()
    if any(kw in low for kw in _MOLD_TYPED_ERROR_KEYWORDS):
        return descr[:100]
    if not descr:
        return _MOLD_TYPED_TAG
    return f"{_MOLD_TYPED_TAG}: {descr}"[:100]


# ─── transformações puras ───────────────────────────────────────────────


def operations_to_order_phases(
    operations: List[OperationRow],
    ingestion_id: UUID,
) -> List[Dict[str, Any]]:
    """``OF_FP`` (``OperationRow``) → linhas de ``CuratedOrderPhase``.

    UMA linha por ``(of_id, fase_id)``. Uma OF pode passar pela mesma
    fase mais que uma vez (retrabalho) → várias `OF_FP` para o mesmo par;
    o constraint unique ``(ingestion_id, of_id, fase_id)`` obriga a
    colapsá-las. As operações do par são agregadas: `horas_reais` somadas
    (tempo total, incluindo reworks), `data_inicio` = mais cedo,
    `data_fim` = mais tarde (None se alguma operação ainda está aberta),
    e o molde/`fase_nome` vêm da operação mais recente.

    `fase_of_id` = ``"of_id::fase_id"`` — chave estável e determinística,
    a MESMA que :func:`crew_to_allocations` reconstrói (não o `OFFP_ID`,
    que é por-operação e não sobreviveria ao colapso).

    Linhas sem ``of_id`` ou ``fase_id`` são deixadas de fora.
    """
    grouped: Dict[tuple, Dict[str, Any]] = {}
    for op in operations:
        of_id = str(op.work_order_id) if op.work_order_id else ""
        fase_id = str(op.phase_id) if op.phase_id else ""
        if not of_id or not fase_id:
            continue
        key = (of_id, fase_id)
        hrs = _elapsed_hours(op.start_at, op.end_at)
        di = _as_date(op.start_at)
        df = _as_date(op.end_at)
        is_open = op.end_at is None

        g = grouped.get(key)
        if g is None:
            grouped[key] = {
                "ingestion_id": ingestion_id,
                "of_id": of_id,
                "fase_id": fase_id,
                "fase_of_id": f"{of_id}::{fase_id}",
                "fase_nome": op.phase_name,
                "horas_reais": hrs,
                "horas_standard": (
                    Decimal(str(op.standard_time_hours))
                    if op.standard_time_hours is not None else None
                ),
                "data_inicio": di,
                "data_fim": df,
                "molde_id": (
                    str(op.operation_mold_id)
                    if op.operation_mold_id is not None else None
                ),
                "_any_open": is_open,
                "_last_end": op.end_at,
            }
            continue

        # Operação adicional do mesmo (of, fase) — agregar.
        if hrs is not None:
            g["horas_reais"] = (g["horas_reais"] or Decimal("0")) + hrs
        if di and (g["data_inicio"] is None or di < g["data_inicio"]):
            g["data_inicio"] = di
        if df and (g["data_fim"] is None or df > g["data_fim"]):
            g["data_fim"] = df
        g["_any_open"] = g["_any_open"] or is_open
        # Representante = operação mais recente (molde + nome da fase).
        if op.end_at is not None and (
            g["_last_end"] is None or op.end_at > g["_last_end"]
        ):
            g["_last_end"] = op.end_at
            g["fase_nome"] = op.phase_name
            if op.operation_mold_id is not None:
                g["molde_id"] = str(op.operation_mold_id)

    rows: List[Dict[str, Any]] = []
    for g in grouped.values():
        any_open = g.pop("_any_open")
        g.pop("_last_end", None)
        # Fase aberta → data_fim NULL (o `current_wip` do repository
        # conta data_inicio NOT NULL + data_fim NULL).
        if any_open:
            g["data_fim"] = None
            g["estado"] = "aberta"
        else:
            g["estado"] = "concluida"
        rows.append(g)
    return rows


def crew_to_allocations(
    crew: List[OperationCrewRow],
    ingestion_id: UUID,
) -> List[Dict[str, Any]]:
    """``OFFP_EQ`` (``OperationCrewRow``) → linhas de ``CuratedAllocation``.

    ``fase_of_id`` = ``"of_id::fase_id"`` — a MESMA chave que
    :func:`operations_to_order_phases` constrói, para a allocation ligar
    à ``CuratedOrderPhase`` certa no ``DiagnosticsRepository``. NÃO o
    ``OFFP_ID`` por-operação, que não sobreviveria ao colapso de reworks.

    UMA linha por ``(fase_of_id, funcionario_id)`` — uma OF pode passar
    pela mesma fase várias vezes (retrabalho), cada passagem com a sua
    `OFFP_EQ`; colapsam-se para não contar o mesmo operador em duplicado.
    ``is_chefe`` fica ``True`` se o operador foi chefe em qualquer das
    passagens.

    Linhas sem ordem, fase ou operador são deixadas de fora.
    """
    seen: Dict[tuple, Dict[str, Any]] = {}
    for row in crew:
        of_id = str(row.work_order_id) if row.work_order_id else ""
        fase_id = str(row.phase_id) if row.phase_id else ""
        if not of_id or not fase_id or not row.operator_id:
            continue
        fase_of_id = f"{of_id}::{fase_id}"
        funcionario_id = str(row.operator_id)
        key = (fase_of_id, funcionario_id)
        existing = seen.get(key)
        if existing is None:
            seen[key] = {
                "ingestion_id": ingestion_id,
                "fase_of_id": fase_of_id,
                "funcionario_id": funcionario_id,
                "is_chefe": bool(row.is_chefe),
            }
        elif row.is_chefe:
            existing["is_chefe"] = True
    return list(seen.values())


def checklist_to_quality_events(
    incidents: List[ChecklistRow],
    ingestion_id: UUID,
) -> List[Dict[str, Any]]:
    """``OF_CHECKLIST`` (``ChecklistRow``) → linhas de ``CuratedQualityEvent``.

    ``(of_id, fase_id)`` é a chave que liga ao ``CuratedOrderPhase``.
    Linhas sem ``of_id`` são deixadas de fora (business key NOT NULL).
    ``erro_tipo`` carrega a keyword mold-typed quando o defeito é de
    molde — o ``MoldDetector`` depende disso.
    """
    rows: List[Dict[str, Any]] = []
    for chk in incidents:
        of_id = str(chk.work_order_id) if chk.work_order_id else ""
        if not of_id:
            continue
        data_evento = (
            _as_date(chk.detected_at)
            or _as_date(chk.verified_at)
            or _as_date(chk.updated_at)
        )
        rows.append({
            "ingestion_id": ingestion_id,
            "of_id": of_id,
            "fase_id": str(chk.phase_id) if chk.phase_id else None,
            "erro_tipo": _erro_tipo(chk),
            "erro_descricao": chk.description,
            "quantidade": 1,
            "data_evento": data_evento,
            "molde_id": (
                str(chk.operation_mold_id)
                if chk.operation_mold_id is not None else None
            ),
        })
    return rows


# ─── orquestração ───────────────────────────────────────────────────────


async def load_curated(
    session,
    tenant_id: UUID,
    *,
    since: Optional[date] = None,
    lookback_days: int = 365,
) -> Dict[str, int]:
    """Full-refresh de ``factory_curated.{order_phase,quality_event,allocation}``.

    Lê as 3 fontes do ERP via o adaptador, transforma com as funções
    puras e reescreve as 3 tabelas curadas numa transacção. Cria 1
    ``IngestionRun`` (audit, axioma 7) que carimba todas as linhas com o
    mesmo ``ingestion_id``.

    O caller é responsável pelo ``session.commit()`` (mesmo padrão do
    ``run_nelo_sync``).
    """
    from src.adapters.nelo import services

    date_to = date.today()
    date_from = since or (date_to - timedelta(days=lookback_days))

    # 1. Audit — um IngestionRun por load. Sem ficheiro de origem (a
    #    fonte é o ERP relacional), usa-se sentinelas explícitas.
    run = IngestionRun(
        created_by="curated_loader",
        source_type=SourceType.SCHEDULE,
        file_name=f"erp:OF_FP+OF_CHECKLIST+OFFP_EQ@{date_from}..{date_to}",
        file_size_bytes=0,
        file_sha256="0" * 64,
        status=IngestionStatus.CURATING,
        quality_gate_status=QualityGateStatus.PASSED,
        started_at_utc=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.flush()  # garante run.id

    # 2. Ler as 3 fontes do ERP.
    operations = await services.list_operations(
        date_from=date_from, date_to=date_to,
    )
    crew = await services.list_operation_crew(
        date_from=date_from, date_to=date_to,
    )
    incidents = await services.list_checklist_incidents(
        date_from=date_from, date_to=date_to,
    )

    # 3. Transformar (puro).
    order_phase_rows = operations_to_order_phases(operations, run.id)
    allocation_rows = crew_to_allocations(crew, run.id)
    quality_rows = checklist_to_quality_events(incidents, run.id)

    # 4. Full-refresh — limpar as 3 tabelas e reescrever. O
    #    ingestion_id novo isola as linhas; apagar as antigas evita
    #    acumular ingestões mortas.
    await session.execute(delete(CuratedAllocation))
    await session.execute(delete(CuratedQualityEvent))
    await session.execute(delete(CuratedOrderPhase))

    for payload in order_phase_rows:
        session.add(CuratedOrderPhase(**payload))
    for payload in allocation_rows:
        session.add(CuratedAllocation(**payload))
    for payload in quality_rows:
        session.add(CuratedQualityEvent(**payload))
    await session.flush()

    # 5. Fechar o IngestionRun.
    total = len(order_phase_rows) + len(allocation_rows) + len(quality_rows)
    run.status = IngestionStatus.SUCCEEDED
    run.total_rows_raw = len(operations) + len(crew) + len(incidents)
    run.total_rows_curated = total
    run.completed_at_utc = datetime.now(timezone.utc)
    await session.flush()

    counts = {
        "ingestion_id": str(run.id),
        "order_phase": len(order_phase_rows),
        "allocation": len(allocation_rows),
        "quality_event": len(quality_rows),
    }
    logger.info(
        "curated_loader — janela=%s..%s order_phase=%d allocation=%d "
        "quality_event=%d",
        date_from, date_to, len(order_phase_rows), len(allocation_rows),
        len(quality_rows),
    )
    return counts


__all__ = [
    "checklist_to_quality_events",
    "crew_to_allocations",
    "load_curated",
    "operations_to_order_phases",
]
