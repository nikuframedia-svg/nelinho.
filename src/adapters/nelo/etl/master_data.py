"""Q.20.B — master-data mirror (ERP → core.* + plan.routing_template*).

Mirrors the small, slow-changing master data the CPO scheduler / profit /
ML query on every run:

* ``list_products()``       → ``core.products``
* ``list_entities()``       → ``core.employees`` (the NELO operators)
* ``list_all_bom()``        → ``core.bom_items``
* ``list_all_routings()``   → ``plan.routing_template`` +
  ``routing_template_phase`` + ``model_routing_assignment``

Routing **structure** only — ``duration_p50_h`` / ``duration_p90_h`` are
left untouched here and filled by the Q.20.F historical time-mining.
The 14 k products collapse onto far fewer routing *patterns* (products
with an identical ordered phase list share one template).

Idempotent: re-running upserts by business key, never duplicates, and
never touches the mined duration columns.

All data comes from the read-only adapter :mod:`src.adapters.nelo.services`
— Pydantic schemas, never raw ERP column names.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from sqlalchemy import select

from src.adapters.nelo import services
from src.adapters.nelo.schemas import BomRow, EntityRow, ProductRow, RoutingRow
from src.core.models.bom import BOMItem
from src.core.models.employee import Employee, EmploymentStatus
from src.core.models.erp_variable import ErpVariable
from src.core.models.product import Product, ProductStatus, ProductType
from src.core.models.rates import LaborRate
from src.plan.models.routing_template import (
    ModelRoutingAssignment,
    RoutingTemplate,
    RoutingTemplatePhase,
)

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror
from src.shared.time import local_today

logger = logging.getLogger(__name__)

# Operators whose ERP record has no admission date still need a non-null
# hire_date (the column is NOT NULL). Use an unmistakable sentinel so a
# report can spot "hire date unknown" rather than trusting a fake value.
_HIRE_DATE_UNKNOWN = date(1900, 1, 1)


# ─── small mappers ──────────────────────────────────────────────────


def _classify_product_type(product_type_id: Optional[int]) -> ProductType:
    """NELO finished goods are kayaks; the catalogue also holds component
    sub-assemblies. ``PRODUTO.P_TP_ID`` is a free numeric classification
    in the ERP — without a confirmed mapping table we keep the safe
    default for a kayak factory (finished good) and only flag the obvious
    component bucket via :func:`_map_product` heuristics on the name.

    Kept as a hook so a real ``PRODUTO_TIPO`` map can slot in later.
    """
    return ProductType.FINISHED_GOOD


def _map_product(row: ProductRow) -> Optional[Dict[str, Any]]:
    """ERP product row → ``core.products`` column dict.

    ``product_code`` carries the ERP ``product_id`` — that is the key
    every other surface (routing, BOM, operations) joins on, so it must
    be the stable business key here.
    """
    if row.product_id in (None, ""):
        return None
    status = (
        ProductStatus.DISCONTINUED if row.discontinued
        else ProductStatus.ACTIVE if row.active
        else ProductStatus.INACTIVE
    )
    return {
        "product_code": str(row.product_id),
        "product_name": str(row.product_name or row.product_id),
        "product_type": _classify_product_type(row.product_type_id),
        "status": status,
        # P_PRECOCUSTO (€) — custo standard do produto. Q.26.A liga-o ao
        # COGS. Faithful: mapeia tal e qual o ERP (incl. 0 e negativos —
        # dado sujo a tratar a jusante, nao silenciar aqui).
        "standard_cost": _to_decimal(row.cost_price, default=Decimal("0")),
        # Q.167.F — P_TP_ID cru. O COGS usa-o para aplicar o factor de M.O.
        # (VAR_ID=2) aos componentes P_TP_ID=90. `_classify_product_type` (o
        # ENUM) é concern à parte e fica intacto.
        "erp_product_type_id": row.product_type_id,
    }


def _map_worker(row: EntityRow) -> Optional[Dict[str, Any]]:
    """ERP entity row → ``core.employees`` column dict.

    Only NELO-internal entities reach here (the adapter filters on
    ``is_internal``). ``entry_date`` (E_DATAENTRADA) feeds ``hire_date``;
    a missing date falls back to the explicit 1900-01-01 sentinel.

    NELO ERP convention: ex-workers are renamed with a ``z) `` prefix
    (lowercase z + closing-paren + space) so they sort to the bottom of
    every picker list. That rename always accompanies ``E_ACTIVO=0`` —
    we treat BOTH signals as TERMINATED for defence-in-depth.
    """
    if row.entity_id in (None, ""):
        return None
    hire = row.entry_date.date() if row.entry_date is not None else _HIRE_DATE_UNKNOWN
    name = str(row.name or row.entity_id)
    # z) prefix = ERP convention for ex-worker; E_ACTIVO=0 is canonical but
    # the prefix adds a second safety net in case the flag lags behind.
    is_terminated = (not row.active) or name.lower().startswith("z) ")
    return {
        "employee_code": str(row.entity_id),
        "employee_name": name,
        "hire_date": hire,
        "status": (
            EmploymentStatus.TERMINATED if is_terminated
            else EmploymentStatus.ACTIVE
        ),
    }


def _to_decimal(value: Any, default: Decimal = Decimal("1")) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


# ─── mirror entry point ─────────────────────────────────────────────


async def mirror_master_data(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Run the master-data mirror under a single ``core.etl_run`` row."""
    async with EtlRunner(session, tenant_id, source="master") as run:
        await _mirror_products(run)
        await _mirror_variables(run)
        await _mirror_employees(run)
        await _mirror_labor_rates(run, session, tenant_id)
        await _mirror_bom(run, session, tenant_id)
        await _mirror_routing(run, session, tenant_id)
    return run.result


