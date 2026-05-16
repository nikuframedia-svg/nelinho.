"""Q.20.E — quality mirror (ERP → quality.error_catalog + rework_entry).

NELO has ~90k historical quality incidents. This mirror imports:

* ``vw_pp1_offp_probs``   → ``quality.error_catalog`` (the distinct error
  vocabulary) + ``quality.rework_entry`` (one row per incident)
* ``vw_pp1_of_checklist`` → ``quality.rework_entry`` (NOK checklist items)

Import is **incremental**: pass ``since`` to bound the window. Each
rework row's ``id`` is a deterministic ``uuid5`` of its ERP key, so
re-importing an overlapping window upserts instead of duplicating.

``severity_hint`` comes from ``map_gravidade_to_severity`` (OFCH_GRAVIDADE
1/2/3 → low/medium/high — confirmed with the NELO CEO 2026-04-26).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date, datetime, time, timezone
from typing import Any, Dict, List, Optional
from uuid import NAMESPACE_DNS, UUID, uuid5

from sqlalchemy import select

from src.core.models.employee import Employee
from src.factory_data_product.ingest.gravidade import map_gravidade_to_severity
from src.quality.models.rework import ErrorCatalog, ReworkEntry

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

_NOK_VALUES = {"NOK", "NÃO OK", "NAO OK", "FALHOU", "FAIL", "N", "0"}


def _norm(text: Any) -> str:
    return " ".join(str(text or "").strip().lower().split())


def _error_code(text: Any, prefix: str = "ERR") -> str:
    """Stable error code for a free-text description."""
    digest = hashlib.sha1(_norm(text).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def _is_nok(resultado: Any) -> bool:
    return str(resultado or "").strip().upper() in _NOK_VALUES


def _as_datetime(value: Any) -> Optional[datetime]:
    """Coerce an ERP timestamp to a tz-aware datetime (assume UTC when
    naive — ``rework_entry.detected_at`` is ``timestamptz``)."""
    dt: Optional[datetime] = None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime.combine(value, time.min)
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _mold_related(text: Any) -> bool:
    return "molde" in _norm(text)


async def _code_to_id(session, tenant_id: UUID) -> Dict[str, UUID]:
    rows = await session.execute(
        select(Employee.employee_code, Employee.id).where(
            Employee.tenant_id == tenant_id
        )
    )
    return {str(code): rid for code, rid in rows}


async def mirror_quality(
    *,
    session,
    tenant_id: UUID,
    adapter,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror quality incidents into the error catalogue + rework log."""
    async with EtlRunner(session, tenant_id, source="quality") as run:
        probs = await adapter.fetch_quality_problems(since=since)
        run.count_read(len(probs))
        checklists = await adapter.fetch_checklists(since=since)
        nok = [c for c in checklists if _is_nok(c.get("resultado"))]
        run.count_read(len(checklists))

        emp_by_code = await _code_to_id(session, tenant_id)

        # 1. Error catalogue — distinct vocabulary across probs + NOK items.
        catalog = _build_catalog(probs, nok)
        await run.upsert(
            ErrorCatalog, catalog,
            key_fields=["error_code"],
            update_fields=["name", "severity_hint", "typical_phase", "mold_related"],
        )

        # 2. Rework entries — one per incident, deterministically keyed.
        rework = _build_rework(probs, nok, emp_by_code)
        skipped = len(probs) + len(nok) - len(rework)
        run.count_skipped(max(0, skipped))
        await run.upsert(
            ReworkEntry, rework,
            key_fields=["id"],
            update_fields=[
                "of_id", "model_id", "causer_employee_id", "chefe_employee_id",
                "phase_id_causer", "phase_id_rework", "error_code",
                "error_description", "mold_id", "detected_at", "context",
            ],
        )
    return run.result


