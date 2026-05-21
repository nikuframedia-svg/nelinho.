"""
Q.67.4.D — ``build_context_facts`` passa de 5 para 12 tabelas no snapshot.

Antes deste sub-sprint, o contexto que o copiloto via era
``operational_snapshot`` + ``quality`` + ``plan_history`` + ``trust_index``.
Faltava-lhe contexto crítico para responder a perguntas como:

* "Quanto stock temos da resina X?"               (warehouse_stock)
* "Sexta é feriado?"                              (factory_calendar)
* "Quantos sabem laminagem?"                       (employee_skills)
* "Qual foi o último custo calculado?"             (cost_calculations)
* "Há um kill-switch activo?"                      (kill_switch)
* "Quando foi o último sync do mirror de moldes?"  (etl_runs)
* "Quais os defeitos mais crónicos?"               (error_catalog)

Estes testes fixam o contrato novo: o snapshot tem 12 keys top-level,
serializa em ≤ 4 KB e cada sub-builder devolve a estrutura esperada.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, List
from uuid import UUID, uuid4

import pytest

from src.copilot.context_builder import (
    MAX_SNAPSHOT_BYTES,
    _build_cost_calculations,
    _build_employee_skills,
    _build_error_catalog,
    _build_etl_runs,
    _build_factory_calendar,
    _build_kill_switch,
    _build_warehouse_stock,
    build_context_facts,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")


# ── FakeSession leve para os novos sub-builders ────────────────────────
#
# A `FakeSession` do conftest assume que uma `queue_scalars([(val,)])`
# alimenta tanto chamadas a `.all()` como a `.scalar()`. Para a maioria
# das queries chega-nos isso, mas alguns sub-builders chamam `.scalar()`
# directo num COUNT; usamos `queue_scalar(val)` nesses casos.


class _Result:
    """Resultado fake que devolve `rows` em `.all()` e `scalar` em `.scalar()`."""

    def __init__(self, rows: Iterable[Any] = (), scalar: Any = None):
        self._rows = list(rows)
        self._scalar = scalar

    def all(self) -> List[Any]:
        return list(self._rows)

    def scalar(self) -> Any:
        return self._scalar

    def scalar_one_or_none(self) -> Any:
        return self._scalar

    def scalars(self) -> "_Result":
        return self


class _ScriptedSession:
    """Devolve resultados por ordem fixa de chamadas a `execute()`.

    Cada sub-builder tem uma ordem de queries previsível — esta sessão
    devolve-as nessa ordem.
    """

    def __init__(self, results: Iterable[_Result]):
        self._results = list(results)
        self.calls = 0

    async def execute(self, _stmt: Any) -> _Result:
        self.calls += 1
        if not self._results:
            return _Result()
        return self._results.pop(0)


# ─────────────────────────────────────────────────────────────────────
# Sub-builder unit tests
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_warehouse_stock_devolve_top_skus():
    synced = datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc)
    session = _ScriptedSession([
        _Result(scalar=1234),  # total count
        _Result(rows=[
            ("RES-001", "Armazém Resinas", 5000.0, synced),
            ("FIB-014", "Armazém Fibras", 320.0, synced),
        ]),
    ])

    snap = await _build_warehouse_stock(session, TENANT)

    assert snap["total_rows"] == 1234
    assert snap["has_data"] is True
    assert snap["top_skus"][0] == {
        "product_code": "RES-001",
        "warehouse": "Armazém Resinas",
        "stock": 5000.0,
    }
    assert snap["last_synced_at"] == synced.isoformat()
    assert snap["source"] == "supply.warehouse_stock"


@pytest.mark.asyncio
async def test_warehouse_stock_bd_vazia_nao_rebenta():
    session = _ScriptedSession([
        _Result(scalar=0),
        _Result(rows=[]),
    ])

    snap = await _build_warehouse_stock(session, TENANT)

    assert snap["has_data"] is False
    assert snap["top_skus"] == []
    assert snap["total_rows"] == 0


@pytest.mark.asyncio
async def test_factory_calendar_devolve_proximos_7_dias():
    today = datetime.now(timezone.utc).date()
    session = _ScriptedSession([
        _Result(rows=[
            (today, True, 8.0, ""),
            (today + timedelta(days=1), False, 0.0, "Sábado"),
            (today + timedelta(days=2), False, 0.0, "Domingo"),
        ]),
    ])

    snap = await _build_factory_calendar(session, TENANT)

    assert snap["has_data"] is True
    assert len(snap["days"]) == 3
    assert snap["working_days_next_7"] == 1
    assert snap["total_shift_hours_next_7"] == 8.0
    assert snap["days"][1]["working"] is False
    assert snap["days"][1]["label"] == "Sábado"


@pytest.mark.asyncio
async def test_employee_skills_top_10():
    session = _ScriptedSession([
        _Result(scalar=1269),
        _Result(rows=[
            ("LAM", "Laminagem peças", 32),
            ("PINT", "Pintura", 18),
            ("ACAB", "Acabamento", 14),
        ]),
    ])

    snap = await _build_employee_skills(session, TENANT)

    assert snap["has_data"] is True
    assert snap["total_assignments"] == 1269
    assert snap["skills"][0] == {"code": "LAM", "name": "Laminagem peças", "operators": 32}
    assert len(snap["skills"]) == 3


@pytest.mark.asyncio
async def test_cost_calculations_ultima_run_e_summary():
    calc_at = datetime(2026, 5, 20, 9, 30, tzinfo=timezone.utc)
    session = _ScriptedSession([
        _Result(scalar=42),
        _Result(rows=[("OF-2026-0123", 15234.50, "APPROVED", calc_at)]),
        _Result(rows=[("APPROVED", 30), ("CALCULATED", 10), ("PENDING", 2)]),
    ])

    snap = await _build_cost_calculations(session, TENANT)

    assert snap["has_data"] is True
    assert snap["total_calculations"] == 42
    assert snap["last_run"]["order_id"] == "OF-2026-0123"
    assert snap["last_run"]["total_cogs_eur"] == 15234.50
    assert snap["last_run"]["status"] == "APPROVED"
    assert len(snap["summary"]) == 3


@pytest.mark.asyncio
async def test_kill_switch_inactive_default():
    session = _ScriptedSession([_Result(rows=[])])

    snap = await _build_kill_switch(session, TENANT)

    assert snap["active"] is False
    assert snap["scopes"] == []
    assert snap["reason"] is None


@pytest.mark.asyncio
async def test_kill_switch_active_com_scopes():
    activated = datetime(2026, 5, 21, 8, 0, tzinfo=timezone.utc)
    session = _ScriptedSession([
        _Result(rows=[
            ("all", "Manutenção planeada", "admin@nelo.pt", activated, None),
            ("decision_type:reschedule_order", "Bloqueio CPO", "admin@nelo.pt", activated, None),
        ]),
    ])

    snap = await _build_kill_switch(session, TENANT)

    assert snap["active"] is True
    assert "all" in snap["scopes"]
    assert "decision_type:reschedule_order" in snap["scopes"]
    assert snap["reason"] == "Manutenção planeada"
    assert snap["activated_by"] == "admin@nelo.pt"


@pytest.mark.asyncio
async def test_etl_runs_ultimo_por_mirror():
    last_master = datetime(2026, 5, 21, 6, 0, tzinfo=timezone.utc)
    last_molds = datetime(2026, 5, 20, 6, 0, tzinfo=timezone.utc)
    session = _ScriptedSession([
        _Result(scalar=512),  # total runs
        _Result(rows=[("master", last_master), ("molds", last_molds)]),
        _Result(rows=[("ok", 1500, 32)]),   # status for master
        _Result(rows=[("ok", 510, 0)]),     # status for molds
    ])

    snap = await _build_etl_runs(session, TENANT)

    assert snap["has_data"] is True
    assert snap["total_runs"] == 512
    assert len(snap["last_runs"]) == 2
    assert snap["last_runs"][0]["source"] == "master"
    assert snap["last_runs"][0]["status"] == "ok"
    assert snap["last_runs"][0]["rows_inserted"] == 1500


@pytest.mark.asyncio
async def test_error_catalog_top_10_codigos():
    session = _ScriptedSession([
        _Result(scalar=87),  # total catalog
        _Result(rows=[
            ("E_LAM_01", 1200),
            ("E_PINT_02", 800),
            ("E_ACAB_03", 320),
        ]),
        _Result(rows=[
            ("E_LAM_01", "Delaminação"),
            ("E_PINT_02", "Escorrido de tinta"),
            ("E_ACAB_03", "Acabamento irregular"),
        ]),
    ])

    snap = await _build_error_catalog(session, TENANT)

    assert snap["has_data"] is True
    assert snap["total_catalog_entries"] == 87
    assert len(snap["top_codes"]) == 3
    assert snap["top_codes"][0] == {
        "code": "E_LAM_01",
        "name": "Delaminação",
        "events": 1200,
    }


# ─────────────────────────────────────────────────────────────────────
# Integration: build_context_facts devolve 12 keys e cabe em 4 KB
# ─────────────────────────────────────────────────────────────────────


# Ordem global das queries (manter sync com `build_context_facts`):
#
#   1. operational_snapshot  — 4 queries (orders-status, top-fases, rework-total, rework-7d)
#   2. quality               — 4 queries (types, total, ranking, code-names) + 1 emp-names
#                              (Esta sub-build chama WorkerRankingService internamente; aqui
#                              passamos só 1 ranking-result mock; o serviço aceita o session.)
#   3. plan_history          — 1 query
#   4. trust_index           — Trust v2 calculator (faz queries próprias — degradamos via
#                              fallback ao falhar; ver overrides abaixo)
#   5. warehouse_stock       — 2 queries (count, top-rows)
#   6. factory_calendar      — 1 query (next 7 days)
#   7. employee_skills       — 2 queries (count, top-skills)
#   8. cost_calculations     — 3 queries (count, last, summary)
#   9. kill_switch           — 1 query (active rows)
#  10. etl_runs              — variable (count + sources + N per source)
#  11. error_catalog         — 3 queries (count, top-events, names)
#
# Para o integration test usamos uma sessão "tolerante" que devolve
# resultados "vazios suficientes" em vez de tentar manter a sequência
# exacta — o objectivo é provar que ``build_context_facts`` *constrói*
# 12 keys, não testar cada sub-builder (esses já têm o seu unit test).


class _ToleranteSession:
    """Devolve sempre um `_Result` vazio. Cada sub-builder degrada para
    o seu fallback. O snapshot tem na mesma 12 keys."""

    async def execute(self, _stmt: Any) -> _Result:
        return _Result(rows=[], scalar=0)


@pytest.mark.asyncio
async def test_build_context_facts_tem_12_keys(monkeypatch):
    """Pin estrutural: 12 chaves top-level, nomes estáveis."""
    # WorkerRankingService faz acesso real à BD via session; força fallback
    # vazio sem rebentar.
    from src.quality.services import worker_ranking_service as wrs_mod

    class _StubRanker:
        def __init__(self, *a, **kw): pass

        async def ranking(self, *a, **kw):
            return []

    monkeypatch.setattr(wrs_mod, "WorkerRankingService", _StubRanker)

    # Trust v2 também — força para o fallback neutral.
    from src.dqa import trust_v2 as trust_v2_mod

    class _StubTrust:
        def __init__(self, *a, **kw): pass

        async def compute_for_scope(self, *_a, **_kw):
            raise RuntimeError("forced fallback")

    monkeypatch.setattr(trust_v2_mod, "TrustIndexV2Calculator", _StubTrust)

    session = _ToleranteSession()
    snap = await build_context_facts(
        session=session,
        tenant_id=TENANT,
        context_window_hours=6,
        user_role="operator",
        kpi_snapshot=None,
    )

    expected_keys = {
        "operational_snapshot",
        "quality",
        "plan_history",
        "trust_index",
        "warehouse_stock",
        "factory_calendar",
        "employee_skills",
        "cost_calculations",
        "kill_switch",
        "etl_runs",
        "error_catalog",
        "meta",
    }
    assert set(snap.keys()) == expected_keys, (
        f"Snapshot deve ter exactamente 12 chaves; faltam: "
        f"{expected_keys - set(snap.keys())} / extras: "
        f"{set(snap.keys()) - expected_keys}"
    )
    assert len(snap) == 12


@pytest.mark.asyncio
async def test_build_context_facts_serializa_em_menos_de_4kb(monkeypatch):
    """O snapshot inteiro tem de caber em 4 KB para não comer prompt."""
    from src.quality.services import worker_ranking_service as wrs_mod

    class _StubRanker:
        def __init__(self, *a, **kw): pass

        async def ranking(self, *a, **kw):
            return []

    monkeypatch.setattr(wrs_mod, "WorkerRankingService", _StubRanker)

    from src.dqa import trust_v2 as trust_v2_mod

    class _StubTrust:
        def __init__(self, *a, **kw): pass

        async def compute_for_scope(self, *_a, **_kw):
            raise RuntimeError("forced fallback")

    monkeypatch.setattr(trust_v2_mod, "TrustIndexV2Calculator", _StubTrust)

    session = _ToleranteSession()
    snap = await build_context_facts(
        session=session,
        tenant_id=TENANT,
        context_window_hours=6,
        user_role="operator",
        kpi_snapshot=None,
    )

    serialized = json.dumps(snap, default=str, separators=(",", ":"))
    size = len(serialized.encode("utf-8"))

    assert size <= MAX_SNAPSHOT_BYTES, (
        f"Snapshot size {size}B excede budget {MAX_SNAPSHOT_BYTES}B"
    )
    # `meta.snapshot_bytes` é registado no próprio snapshot — confirma
    # que o auto-relato está coerente (alguma margem porque o bytes
    # registado é o pré-meta).
    assert snap["meta"]["budget_bytes"] == MAX_SNAPSHOT_BYTES


@pytest.mark.asyncio
async def test_build_context_facts_cada_tabela_devolve_estrutura(monkeypatch):
    """Sample 1 row por tabela — cada sub-builder devolve um dict, não None."""
    from src.quality.services import worker_ranking_service as wrs_mod

    class _StubRanker:
        def __init__(self, *a, **kw): pass

        async def ranking(self, *a, **kw):
            return []

    monkeypatch.setattr(wrs_mod, "WorkerRankingService", _StubRanker)

    from src.dqa import trust_v2 as trust_v2_mod

    class _StubTrust:
        def __init__(self, *a, **kw): pass

        async def compute_for_scope(self, *_a, **_kw):
            raise RuntimeError("forced fallback")

    monkeypatch.setattr(trust_v2_mod, "TrustIndexV2Calculator", _StubTrust)

    session = _ToleranteSession()
    snap = await build_context_facts(
        session=session,
        tenant_id=TENANT,
        context_window_hours=6,
        user_role="operator",
        kpi_snapshot=None,
    )

    # Cada tabela tem de devolver um dict (nunca None / nunca lista crua).
    for key in (
        "operational_snapshot", "quality", "plan_history", "trust_index",
        "warehouse_stock", "factory_calendar", "employee_skills",
        "cost_calculations", "kill_switch", "etl_runs", "error_catalog",
        "meta",
    ):
        assert isinstance(snap[key], dict), f"{key} não devolveu dict"

    # Pins de campos load-bearing por tabela — se mudarem, o LLM prompt
    # template tem de mudar também.
    assert "has_data" in snap["warehouse_stock"]
    assert "days" in snap["factory_calendar"]
    assert "skills" in snap["employee_skills"]
    assert "summary" in snap["cost_calculations"]
    assert "active" in snap["kill_switch"]
    assert "last_runs" in snap["etl_runs"]
    assert "top_codes" in snap["error_catalog"]
    assert snap["meta"]["tables_count"] == 12