async def _mirror_variables(run: EtlRunner) -> None:
    """Q.167.F — espelha dbo.VARIAVEIS (factor de M.O. VAR_ID=2 etc.)."""
    rows = await services.list_variables()
    run.count_read(len(rows))
    mapped = [
        {
            "var_id": r.var_id,
            "var_value": r.var_value,
            "var_description": r.var_description,
        }
        for r in rows
        if r.var_id is not None
    ]
    run.count_skipped(len(rows) - len(mapped))
    await run.upsert(
        ErpVariable, mapped,
        key_fields=["var_id"],
        update_fields=["var_value", "var_description"],
    )


async def _mirror_products(run: EtlRunner) -> None:
    rows = await services.list_products()
    run.count_read(len(rows))
    mapped = [m for m in (_map_product(r) for r in rows) if m is not None]
    run.count_skipped(len(rows) - len(mapped))
    await run.upsert(
        Product, mapped,
        key_fields=["product_code"],
        update_fields=[
            "product_name", "product_type", "status", "standard_cost",
            "erp_product_type_id",
        ],
    )


async def _mirror_employees(run: EtlRunner) -> None:
    rows = await services.list_entities(internal_only=True)
    run.count_read(len(rows))
    mapped = [m for m in (_map_worker(r) for r in rows) if m is not None]
    run.count_skipped(len(rows) - len(mapped))
    await run.upsert(
        Employee, mapped,
        key_fields=["employee_code"],
        update_fields=["employee_name", "hire_date", "status"],
    )


async def _employee_id_by_code(session, tenant_id: UUID) -> Dict[str, UUID]:
    """Map ERP operator key (``core.employees.employee_code``) → row UUID."""
    rows = await session.execute(
        select(Employee.employee_code, Employee.id).where(
            Employee.tenant_id == tenant_id
        )
    )
    return {str(code): eid for code, eid in rows}


def _map_labor_rate(
    row: EntityRow, by_code: Dict[str, UUID], as_of: date
) -> Optional[Dict[str, Any]]:
    """ERP entity → ``core.labor_rates`` dict (Q.26.C).

    ``E_CUSTOHORA`` e o custo/hora total a empresa — mapeia-se directo
    como ``loaded_rate``; ``burden_rate=0`` porque nao ha split de
    encargos a fabricar (o ERP ja da o total). Custo 0 entra tal e qual.
    """
    emp_id = by_code.get(str(row.entity_id))
    if emp_id is None:
        return None
    rate = _to_decimal(row.cost_per_hour, default=Decimal("0"))
    return {
        "employee_id": emp_id,
        "effective_date": as_of,
        "base_hourly_rate": rate,
        "burden_rate": Decimal("0"),
        "loaded_rate": rate,
        "currency_code": "EUR",
    }


async def _mirror_labor_rates(run: EtlRunner, session, tenant_id: UUID) -> None:
    """Sincroniza o custo/hora dos operadores -> ``core.labor_rates``.

    Uma linha por operador, time-phased na data do sync — re-correr no
    mesmo dia faz upsert; noutro dia cria uma linha nova (a taxa muda
    com o tempo, e guardar o historico e o comportamento certo).
    """
    rows = await services.list_entities(internal_only=True)
    run.count_read(len(rows))
    by_code = await _employee_id_by_code(session, tenant_id)
    as_of = local_today()
    mapped = [
        m for m in (_map_labor_rate(r, by_code, as_of) for r in rows)
        if m is not None
    ]
    run.count_skipped(len(rows) - len(mapped))
    await run.upsert(
        LaborRate, mapped,
        key_fields=["employee_id", "effective_date"],
        update_fields=["base_hourly_rate", "burden_rate", "loaded_rate"],
    )


