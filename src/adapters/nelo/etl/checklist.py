"""Q.167.A — checklist root-cause mirror (ERP ``OF_CHECKLIST`` → ``quality.rework_entry``).

The legacy OF_FP quality mirror (:mod:`.quality`) can only set
``phase_id_causer == phase_id_rework`` — ``OF_FP`` knows only the phase a
rework *happened* in. ``OF_CHECKLIST`` is the **canonical root-cause
source**: it separates the phase that **caused** a defect (``OFCH_FP_ID``)
from the phase that **detected** it (``OFCH_FP_ID_CHK``) — distinct in
78.5 % of rows — and names the culprit operation (``OFCH_OFFP_ID_CULPA``),
from which the responsible operator + chefe are resolved via ``OFFP_EQ``.
``OFCH_CULPA_CHEFE`` marks the chefe as the party at fault.

One ``rework_entry`` per real defect (``OFCH_GRAVIDADE >= 1``; gravidade 0
is an "Ok" tick). ``id`` is ``uuid5`` of ``OFCH_ID`` — a **distinct
namespace** from the OFFP-keyed :mod:`.quality` mirror, so the two never
collide. ``context.source = "erp_of_checklist"`` lets dashboards tell the
canonical-RCA rows from the legacy OF_FP rows (reconciling the two defect
streams is a follow-up — see the campaign plan).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_DNS, UUID, uuid5

from sqlalchemy import select

from src.adapters.nelo import services
from src.adapters.nelo.schemas import ChecklistIncidentRow
from src.core.models.employee import Employee
from src.quality.models.rework import ReworkEntry

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Window default — one year, enough for the quality dashboards.
_DEFAULT_LOOKBACK_DAYS = 365

# OFCH_GRAVIDADE → severity (1/2/3 → low/medium/high; CEO-confirmed
# 2026-04-26 that all three count as defects). Inlined to avoid a
# cross-package import into the adapter layer.
_GRAVIDADE_TO_SEVERITY: Dict[int, str] = {1: "low", 2: "medium", 3: "high"}


def _as_utc(value: Any) -> Optional[datetime]:
    """Coerce an ERP timestamp to tz-aware UTC (``detected_at`` is timestamptz)."""
    dt: Optional[datetime] = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _severity(gravidade: Any) -> str:
    try:
        return _GRAVIDADE_TO_SEVERITY.get(int(gravidade), "medium")
    except (TypeError, ValueError):
        return "medium"


def build_rework_from_checklist(
    incidents: List[ChecklistIncidentRow],
    by_code: Dict[str, UUID],
) -> List[Dict[str, Any]]:
    """One ``rework_entry`` dict per checklist defect, with the **real**
    causer ≠ detector split and the responsible operator resolved.

    ``by_code`` maps ERP ``E_ID`` (as str) → ``core.employees.id``. Per
    ``OFCH_CULPA_CHEFE``: when the chefe is at fault the causer is the
    chefe, otherwise the operário; the chefe is always recorded too.
    """
    rows: List[Dict[str, Any]] = []
    for inc in incidents:
        detected = _as_utc(inc.detected_at)
        if detected is None:
            continue

        # Causer vs detector — the whole point. Fall back to the causer
        # phase only when the ERP left the detector phase null.
        causer_phase = str(inc.phase_id_causer)
        rework_phase = (
            str(inc.phase_id_detector)
            if inc.phase_id_detector is not None
            else causer_phase
        )

        chefe_id = by_code.get(str(inc.causer_chefe_eid)) if inc.causer_chefe_eid else None
        operator_id = (
            by_code.get(str(inc.causer_operator_eid)) if inc.causer_operator_eid else None
        )
        # OFCH_CULPA_CHEFE → the chefe is the party at fault.
        causer_id = chefe_id if inc.culpa_chefe else operator_id

        description = (inc.description or "Defeito de checklist sem descrição").strip()
        rows.append({
            "id": uuid5(NAMESPACE_DNS, f"nelo-erp-ofch-{inc.checklist_id}"),
            "of_id": str(inc.work_order_id),
            "model_id": str(inc.product_id) if inc.product_id else None,
            "phase_id_causer": causer_phase,
            "phase_id_rework": rework_phase,
            "causer_employee_id": causer_id,
            "chefe_employee_id": chefe_id,
            "original_op_id": str(inc.causer_op_id) if inc.causer_op_id else None,
            "rework_op_id": str(inc.detector_op_id) if inc.detector_op_id else None,
            "error_code": f"CHK-P{inc.phase_id_causer}",
            "error_description": description[:2000],
            "detected_at": detected,
            "context": {
                "erp_ofch_id": str(inc.checklist_id),
                "gravidade_raw": int(inc.gravidade),
                "severity_hint": _severity(inc.gravidade),
                # Q.167.E — `severe_return` é a chave que as marts de
                # molde/disciplina lêem para o "rework grave"
                # (`(context->>'severe_return')::boolean`). O OF_FP punha-a de
                # OFFP_RETORNO_GRAVE; o checklist deriva-a da gravidade máxima
                # (3 = high/grave). Sem isto, as measures `.graves` zeravam ao
                # trocar a fonte para OF_CHECKLIST.
                "severe_return": int(inc.gravidade) >= 3,
                "estado": inc.estado,
                "culpa_chefe": bool(inc.culpa_chefe),
                "molde_reparar": bool(inc.molde_reparar),
                "product_type_name": inc.product_type_name,
                "source": "erp_of_checklist",
            },
        })
    return rows


async def _employee_id_by_code(session, tenant_id: UUID) -> Dict[str, UUID]:
    """Map ERP operator key (``core.employees.employee_code`` == ``E_ID``) → row UUID."""
    rows = await session.execute(
        select(Employee.employee_code, Employee.id).where(Employee.tenant_id == tenant_id)
    )
    return {str(code): eid for code, eid in rows}


async def mirror_checklist(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror ERP checklist defects into ``quality.rework_entry`` with real RCA."""
    async with EtlRunner(session, tenant_id, source="checklist") as run:
        date_from = since or (date.today() - timedelta(days=_DEFAULT_LOOKBACK_DAYS))
        date_to = date.today()
        incidents = await services.list_checklist_incidents(date_from=date_from, date_to=date_to)
        run.count_read(len(incidents))

        by_code = await _employee_id_by_code(session, tenant_id)
        rework = build_rework_from_checklist(incidents, by_code)
        run.count_skipped(len(incidents) - len(rework))

        await run.upsert(
            ReworkEntry, rework,
            key_fields=["id"],
            update_fields=[
                "of_id", "model_id", "phase_id_causer", "phase_id_rework",
                "causer_employee_id", "chefe_employee_id", "original_op_id",
                "rework_op_id", "error_code", "error_description", "detected_at",
                "context",
            ],
        )
        n_split = sum(1 for r in rework if r["phase_id_causer"] != r["phase_id_rework"])
        logger.info(
            "checklist mirror — window=%s..%s defects=%d causer!=detector=%d",
            date_from, date_to, len(rework), n_split,
        )
    return run.result


register_mirror("checklist", mirror_checklist)
