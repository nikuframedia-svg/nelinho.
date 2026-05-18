"""Q.36.B — quality mirror (ERP OF_CHECKLIST → quality.error_catalog + rework_entry).

A fonte real de retrabalho/defeitos na MAR-KAYAKS é a tabela
``dbo.OF_CHECKLIST`` (≈3 M linhas): texto livre do defeito
(``OFCH_DESCR``), gravidade (``OFCH_GRAVIDADE`` 1/2/3), molde a reparar
(``OFCH_MOLDE_REPARAR``), operação culpada (``OFCH_OFFP_ID_CULPA``). O
mirror antigo (Q.20.E) lia as colunas ``OFFP_PROBS_*`` / a tabela
``OFFP_PROBLEMA`` — ambas **vazias** neste ERP — pelo que o
``rework_entry`` ficou 99% ``RETURN`` não-categorizado.

Este mirror, sobre uma janela ``[since, today]``:

* deriva o vocabulário de defeitos a partir das ``OFCH_DESCR`` distintas
  → ``quality.error_catalog``;
* materializa uma linha por incidente de checklist
  → ``quality.rework_entry``.

Cada ``rework_entry.id`` é um ``uuid5`` determinístico do ``OFCH_ID`` —
re-importar uma janela sobreposta faz upsert, nunca duplica.

O ``causer_employee_id`` é resolvido honestamente: liga a operação
culpada (``OFCH_OFFP_ID_CULPA``, senão a própria ``OFCH_OFFP_ID``) ao
operador via ``OFFP_EQ`` (preferindo o chefe quando ``OFCH_CULPA_CHEFE``)
e desse operador ao ``core.employees``. Quando nada disto resolve fica
``None`` — sem fabricar um causador.

Tabela pesada — passar sempre ``since`` para limitar a janela. O mirror
corre incrementalmente.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_DNS, UUID, uuid5

from sqlalchemy import select

from src.adapters.nelo import services
from src.adapters.nelo.schemas import ChecklistRow, OperationCrewRow
from src.core.models.employee import Employee
from src.factory_data_product.ingest.gravidade import map_gravidade_to_severity
from src.quality.models.rework import ErrorCatalog, ReworkEntry

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Look-back por omissão quando o caller não passa ``since`` — um ano de
# checklist, suficiente para os dashboards de qualidade sem varrer 7 anos.
_DEFAULT_LOOKBACK_DAYS = 365

# Palavras-chave que marcam um defeito como atribuível ao molde quando a
# flag ``OFCH_MOLDE_REPARAR`` não está activa. Mantém-se alinhado com
# ``erro_tree._MOLD_TYPED_ERROR_KEYWORDS`` — o detector causal classifica
# os mesmos defeitos como mold-typed.
_MOLD_KEYWORDS = (
    "molde", "interior enrugado", "molde baço", "molde baco",
    "deformação", "deformacao", "bolha", "desmold",
)


def _as_utc(value: Any) -> Optional[datetime]:
    """Coage um timestamp do ERP para datetime tz-aware (UTC) —
    ``rework_entry.detected_at`` é ``timestamptz``."""
    dt: Optional[datetime] = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_mold_related(chk: ChecklistRow) -> bool:
    """Um defeito é de molde se a flag ``OFCH_MOLDE_REPARAR`` estiver
    activa, ou se o texto do defeito casar uma keyword de molde."""
    if chk.mold_repair:
        return True
    text = f"{chk.description or ''} {chk.description_en or ''}".lower()
    return any(kw in text for kw in _MOLD_KEYWORDS)


def _error_code(description: str) -> str:
    """Código estável e curto derivado da descrição livre do defeito.

    O ``OFCH_DESCR`` é texto livre — para o catálogo agregar de forma
    limpa entre anos de dados, normaliza-se: minúsculas, sem acentos
    perdidos, espaços→hífen, recorte a 64 chars (largura da coluna). Duas
    linhas com a mesma descrição → o mesmo código → uma entrada.
    """
    slug = (description or "").strip().lower()
    slug = re.sub(r"[^\w\s-]", "", slug, flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    if not slug:
        return "sem-descricao"
    return slug[:64]


def _crew_index(crew: List[OperationCrewRow]) -> Dict[int, OperationCrewRow]:
    """``{operation_id: linha de crew}`` — quando uma operação tem mais do
    que um operador, privilegia o chefe (o ``OFCH_CULPA_CHEFE`` aponta o
    chefe da operação como o causador)."""
    index: Dict[int, OperationCrewRow] = {}
    for row in crew:
        current = index.get(row.operation_id)
        if current is None or (row.is_chefe and not current.is_chefe):
            index[row.operation_id] = row
    return index


def build_catalog(incidents: List[ChecklistRow]) -> List[Dict[str, Any]]:
    """Vocabulário distinto de defeitos sobre a janela de checklist.

    Uma gravidade mais alta na mesma descrição eleva o ``severity_hint``;
    um defeito de molde marca a entrada ``mold_related``.
    """
    _rank = {"low": 0, "medium": 1, "high": 2}
    seen: Dict[str, Dict[str, Any]] = {}
    for chk in incidents:
        code = _error_code(chk.description)
        severity = map_gravidade_to_severity(chk.severity)
        mold_related = _is_mold_related(chk)
        entry = seen.get(code)
        if entry is None:
            seen[code] = {
                "error_code": code,
                "name": (chk.description or code)[:255],
                "severity_hint": severity,
                "typical_phase": str(chk.phase_id) if chk.phase_id else None,
                "mold_related": mold_related,
            }
        else:
            if _rank[severity] > _rank[entry["severity_hint"]]:
                entry["severity_hint"] = severity
            if mold_related:
                entry["mold_related"] = True
    return list(seen.values())


def build_rework(
    incidents: List[ChecklistRow],
    *,
    crew_by_op: Optional[Dict[int, OperationCrewRow]] = None,
    employee_by_code: Optional[Dict[str, UUID]] = None,
) -> List[Dict[str, Any]]:
    """Uma linha de ``rework_entry`` por incidente de checklist.

    ``id`` é ``uuid5`` do ``OFCH_ID`` para que uma janela re-importada
    faça upsert em vez de duplicar. ``causer_employee_id`` é resolvido
    via a operação culpada → ``OFFP_EQ`` → ``core.employees``; quando não
    resolve fica ``None`` (honesto — sem inventar um causador).
    """
    crew_by_op = crew_by_op or {}
    employee_by_code = employee_by_code or {}
    rows: List[Dict[str, Any]] = []
    for chk in incidents:
        detected = (
            _as_utc(chk.detected_at)
            or _as_utc(chk.verified_at)
            or _as_utc(chk.updated_at)
        )
        if detected is None:
            continue

        # Causador: a operação culpada (OFCH_OFFP_ID_CULPA) tem
        # precedência; senão a operação onde o defeito foi apontado.
        culprit_op = chk.blame_operation_id or chk.operation_id
        causer_id: Optional[UUID] = None
        if culprit_op is not None:
            crew_row = crew_by_op.get(culprit_op)
            if crew_row is not None:
                causer_id = employee_by_code.get(str(crew_row.operator_id))

        mold_related = _is_mold_related(chk)
        rows.append({
            "id": uuid5(NAMESPACE_DNS, f"nelo-erp-ofch-{chk.checklist_id}"),
            "of_id": str(chk.work_order_id) if chk.work_order_id else "",
            "model_id": None,
            "causer_employee_id": causer_id,
            "phase_id_causer": str(chk.phase_id) if chk.phase_id else None,
            "phase_id_rework": str(chk.phase_id) if chk.phase_id else None,
            "error_code": _error_code(chk.description),
            "error_description": chk.description,
            "mold_id": (
                str(chk.operation_mold_id)
                if chk.operation_mold_id is not None else None
            ),
            "detected_at": detected,
            "context": {
                "erp_ofch_id": str(chk.checklist_id),
                "erp_offp_id": str(chk.operation_id) if chk.operation_id else None,
                "severity": map_gravidade_to_severity(chk.severity),
                "gravidade_raw": chk.severity,
                "mold_repair": bool(chk.mold_repair),
                "mold_related": mold_related,
                "blame_chefe": bool(chk.blame_chefe),
                "resolved": bool(chk.resolved),
                "phase_name": chk.phase_name,
                "source": "erp_of_checklist",
            },
        })
    return rows


async def _employee_by_code(session, tenant_id: UUID) -> Dict[str, UUID]:
    """``{employee_code: row UUID}`` — o ``employee_code`` carrega o
    ``E_ID`` do ERP (igual ao ``OFFPEQ_E_ID``)."""
    rows = await session.execute(
        select(Employee.employee_code, Employee.id).where(
            Employee.tenant_id == tenant_id
        )
    )
    return {str(code): eid for code, eid in rows}


async def mirror_quality(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Espelha os incidentes de qualidade (`OF_CHECKLIST`) no catálogo de
    erros + log de retrabalho."""
    async with EtlRunner(session, tenant_id, source="quality") as run:
        date_from = since or (date.today() - timedelta(days=_DEFAULT_LOOKBACK_DAYS))
        date_to = date.today()

        incidents = await services.list_checklist_incidents(
            date_from=date_from, date_to=date_to,
        )
        run.count_read(len(incidents))

        # Crew da janela para resolver o causador. O mapa employee_code→UUID
        # vem do que o mirror master-data já escreveu em core.employees.
        crew = await services.list_operation_crew(
            date_from=date_from, date_to=date_to,
        )
        crew_by_op = _crew_index(crew)
        employee_by_code = await _employee_by_code(session, tenant_id)

        # 1. Catálogo de erros — vocabulário distinto dos defeitos.
        catalog = build_catalog(incidents)
        await run.upsert(
            ErrorCatalog, catalog,
            key_fields=["error_code"],
            update_fields=["name", "severity_hint", "typical_phase", "mold_related"],
        )

        # 2. Linhas de retrabalho — uma por incidente, com id determinístico.
        rework = build_rework(
            incidents,
            crew_by_op=crew_by_op,
            employee_by_code=employee_by_code,
        )
        await run.upsert(
            ReworkEntry, rework,
            key_fields=["id"],
            update_fields=[
                "of_id", "model_id", "causer_employee_id",
                "phase_id_causer", "phase_id_rework",
                "error_code", "error_description", "mold_id",
                "detected_at", "context",
            ],
        )
        resolved_causer = sum(1 for r in rework if r["causer_employee_id"])
        logger.info(
            "quality mirror — janela=%s..%s incidentes=%d catálogo=%d "
            "causador-resolvido=%d/%d",
            date_from, date_to, len(incidents), len(catalog),
            resolved_causer, len(rework),
        )
    return run.result


register_mirror("quality", mirror_quality)
