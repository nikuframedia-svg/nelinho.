"""Q.31.F — GET /v1/search (pesquisa global).

Cobre:
  * `q` < 2 caracteres → resultados vazios, sem tocar na BD;
  * match em barcos / operadores / moldes / erros, cada um com o tipo certo;
  * `q` numérico procura também o nº de casco (legacy_id);
  * cada tipo limitado a `limit`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from src.core.models.employee import Employee
from src.plan.models.mold import Mold
from src.plan.models.order import ProductionOrder
from src.quality.models.rework import ErrorCatalog
from src.search.api import global_search
from tests.conftest import FakeSession

TENANT = UUID("00000000-0000-0000-0000-000000000001")


class _FakeSession(FakeSession):
    """Q.68.3.4 — subclasse local sobre o canónico.

    O endpoint emite 4 SELECTs distintos (ProductionOrder, Employee,
    Mold, ErrorCatalog). Cada um traz uma entidade diferente no
    ``column_descriptions[0]["entity"]``; dispatchamos a lista certa
    com base na entidade.
    """

    def __init__(self, by_entity: dict[Any, list]) -> None:
        super().__init__()
        self.by_entity = dict(by_entity)
        self.calls = 0

    async def execute(self, stmt: Any):  # type: ignore[override]
        self.calls += 1
        try:
            entity = stmt.column_descriptions[0]["entity"]
        except Exception:
            entity = None
        rows = self.by_entity.get(entity, [])
        self.queue_scalars(rows)
        return await super().execute(stmt)


def _order(**kw) -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(), tenant_id=TENANT, legacy_id=kw.get("legacy_id", 4271),
        product_name=kw.get("product_name", "K1 Vanquish"),
        product_type=kw.get("product_type", "K1"),
        current_phase_name=kw.get("phase", "Laminagem"),
    )


@pytest.mark.asyncio
async def test_short_query_returns_empty_without_db():
    session = _FakeSession({})
    out = await global_search(q="k", limit=5, tenant_id=TENANT, session=session)  # type: ignore[arg-type]
    assert out == {"query": "k", "results": []}
    assert session.calls == 0


@pytest.mark.asyncio
async def test_search_matches_each_entity_type():
    emp = Employee(
        id=uuid4(), employee_name="João Laminador", employee_code="OP-12",
    )
    mold = Mold(
        id=uuid4(), mold_code="MOLD-K1-03", name="Molde K1", model_id="K1",
    )
    err = ErrorCatalog(
        id=uuid4(), error_code="RESIN_BUBBLE", name="Bolha na resina",
    )

    session = _FakeSession({
        ProductionOrder: [_order()],
        Employee: [emp],
        Mold: [mold],
        ErrorCatalog: [err],
    })
    out = await global_search(q="la", limit=5, tenant_id=TENANT, session=session)  # type: ignore[arg-type]
    types = {r["type"] for r in out["results"]}
    assert types == {"barco", "operador", "molde", "erro"}
    barco = next(r for r in out["results"] if r["type"] == "barco")
    assert barco["label"] == "K1 #4271"


@pytest.mark.asyncio
async def test_numeric_query_still_runs_all_four_lookups():
    session = _FakeSession({ProductionOrder: [_order(legacy_id=5103)]})
    out = await global_search(q="5103", limit=5, tenant_id=TENANT, session=session)  # type: ignore[arg-type]
    assert session.calls == 4  # barcos + operadores + moldes + erros
    assert out["results"][0]["label"] == "K1 #5103"
