"""Q.20.B — master-data mirror (ERP → core.* + plan.routing_template*).

Mirrors the small, slow-changing master data the CPO scheduler / profit /
ML query on every run:

* ``vw_pp1_produto``            → ``core.products``
* ``vw_pp1_entidade``           → ``core.employees`` (the 122 operators)
* ``vw_pp1_produto_componente`` → ``core.bom_items``
* ``vw_pp1_produto_fase``       → ``plan.routing_template`` +
  ``routing_template_phase`` + ``model_routing_assignment``

Routing structure only — ``duration_p50_h``/``p90_h`` are left NULL here
and filled by the Q.20.F historical time-mining. The 899 products collapse
onto far fewer routing *patterns* (products with an identical ordered
phase list share one template).

Idempotent: re-running upserts by business key, never duplicates, and
never touches the mined duration columns.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import select

from src.core.models.employee import Employee, EmploymentStatus
from src.core.models.product import Product, ProductStatus, ProductType
from src.core.models.bom import BOMItem
from src.plan.models.routing_template import (
    ModelRoutingAssignment,
    RoutingTemplate,
    RoutingTemplatePhase,
)

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Employees whose ERP record has no admission date still need a non-null
# hire_date (the column is NOT NULL). Use an unmistakable sentinel so a
# report can spot "hire date unknown" rather than trusting a fake value.
_HIRE_DATE_UNKNOWN = date(1900, 1, 1)


# ─── small mappers ──────────────────────────────────────────────────


def _truthy(value: Any) -> bool:
    """ERP booleans arrive as 1/0, '1'/'0', True/False."""
    if isinstance(value, str):
        return value.strip() in ("1", "true", "True", "S", "Sim")
    return bool(value)


def _classify_product_type(raw: Any) -> ProductType:
    """NELO products are kayaks (finished goods) plus a handful of
    semi-finished sub-assemblies. The ERP ``product_type_raw`` is a free
    string; anything that doesn't look like a sub-assembly is a finished
    good — the safe default for a kayak factory.
    """
    text = str(raw or "").strip().upper()
    if any(tag in text for tag in ("COMPON", "SEMI", "SUB", "MATERIA", "MATÉRIA")):
        return ProductType.SEMI_FINISHED
    return ProductType.FINISHED_GOOD


def _to_decimal(value: Any, default: Decimal = Decimal("1")) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


def _map_product(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """ERP product row → ``core.products`` column dict.

    ``product_code`` carries the ERP ``product_id`` — that is the key
    every other view (produto_fase, produto_componente, of_fp) joins on,
    so it must be the stable business key here. The human-readable code
    goes to ``customer_product_code``.
    """
    erp_id = row.get("product_id")
    if erp_id in (None, ""):
        return None
    return {
        "product_code": str(erp_id),
        "product_name": str(row.get("product_name") or erp_id),
        "customer_product_code": (
            str(row["product_code"]) if row.get("product_code") else None
        ),
        "product_type": _classify_product_type(row.get("product_type_raw")),
        "status": (
            ProductStatus.ACTIVE if _truthy(row.get("active"))
            else ProductStatus.INACTIVE
        ),
    }


def _map_worker(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """ERP entidade row → ``core.employees`` column dict."""
    erp_id = row.get("entidade_id")
    if erp_id in (None, ""):
        return None
    hire = row.get("data_admissao")
    if not isinstance(hire, date):
        hire = _HIRE_DATE_UNKNOWN
    return {
        "employee_code": str(erp_id),
        "employee_name": str(row.get("nome") or erp_id),
        "hire_date": hire,
        "status": (
            EmploymentStatus.ACTIVE if _truthy(row.get("activo"))
            else EmploymentStatus.TERMINATED
        ),
    }


# ─── mirror entry point ─────────────────────────────────────────────


async def mirror_master_data(
    *,
    session,
    tenant_id: UUID,
    adapter,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Run the master-data mirror under a single ``core.etl_run`` row."""
    async with EtlRunner(session, tenant_id, source="master") as run:
        await _mirror_products(run, adapter)
        await _mirror_employees(run, adapter)
        await _mirror_bom(run, session, tenant_id, adapter)
        await _mirror_routing(run, session, tenant_id, adapter)
    return run.result


async def _mirror_products(run: EtlRunner, adapter) -> None:
    rows = await adapter.fetch_products()
    run.count_read(len(rows))
    mapped = [m for m in (_map_product(r) for r in rows) if m is not None]
    run.count_skipped(len(rows) - len(mapped))
    await run.upsert(
        Product, mapped,
        key_fields=["product_code"],
        update_fields=["product_name", "customer_product_code",
                       "product_type", "status"],
    )


async def _mirror_employees(run: EtlRunner, adapter) -> None:
    rows = await adapter.fetch_workers(active_only=False)
    run.count_read(len(rows))
    mapped = [m for m in (_map_worker(r) for r in rows) if m is not None]
    run.count_skipped(len(rows) - len(mapped))
    await run.upsert(
        Employee, mapped,
        key_fields=["employee_code"],
        update_fields=["employee_name", "hire_date", "status"],
    )


async def _product_id_by_code(
    session, tenant_id: UUID,
) -> Dict[str, UUID]:
    """Map ERP product key (``core.products.product_code``) → row UUID."""
    rows = await session.execute(
        select(Product.product_code, Product.id).where(
            Product.tenant_id == tenant_id
        )
    )
    return {str(code): pid for code, pid in rows}


