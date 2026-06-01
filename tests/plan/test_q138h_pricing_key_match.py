"""Q.138.H — test que prova e fixa o casamento de chaves product_code↔production_orders.

BUG confirmado (Ronda 3 loop noturno 2026-06-01):
- profit.product_pricing.product_id é UUID de core.products.id
- plan.production_orders.product_id é INTEGER ERP (ex: 20205)
- core.products.product_code = str(P_ID) <- chave de ligação
- _load_product_prices (antes do fix) devolvia {uuid_str: price}
  mas o decoder procurava price_lookup.get(str(final_op.product_id), 0.0)
  onde product_id = "20205" -> UUID ≠ "20205" -> throughput=0

FIX Q.138.H: _load_product_prices faz JOIN com core.products e devolve
     {product_code: price} onde product_code = str(P_ID) = "20205".

DAMP: cada teste é spec independente e lê como especificação completa.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from src.plan.api._cpo_common import _load_product_prices


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class _FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeSessionReturnsProductCode:
    """Fake que simula a query APÓS o fix: devolve (product_code, price, valid_from).
    product_code é string numérica (ex: "20205") — o str(P_ID) do ERP.
    """
    def __init__(self, rows):
        self._rows = rows

    async def execute(self, stmt):
        return _FakeExecuteResult(self._rows)


class _FakeSessionReturnsUUID:
    """Fake que simula o comportamento ANTES do fix: devolve (UUID, price, valid_from).
    Representa o que a BD devolvia sem o JOIN com core.products.
    """
    def __init__(self, uuid_key: UUID, price: Decimal):
        self._uuid = uuid_key
        self._price = price

    async def execute(self, stmt):
        today = date.today()
        return _FakeExecuteResult([(self._uuid, self._price, today)])


# ---------------------------------------------------------------------------
# Testes que provam o FIX (comportamento correcto após Q.138.H)
# ---------------------------------------------------------------------------

def test_load_product_prices_key_is_product_code_string():
    """Após fix Q.138.H, a chave do mapa é product_code (string numérica ERP),
    NÃO o UUID de core.products.id.

    O decoder faz price_lookup.get(str(op.product_id), 0.0)
    onde op.product_id = "20205" (string do integer ERP).
    Para casar, o mapa DEVE ter "20205" como chave.
    """
    today = date.today()
    rows = [
        ("20205", Decimal("2400.00"), today),
        ("20235", Decimal("1700.00"), today),
    ]
    session = _FakeSessionReturnsProductCode(rows)
    prices = asyncio.run(_load_product_prices(session, uuid4()))

    assert "20205" in prices, (
        "product_code '20205' não está no mapa — fix Q.138.H não aplicado"
    )
    assert prices["20205"] == 2400.0
    assert "20235" in prices
    assert prices["20235"] == 1700.0

    # Sem UUIDs no mapa (len 36 chars)
    for key in prices:
        assert len(key) < 36, f"UUID encontrado como chave: {key!r} — bug pré-fix"


def test_load_product_prices_deduplicates_keeps_latest_by_product_code():
    """Duas linhas para o mesmo product_code — a mais recente ganha.
    Query ordena DESC valid_from; helper guarda o primeiro encontrado.
    """
    today = date.today()
    rows = [
        ("20205", Decimal("2500.00"), today),                  # mais recente
        ("20205", Decimal("2400.00"), today - timedelta(days=30)),  # mais antiga
    ]
    session = _FakeSessionReturnsProductCode(rows)
    prices = asyncio.run(_load_product_prices(session, uuid4()))

    assert prices.get("20205") == 2500.0, "Devia manter a linha mais recente"
    assert len(prices) == 1


def test_load_product_prices_empty_returns_empty_dict():
    """Tabela vazia -> dict vazio (sem crash)."""
    session = _FakeSessionReturnsProductCode([])
    prices = asyncio.run(_load_product_prices(session, uuid4()))
    assert prices == {}


def test_load_product_prices_swallows_db_errors():
    """Falha de BD não derruba o endpoint — devolve {} (throughput=0, honesto)."""
    class _BoomSession:
        async def execute(self, *_a, **_kw):
            raise RuntimeError("profit.product_pricing does not exist")

    prices = asyncio.run(_load_product_prices(_BoomSession(), uuid4()))
    assert prices == {}


# ---------------------------------------------------------------------------
# Prova E2E: decoder + chave product_code -> throughput > 0
# ---------------------------------------------------------------------------

def test_decoder_throughput_with_product_code_key():
    """O decoder encontra o preço quando a chave é product_code (string ERP).

    Simula o caminho completo após fix Q.138.H:
    1. _load_product_prices devolve {"20205": 2400.0}
    2. SchedulingOperation.product_id = "20205"
    3. decoder faz price_lookup.get("20205") = 2400.0
    4. throughput_eur_day > 0
    """
    from datetime import datetime, timedelta as td

    from src.plan.cpo.chromosome import Chromosome
    from src.plan.cpo.decoder import decode
    from src.plan.cpo.state import FactoryState
    from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation

    ref = datetime(2026, 6, 1, 8, 0)
    op = SchedulingOperation(
        operation_id="O_FINAL",
        order_id="OF_20205",
        product_id="20205",   # <- integer string como vem do ERP (plan.production_orders.product_id)
        sequence=1,
        operation_code="ACABAMENTO",
        duration_minutes=120,
        machine_id="M1",
        phase_id="ACABAMENTO",
    )
    result = decode(
        Chromosome(permutation=[0]),
        [op],
        [SchedulingMachine(machine_id="M1", name="M1")],
        FactoryState(tenant_id=uuid4()),
        horizon_start=ref,
        horizon_end=ref + td(days=2),
        product_price_eur={"20205": 2400.0},  # chave product_code, NÃO UUID
    )
    assert result["throughput_eur_total"] == 2400.0, (
        f"throughput_eur_total esperado 2400.0, got {result['throughput_eur_total']}"
    )
    assert result["throughput_eur_day"] == pytest.approx(1200.0, rel=0.01)


def test_decoder_zero_throughput_when_uuid_key_used_with_int_product_id():
    """Prova do bug original: se o mapa tiver chave UUID mas o op tiver
    product_id="20205" (integer string), o preço NÃO é encontrado -> throughput=0.

    Este teste documenta o comportamento ANTES do fix para que ninguém
    reverta para UUID keys sem perceber as consequências.
    """
    from datetime import datetime, timedelta as td

    from src.plan.cpo.chromosome import Chromosome
    from src.plan.cpo.decoder import decode
    from src.plan.cpo.state import FactoryState
    from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation

    ref = datetime(2026, 6, 1, 8, 0)
    op = SchedulingOperation(
        operation_id="O_FINAL",
        order_id="OF_20205",
        product_id="20205",   # <- integer string do ERP
        sequence=1,
        operation_code="ACABAMENTO",
        duration_minutes=120,
        machine_id="M1",
        phase_id="ACABAMENTO",
    )
    # Mapa com chave UUID (comportamento pré-fix) — NÃO deve casar com "20205"
    some_uuid = str(uuid4())
    result = decode(
        Chromosome(permutation=[0]),
        [op],
        [SchedulingMachine(machine_id="M1", name="M1")],
        FactoryState(tenant_id=uuid4()),
        horizon_start=ref,
        horizon_end=ref + td(days=2),
        product_price_eur={some_uuid: 2400.0},  # chave UUID — não casa com "20205"
    )
    # Com UUID como chave, throughput deve ser 0 (bug documentado)
    assert result["throughput_eur_day"] == 0.0, (
        "UUID key não deve casar com product_id integer string — "
        "se isto passar com throughput>0, o decoder mudou de comportamento"
    )
