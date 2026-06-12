"""Q.168.A — due_date fio-a-fio: loader → resolver → ops → cpo_meta.

A auditoria 2026-06-10 apanhou o elo partido: o SQL de `_load_open_orders_db`
SELECIONA `data_entrega_prevista` (COALESCE das 3 datas reais do ERP) mas o
dict devolvido NÃO incluía o campo — `RoutingResolver.resolve()` lia sempre
None e TODAS as ordens ficavam sem due_date. Resultado: backward-scheduling e
tardiness/OTD cegos (o teste Q.157.B verificava o SQL, nunca o dict).

Estes testes travam o fio completo:
  1. o dict do loader transporta `data_entrega_prevista`;
  2. a sentinela SQL-Server 1900-01-01 é anulada no SQL (sentinela ≠ data);
  3. o resolver converte-a em `SchedulingOperation.due_date` (datetime);
  4. sem data → due_date=None (nunca fabricado, invariante #8);
  5. o cpo_meta expõe a cobertura de due dates (observabilidade).
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.plan.cpo.state import FactoryState
from src.plan.services.routing_resolver import RoutingResolver

TENANT = UUID("11111111-1111-1111-1111-111111111111")

_ROW = {
    "of_id": "123456",
    "modelo_id": "42366",
    "current_fase_id": None,
    "is_mold": False,
    "done_fase_ids": [],
    "data_entrega_prevista": "2026-07-15T00:00:00",
    # Q.174.F0.1 — o SELECT real devolve a proveniência da due date.
    "due_source": "plano_erp",
}


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _RowsSession:
    """Sessão fake: devolve linhas prontas e captura o SQL gerado."""

    def __init__(self, rows):
        self._rows = rows
        self.sql_text = ""

    async def execute(self, stmt, params=None):
        self.sql_text = str(stmt)
        return _RowsResult(self._rows)


# ─────────────────────────── 1. loader → dict ────────────────────────────


@pytest.mark.asyncio
async def test_loader_dict_carries_data_entrega_prevista() -> None:
    """O dict devolvido pelo loader transporta a data-alvo REAL (o bug era
    o SELECT tê-la e o dict deixá-la cair)."""
    from src.plan.cpo.state_loaders import _load_open_orders_db

    sess = _RowsSession([dict(_ROW)])
    out = await _load_open_orders_db(sess, TENANT, scope="boats_only")

    assert len(out) == 1
    assert out[0]["data_entrega_prevista"] == "2026-07-15T00:00:00"


@pytest.mark.asyncio
async def test_loader_dict_due_none_when_absent() -> None:
    """Sem data no ERP → o campo viaja como None (nunca inventado)."""
    from src.plan.cpo.state_loaders import _load_open_orders_db

    row = dict(_ROW, data_entrega_prevista=None)
    out = await _load_open_orders_db(_RowsSession([row]), TENANT)
    assert out[0]["data_entrega_prevista"] is None


@pytest.mark.asyncio
async def test_loader_sql_nullifies_1900_sentinel() -> None:
    """A sentinela SQL-Server `1900-01-01` (zero-date) NÃO é uma data de
    entrega — o SQL anula-a antes de a expor como data_entrega_prevista.
    (Range real medido no mirror 2026-06-10: min=1900-01-01 → lixo.)"""
    from src.plan.cpo.state_loaders import _load_open_orders_db

    sess = _RowsSession([])
    await _load_open_orders_db(sess, TENANT)
    assert "1901-01-01" in sess.sql_text, (
        "o SELECT exterior tem de anular datas < 1901 (sentinela, não prazo)"
    )


# ─────────────────────────── 2. resolver → ops ───────────────────────────


def _state_with_route(model_id: str = "42366") -> FactoryState:
    state = FactoryState(tenant_id=uuid4())
    state.historical_routes_by_model = {
        model_id: [
            {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 1, "duration_hours": 4.32},
            {"fase_id": "2", "fase_nome": "Cura", "sequence": 2, "duration_hours": 17.38},
        ]
    }
    return state


def test_resolver_parses_due_date_into_every_op() -> None:
    """A data-alvo do loader chega a TODAS as ops como datetime — é o que o
    backward-scheduling (decoder_helpers) e a tardiness (decoder_kpis) leem."""
    resolver = RoutingResolver(_state_with_route())
    ops = resolver.resolve(
        {"of_id": "OF-1", "modelo_id": "42366",
         "data_entrega_prevista": "2026-07-15T00:00:00"}
    )

    assert len(ops) == 2
    assert all(op.due_date == datetime(2026, 7, 15) for op in ops)


def test_resolver_due_date_none_when_missing() -> None:
    """Ordem sem data-alvo → due_date=None em todas as ops (sem fabricar)."""
    resolver = RoutingResolver(_state_with_route())
    ops = resolver.resolve({"of_id": "OF-2", "modelo_id": "42366"})
    assert ops and all(op.due_date is None for op in ops)


def test_resolver_due_date_with_z_suffix_is_naive() -> None:
    """Ressalva do reviewer: um valor com 'Z' (ou offset) NÃO pode produzir um
    datetime aware — o domínio de planeamento é naive-consistente e
    `decoder_kpis` compara `due < horizon_start` (naive); aware rebentaria com
    TypeError. O parser normaliza para naive até à migração tz (F1.B)."""
    resolver = RoutingResolver(_state_with_route())
    ops = resolver.resolve(
        {"of_id": "OF-3", "modelo_id": "42366",
         "data_entrega_prevista": "2026-07-15T00:00:00Z"}
    )
    assert ops
    for op in ops:
        assert op.due_date == datetime(2026, 7, 15)
        assert op.due_date.tzinfo is None


# ─────────────────────────── 3. cpo_meta coverage ─────────────────────────


def test_due_date_coverage_meta_counts_orders_not_ops() -> None:
    """A cobertura conta ORDENS (não ops): 1 ordem com due + 1 sem = 50%."""
    from src.plan.cpo.scheduler_run import _due_date_coverage

    resolver = RoutingResolver(_state_with_route())
    ops = resolver.resolve(
        {"of_id": "OF-1", "modelo_id": "42366",
         "data_entrega_prevista": "2026-07-15T00:00:00"}
    ) + resolver.resolve({"of_id": "OF-2", "modelo_id": "42366"})

    cov = _due_date_coverage(ops)
    assert cov == {"orders_with_due": 1, "orders_total": 2, "pct": 50.0}


def test_due_date_coverage_meta_empty_is_honest() -> None:
    """Scope vazio → 0/0 com pct=0.0 (nunca divisão por zero nem invenção)."""
    from src.plan.cpo.scheduler_run import _due_date_coverage

    assert _due_date_coverage([]) == {
        "orders_with_due": 0, "orders_total": 0, "pct": 0.0,
    }