async def _mirror_bom(run: EtlRunner, session, tenant_id: UUID, adapter) -> None:
    rows = await adapter.fetch_components()
    run.count_read(len(rows))
    by_code = await _product_id_by_code(session, tenant_id)

    mapped: List[Dict[str, Any]] = []
    skipped = 0
    for r in rows:
        parent = by_code.get(str(r.get("produto_id")))
        component = by_code.get(str(r.get("componente_id")))
        if parent is None or component is None:
            # A BOM row referencing a product the mirror hasn't seen —
            # log + skip rather than crash (QA01 spirit: explicit, not silent).
            skipped += 1
            logger.warning(
                "bom row skipped — unknown product parent=%s component=%s",
                r.get("produto_id"), r.get("componente_id"),
            )
            continue
        mapped.append({
            "parent_product_id": parent,
            "component_product_id": component,
            "sequence": int(r.get("sequencia") or 0),
            "quantity_per": _to_decimal(r.get("quantidade")),
            "unit_of_measure": str(r.get("unidade") or "UN")[:10],
        })
    run.count_skipped(skipped)
    await run.upsert(
        BOMItem, mapped,
        key_fields=["parent_product_id", "component_product_id", "sequence"],
        update_fields=["quantity_per", "unit_of_measure"],
    )


# ─── routing: product phase lists → templates ───────────────────────


def _routing_signature(phases: Sequence[str]) -> str:
    """Stable code for a routing pattern — products sharing the same
    ordered phase list collapse onto one ``RoutingTemplate``.
    """
    joined = "|".join(phases)
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]
    return f"ERP-{digest}"


def group_routing_patterns(
    pf_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Tuple[List[Tuple[int, str, bool]], List[str]]]:
    """Collapse per-product phase rows onto routing patterns.

    Returns ``{signature: (ordered [(seq, fase_id, requires_mold)],
    [product_id, …])}``. Products with an identical ordered phase list
    share one signature — that is the whole point of templates.
    """
    by_product: Dict[str, List[Tuple[int, str, bool]]] = {}
    for r in pf_rows:
        pid = str(r.get("product_id") or "")
        fid = str(r.get("fase_id") or "")
        if not pid or not fid:
            continue
        by_product.setdefault(pid, []).append((
            int(r.get("sequencia") or 0),
            fid,
            _truthy(r.get("requires_mold")),
        ))

    patterns: Dict[str, Tuple[List[Tuple[int, str, bool]], List[str]]] = {}
    for pid, phases in by_product.items():
        phases.sort(key=lambda t: t[0])
        sig = _routing_signature([f for _, f, _ in phases])
        if sig not in patterns:
            patterns[sig] = (phases, [])
        patterns[sig][1].append(pid)
    return patterns


async def _mirror_routing(run: EtlRunner, session, tenant_id: UUID, adapter) -> None:
    """Build routing templates from ``vw_pp1_produto_fase``.

    ``duration_p50_h``/``p90_h`` are intentionally NOT written — they are
    mined from real history by Q.20.F. Phase upsert excludes those columns
    so a nightly master sync never wipes mined durations.
    """
    pf_rows = await adapter.fetch_product_phases()
    run.count_read(len(pf_rows))
    phase_rows = await adapter.fetch_phases()
    phase_name: Dict[str, str] = {
        str(p.get("fase_id")): str(p.get("fase_nome") or p.get("fase_id"))
        for p in phase_rows
    }

    patterns = group_routing_patterns(pf_rows)
    existing_templates = await _templates_by_code(session, tenant_id)
    assignment_rows: List[Dict[str, Any]] = []

    for code, (phases, product_ids) in patterns.items():
        template = existing_templates.get(code)
        if template is None:
            template = RoutingTemplate(
                tenant_id=tenant_id,
                code=code,
                name=f"Padrão ERP {len(phases)} fases",
                phase_count=len(phases),
                active=True,
                model_coverage=len(product_ids),
            )
            session.add(template)
            existing_templates[code] = template
            run.result.rows_inserted += 1
        else:
            template.phase_count = len(phases)
            template.model_coverage = len(product_ids)
            template.active = True
        await session.flush()  # ensure template.id is populated

        phase_dicts = [
            {
                "template_id": template.id,
                "seq": idx + 1,
                "phase_id": fid,
                "phase_name": phase_name.get(fid, fid),
                "requires_mold": mold,
            }
            for idx, (_, fid, mold) in enumerate(phases)
        ]
        await run.upsert(
            RoutingTemplatePhase, phase_dicts,
            key_fields=["template_id", "seq"],
            # NEVER list duration_p50_h / duration_p90_h — Q.20.F owns those.
            update_fields=["phase_id", "phase_name", "requires_mold"],
        )

        for pid in product_ids:
            assignment_rows.append({
                "model_id": pid,
                "primary_template_id": template.id,
            })

    await run.upsert(
        ModelRoutingAssignment, assignment_rows,
        key_fields=["model_id"],
        update_fields=["primary_template_id"],
    )


async def _templates_by_code(
    session, tenant_id: UUID,
) -> Dict[str, RoutingTemplate]:
    rows = await session.execute(
        select(RoutingTemplate).where(RoutingTemplate.tenant_id == tenant_id)
    )
    return {t.code: t for t in rows.scalars()}


register_mirror("master", mirror_master_data)
