"""Q.158 — `_boats_em_producao_summary` lê a contagem canónica de "barcos em
produção" (regra EXATA da NELO) da view `factory_raw.v_of_em_producao`.

`em_producao` = NOT is_fila (≈830, o que a fábrica conta); `total` = tudo que o
CPO planeia (≈1209). É **best-effort**: quando a view falta (dev sem mirror do
ERP) devolve `None` — o card cai no número por-encomenda, sem inventar.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.factory_data_product.services.factory_map_service import FactoryMapService

TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _Result:
    """Resultado mínimo com `.mappings().first()` (como o do SQLAlchemy)."""

    def __init__(self, row: dict | None) -> None:
        self._row = row

    def mappings(self) -> "_Result":
        return self

    def first(self) -> dict | None:
        return self._row


class _RowSession:
    """Session cuja `execute()` devolve uma linha de contagem (happy path)."""

    def __init__(self, row: dict) -> None:
        self._row = row

    async def execute(self, stmt, *args, **kwargs) -> _Result:  # noqa: ANN001
        return _Result(self._row)


class _RaisingSession:
    """Session cuja `execute()` rebenta — view ausente / outage."""

    async def execute(self, stmt, *args, **kwargs):  # noqa: ANN001
        raise SQLAlchemyError("relation factory_raw.v_of_em_producao does not exist")


@pytest.mark.asyncio
async def test_boats_em_producao_summary_happy_path() -> None:
    row = {
        "total": 1209,
        "em_producao": 830,
        "fila": 379,
        "reparacao": 161,
        "nova_producao": 669,
    }
    svc = FactoryMapService(_RowSession(row), TENANT)
    out = await svc._boats_em_producao_summary()
    assert out == row
    # em_producao (display) = total - fila (= NOT is_fila).
    assert out["em_producao"] == out["total"] - out["fila"]
    # reparacao + nova_producao = em_producao (os dois tipos NOT-fila).
    assert out["reparacao"] + out["nova_producao"] == out["em_producao"]


@pytest.mark.asyncio
async def test_boats_em_producao_summary_returns_none_when_view_missing() -> None:
    svc = FactoryMapService(_RaisingSession(), TENANT)
    out = await svc._boats_em_producao_summary()
    assert out is None