def _build_catalog(
    probs: List[Dict[str, Any]], nok: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Distinct error vocabulary. Worst gravidade wins for severity_hint."""
    seen: Dict[str, Dict[str, Any]] = {}
    for p in probs:
        desc = p.get("descricao")
        if not desc:
            continue
        code = _error_code(desc)
        grav = p.get("gravidade")
        entry = seen.get(code)
        if entry is None:
            seen[code] = {
                "error_code": code,
                "name": str(desc)[:255],
                "severity_hint": map_gravidade_to_severity(grav),
                "typical_phase": (
                    str(p["fase_culpada_id"]) if p.get("fase_culpada_id") else None
                ),
                "mold_related": _mold_related(desc),
                "_grav": _grav_int(grav),
            }
        else:
            g = _grav_int(grav)
            if g > entry["_grav"]:
                entry["_grav"] = g
                entry["severity_hint"] = map_gravidade_to_severity(grav)
    for c in nok:
        item = c.get("item")
        if not item:
            continue
        code = _error_code(item, prefix="CHK")
        if code not in seen:
            seen[code] = {
                "error_code": code,
                "name": str(item)[:255],
                "severity_hint": "medium",
                "typical_phase": str(c["fase_id"]) if c.get("fase_id") else None,
                "mold_related": _mold_related(item),
                "_grav": 0,
            }
    for entry in seen.values():
        entry.pop("_grav", None)
    return list(seen.values())


def _grav_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _build_rework(
    probs: List[Dict[str, Any]],
    nok: List[Dict[str, Any]],
    emp_by_code: Dict[str, UUID],
) -> List[Dict[str, Any]]:
    """One rework row per incident. ``id`` is uuid5 of the ERP key so a
    re-imported window upserts rather than duplicates."""
    rows: List[Dict[str, Any]] = []
    for p in probs:
        prob_id = p.get("prob_id")
        of_id = p.get("of_id")
        detected = _as_datetime(p.get("data_registo"))
        if prob_id in (None, "") or not of_id or detected is None:
            continue
        rows.append({
            "id": uuid5(NAMESPACE_DNS, f"nelo-erp-prob-{prob_id}"),
            "of_id": str(of_id),
            "model_id": str(p["modelo_id"]) if p.get("modelo_id") else None,
            "causer_employee_id": emp_by_code.get(str(p.get("entidade_culpada_id"))),
            "chefe_employee_id": emp_by_code.get(str(p.get("chefe_id"))),
            "phase_id_causer": (
                str(p["fase_culpada_id"]) if p.get("fase_culpada_id") else None
            ),
            "phase_id_rework": (
                str(p["fase_avaliacao_id"]) if p.get("fase_avaliacao_id") else None
            ),
            "error_code": _error_code(p.get("descricao")),
            "error_description": (
                str(p["descricao"]) if p.get("descricao") else None
            ),
            "mold_id": None,
            "detected_at": detected,
            "context": {
                "erp_prob_id": str(prob_id),
                "gravidade": p.get("gravidade"),
                "source": "erp_offp_probs",
            },
        })
    for c in nok:
        chk_id = c.get("checklist_id")
        of_id = c.get("of_id")
        detected = _as_datetime(c.get("data_registo"))
        if chk_id in (None, "") or not of_id or detected is None:
            continue
        rows.append({
            "id": uuid5(NAMESPACE_DNS, f"nelo-erp-checklist-{chk_id}"),
            "of_id": str(of_id),
            "model_id": None,
            "causer_employee_id": None,
            "chefe_employee_id": None,
            "phase_id_causer": str(c["fase_id"]) if c.get("fase_id") else None,
            "phase_id_rework": str(c["fase_id"]) if c.get("fase_id") else None,
            "error_code": _error_code(c.get("item"), prefix="CHK"),
            "error_description": str(c["item"]) if c.get("item") else None,
            "mold_id": None,
            "detected_at": detected,
            "context": {
                "erp_checklist_id": str(chk_id),
                "source": "erp_of_checklist",
            },
        })
    return rows


register_mirror("quality", mirror_quality)
