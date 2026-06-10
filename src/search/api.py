"""GET /v1/search — pesquisa global (Q.31.F).

Uma só caixa de pesquisa que varre os 4 tipos de entidade que o gestor
procura no dia-a-dia: barcos (ordens de fabrico), operadores, moldes e
erros (catálogo). Alimenta a command-palette do frontend.

Tenant-scoped. Match por `ILIKE %q%`; cada tipo limitado a `limit`
resultados para a palette ficar leve.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.employee import Employee
from src.plan.models.mold import Mold
from src.plan.models.order import ProductionOrder
from src.quality.models.rework import ErrorCatalog
from src.shared.auth.headers import require_tenant_header
from src.shared.database import get_session

router = APIRouter(prefix="/v1/search", tags=["search"])

_MIN_Q = 2


def _order_hit(o: ProductionOrder) -> dict[str, Any]:
    return {
        "type": "barco",
        "id": str(o.id),
        "label": f"{o.product_type or '?'} #{o.legacy_id}",
        "sublabel": o.current_phase_name or "—",
    }


def _employee_hit(e: Employee) -> dict[str, Any]:
    return {
        "type": "operador",
        "id": str(e.id),
        "label": e.employee_name,
        "sublabel": e.employee_code or "",
    }


def _mold_hit(m: Mold) -> dict[str, Any]:
    return {
        "type": "molde",
        "id": str(m.id),
        "label": m.mold_code,
        "sublabel": m.name or m.model_id or "",
    }


def _error_hit(c: ErrorCatalog) -> dict[str, Any]:
    return {
        "type": "erro",
        "id": str(c.id),
        "label": c.error_code,
        "sublabel": c.name or "",
    }


def _rank(hit: dict[str, Any], term: str) -> tuple[int, str]:
    """Q.170.H — relevância: exato < prefixo < prefixo-no-sublabel < substring.

    O ILIKE %q% devolvia em ordem arbitrária da BD (e sem ORDER BY o LIMIT
    nem era determinístico): procurar "Vanq" podia enterrar o "Vanquish"
    exato debaixo de matches de substring quaisquer."""
    t = term.lower()
    label = str(hit.get("label") or "").lower()
    sub = str(hit.get("sublabel") or "").lower()
    if label == t:
        rank = 0
    elif label.startswith(t):
        rank = 1
    elif sub.startswith(t):
        rank = 2
    else:
        rank = 3
    return (rank, label)


def _ranked(hits: list[dict[str, Any]], term: str, limit: int) -> list[dict[str, Any]]:
    return sorted(hits, key=lambda h: _rank(h, term))[:limit]


@router.get("")
async def global_search(
    q: str = Query(..., description="Texto a procurar (mínimo 2 caracteres)."),
    limit: int = Query(5, ge=1, le=20, description="Resultados por tipo."),
    tenant_id: UUID = Depends(require_tenant_header),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Pesquisa barcos / operadores / moldes / erros num só pedido.

    Q.170.H — cada tipo busca `limit*3` candidatos (ordenados na BD p/
    determinismo) e devolve os `limit` mais relevantes (exato > prefixo >
    substring)."""
    term = (q or "").strip()
    if len(term) < _MIN_Q:
        return {"query": term, "results": []}
    pat = f"%{term}%"
    fetch = limit * 3
    results: list[dict[str, Any]] = []

    # Barcos — nome/tipo do produto; nº de casco (legacy_id) quando q é dígito.
    order_conds = [
        ProductionOrder.product_name.ilike(pat),
        ProductionOrder.product_type.ilike(pat),
    ]
    if term.isdigit():
        order_conds.append(ProductionOrder.legacy_id == int(term))
    orders = (
        await session.execute(
            select(ProductionOrder)
            .where(ProductionOrder.tenant_id == tenant_id, or_(*order_conds))
            .order_by(ProductionOrder.product_name, ProductionOrder.legacy_id)
            .limit(fetch)
        )
    ).scalars().all()
    results += _ranked([_order_hit(o) for o in orders], term, limit)

    # Operadores — nome ou código.
    emps = (
        await session.execute(
            select(Employee)
            .where(
                Employee.tenant_id == tenant_id,
                or_(
                    Employee.employee_name.ilike(pat),
                    Employee.employee_code.ilike(pat),
                ),
            )
            .order_by(Employee.employee_name)
            .limit(fetch)
        )
    ).scalars().all()
    results += _ranked([_employee_hit(e) for e in emps], term, limit)

    # Moldes — código, nome ou modelo.
    molds = (
        await session.execute(
            select(Mold)
            .where(
                Mold.tenant_id == tenant_id,
                or_(
                    Mold.mold_code.ilike(pat),
                    Mold.name.ilike(pat),
                    Mold.model_id.ilike(pat),
                ),
            )
            .order_by(Mold.mold_code)
            .limit(fetch)
        )
    ).scalars().all()
    results += _ranked([_mold_hit(m) for m in molds], term, limit)

    # Erros — catálogo: código ou nome.
    errs = (
        await session.execute(
            select(ErrorCatalog)
            .where(
                ErrorCatalog.tenant_id == tenant_id,
                or_(
                    ErrorCatalog.error_code.ilike(pat),
                    ErrorCatalog.name.ilike(pat),
                ),
            )
            .order_by(ErrorCatalog.error_code)
            .limit(fetch)
        )
    ).scalars().all()
    results += _ranked([_error_hit(c) for c in errs], term, limit)

    return {"query": term, "results": results}