async def _product_id_by_code(session, tenant_id: UUID) -> Dict[str, UUID]:
    """Map ERP product key (``core.products.product_code``) → row UUID."""
    rows = await session.execute(
        select(Product.product_code, Product.id).where(
            Product.tenant_id == tenant_id
        )
    )
    return {str(code): pid for code, pid in rows}


def _map_bom(rows: Sequence[BomRow], by_code: Dict[str, UUID]) -> Tuple[List[Dict[str, Any]], int]:
    """ERP BOM rows → ``core.bom_items`` dicts. Returns (mapped, skipped).

    ``PRODUTO_COMPONENTE`` has no sequence column; the stable ``bom_id``
    (COMP_ID) is used as the ``sequence`` so the (parent, component, seq)
    business key is unique and re-import is idempotent.
    """
    mapped: List[Dict[str, Any]] = []
    skipped = 0
    for r in rows:
        parent = by_code.get(str(r.parent_product_id))
        component = by_code.get(str(r.component_product_id))
        if parent is None or component is None:
            # BOM row referencing a product the mirror hasn't seen — log
            # + skip rather than crash (QA01 spirit: explicit, not silent).
            skipped += 1
            logger.warning(
                "bom row skipped — unknown product parent=%s component=%s",
                r.parent_product_id, r.component_product_id,
            )
            continue
        mapped.append({
            "parent_product_id": parent,
            "component_product_id": component,
            "sequence": int(r.bom_id),
            "quantity_per": _to_decimal(r.quantity),
            "unit_of_measure": "UN",
        })
    return mapped, skipped


async def _mirror_bom(run: EtlRunner, session, tenant_id: UUID) -> None:
    rows = await services.list_all_bom()
    run.count_read(len(rows))
    by_code = await _product_id_by_code(session, tenant_id)
    mapped, skipped = _map_bom(rows, by_code)
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
    rows: Sequence[RoutingRow],
) -> Dict[str, Tuple[List[Tuple[int, str, str]], List[str]]]:
    """Collapse per-product routing rows onto routing patterns.

    Returns ``{signature: (ordered [(seq, phase_id, phase_name)],
    [product_id, …])}``. Products with an identical ordered phase list
    share one signature — that is the whole point of templates. Rows
    without a phase (``PRODUTO_FASE`` allows NULL ``PRODF_FP_ID`` for
    free-text instruction lines) are dropped.
    """
    by_product: Dict[str, List[Tuple[int, str, str]]] = {}
    for r in rows:
        if r.product_id in (None, "") or r.phase_id in (None, ""):
            continue
        pid = str(r.product_id)
        fid = str(r.phase_id)
        by_product.setdefault(pid, []).append(
            (int(r.sequence or 0), fid, str(r.phase_name or fid))
        )

    patterns: Dict[str, Tuple[List[Tuple[int, str, str]], List[str]]] = {}
    for pid, phases in by_product.items():
        phases.sort(key=lambda t: t[0])
        sig = _routing_signature([f for _, f, _ in phases])
        if sig not in patterns:
            patterns[sig] = (phases, [])
        patterns[sig][1].append(pid)
    return patterns


async def _mirror_routing(run: EtlRunner, session, tenant_id: UUID) -> None:
    """Build routing templates from the product-phase routing surface.

    ``duration_p50_h`` / ``duration_p90_h`` are intentionally NOT written
    — they are mined from real history by Q.20.F. The phase upsert
    excludes those columns so a nightly master sync never wipes mined
    durations.
    """
    rows = await services.list_all_routings()
    run.count_read(len(rows))

    patterns = group_routing_patterns(rows)
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
                "phase_name": fname,
            }
            for idx, (_, fid, fname) in enumerate(phases)
        ]
        await run.upsert(
            RoutingTemplatePhase, phase_dicts,
            key_fields=["template_id", "seq"],
            # NEVER list duration_p50_h / duration_p90_h — Q.20.F owns those.
            update_fields=["phase_id", "phase_name"],
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


async def _templates_by_code(session, tenant_id: UUID) -> Dict[str, RoutingTemplate]:
    rows = await session.execute(
        select(RoutingTemplate).where(RoutingTemplate.tenant_id == tenant_id)
    )
    return {t.code: t for t in rows.scalars()}


register_mirror("master", mirror_master_data)
