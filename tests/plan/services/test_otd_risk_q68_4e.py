"""Q.68.4.E — `src/plan/services/otd_risk_service.py` foi medido a **0%**
no inventário do Q.67.3.D: 52 statements, zero a serem exercitados. O
serviço alimenta o painel "que kayaks vão atrasar?" — sem testes, qualquer
refactor à pipeline ML faz silenciar o sinal sem ninguém notar.

Estes testes cobrem:

* o classificador de bandas (`_risk_band`) — anchors em 0.60 / 0.30
  determinam a UI badge (alto/medio/baixo).
* a degradação honesta quando não há predictor activo — retorna
  `model_available=False` + lista vazia (NUNCA inventa um número).
* o feature-row builder dentro de `otd_risk()` — `slack_days` corretos,
  agregados por `of_id`, `phase_error_rate_mean` arrancado a 0.0.
* a degradação honesta quando há orders mas sem `transport_date` (excluídas
  pelo SQL) e/ou predictor crasha em runtime.
* a ordenação descendente por `late_probability` + `top_n` corta a lista.

Tests usam `FakeSession` do conftest (queue-based) + monkeypatch ao
`ensure_otd_risk_model` / `load_active_otd_risk_predictor` para evitar
treinar modelos reais.
"""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from src.plan.services import otd_risk_service as ors_mod
from src.plan.services.otd_risk_service import (
    RISK_BANDS,
    OTDRiskService,
    _risk_band,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


# ─── Helpers ──────────────────────────────────────────────────────────────


class _OrderRow(dict):
    """Mimics SQLAlchemy `Row.mappings()` items — supports `row["k"]`."""


def _patch_train_and_loader(
    monkeypatch: pytest.MonkeyPatch,
    *,
    predictor,
) -> None:
    async def _noop_ensure(*_a, **_kw) -> None:
        return None

    async def _load(*_a, **_kw):
        return predictor

    monkeypatch.setattr(ors_mod, "ensure_otd_risk_model", _noop_ensure)
    monkeypatch.setattr(
        ors_mod, "load_active_otd_risk_predictor", _load,
    )


class _FakeMappingsResult:
    """SQLAlchemy `execute().mappings().all()` stand-in."""

    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self) -> "_FakeMappingsResult":
        return self

    def all(self) -> list[dict]:
        return list(self._rows)


class _ScriptedSession:
    """Session scriptada: a primeira `execute()` devolve as orders (mappings),
    a segunda devolve os aggregates (rows tuples)."""

    def __init__(
        self,
        *,
        orders: list[dict],
        aggregates_rows: list[tuple],
    ) -> None:
        # OTDRiskService chama `_order_phase_aggregates()` ANTES da query
        # de orders? Não — ver o código: orders primeiro, agregados depois.
        self._results = [
            _FakeMappingsResult(orders),
            SimpleNamespace(all=lambda rows=aggregates_rows: list(rows)),
        ]

    async def execute(self, _stmt, *_args, **_kwargs) -> object:
        if not self._results:
            raise AssertionError("Unexpected extra session.execute() call")
        return self._results.pop(0)


# ─── _risk_band ───────────────────────────────────────────────────────────


def test_risk_bands_are_three_canonical_labels():
    """A UI faz badge por banda — qualquer drift no número/ordem das bandas
    parte o componente de Painel sem aviso."""
    labels = {label for _, label in RISK_BANDS}
    assert labels == {"alto", "medio", "baixo"}
    # Thresholds devem ser decrescentes (0.60, 0.30, 0.0) para que o
    # walk em `_risk_band` apanhe o limiar mais alto primeiro.
    thresholds = [t for t, _ in RISK_BANDS]
    assert thresholds == sorted(thresholds, reverse=True)


def test_risk_band_alto_at_threshold_and_above():
    assert _risk_band(0.60) == "alto"
    assert _risk_band(0.75) == "alto"
    assert _risk_band(1.0) == "alto"


def test_risk_band_medio_window():
    assert _risk_band(0.30) == "medio"
    assert _risk_band(0.45) == "medio"
    assert _risk_band(0.59) == "medio"


def test_risk_band_baixo_below_30():
    assert _risk_band(0.0) == "baixo"
    assert _risk_band(0.15) == "baixo"
    assert _risk_band(0.29) == "baixo"


# ─── otd_risk() — degradation paths ───────────────────────────────────────


@pytest.mark.asyncio
async def test_otd_risk_without_predictor_returns_honest_empty(
    monkeypatch: pytest.MonkeyPatch,
):
    """Sem predictor activo, NUNCA inventar probabilidades — devolver
    `model_available=False` + razão em PT-PT + lista vazia."""
    _patch_train_and_loader(monkeypatch, predictor=None)
    # Nenhuma query deveria correr se predictor é None — usar um session
    # que falha ao primeiro execute() seria draconiano (a função pode
    # alterar ordem), mas o `_ScriptedSession` aqui não é usado.
    svc = OTDRiskService(session=_ScriptedSession(orders=[], aggregates_rows=[]), tenant_id=TENANT)
    out = await svc.otd_risk()
    assert out["model_available"] is False
    assert out["orders"] == []
    assert "histórico" in out["reason"] or "modelo" in out["reason"]


@pytest.mark.asyncio
async def test_otd_risk_with_predictor_but_no_open_orders(
    monkeypatch: pytest.MonkeyPatch,
):
    """Predictor activo + zero orders abertas → `model_available=True` +
    lista vazia (sem `reason`, sem inventar nada)."""

    def _predictor(rows):
        return [0.5] * len(rows)

    _patch_train_and_loader(monkeypatch, predictor=_predictor)

    class _OnlyOrdersSession:
        async def execute(self, _stmt, *_a, **_kw):
            return _FakeMappingsResult([])

    svc = OTDRiskService(session=_OnlyOrdersSession(), tenant_id=TENANT)
    out = await svc.otd_risk()
    assert out == {"model_available": True, "orders": []}


@pytest.mark.asyncio
async def test_otd_risk_predictor_runtime_failure_degrades(
    monkeypatch: pytest.MonkeyPatch,
):
    """Se o `predictor(...)` rebenta, devolver degradação honesta — não
    propagar exceção para o painel (Plan v4 §11)."""

    def _broken(rows):
        raise RuntimeError("model crashed mid-batch")

    _patch_train_and_loader(monkeypatch, predictor=_broken)
    today = date.today()
    sess = _ScriptedSession(
        orders=[
            {
                "legacy_id": 7001,
                "product_name": "K1 Vanquish",
                "product_type": "K1",
                "current_phase_id": "F-LAM",
                "current_phase_name": "Laminagem",
                "transport_date": today + timedelta(days=5),
            }
        ],
        aggregates_rows=[("7001", 5, 12.0)],
    )
    svc = OTDRiskService(session=sess, tenant_id=TENANT)
    out = await svc.otd_risk()
    assert out["model_available"] is False
    assert out["orders"] == []
    assert "Falha" in out["reason"] or "modelo" in out["reason"]


# ─── otd_risk() — happy paths ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_otd_risk_happy_path_ranks_orders_descending(
    monkeypatch: pytest.MonkeyPatch,
):
    """Predictor devolve [0.8, 0.2, 0.5]; resultado vem ordenado [0.8, 0.5, 0.2]
    e cada item tem o `risk_band` correcto (alto/medio/baixo)."""
    today = date.today()

    captured: dict = {}

    def _predictor(rows):
        captured["rows"] = rows
        # Mantém ordem dos rows recebidos.
        return [0.8, 0.2, 0.5]

    _patch_train_and_loader(monkeypatch, predictor=_predictor)

    sess = _ScriptedSession(
        orders=[
            {
                "legacy_id": 100,
                "product_name": "K1",
                "product_type": "K1",
                "current_phase_id": "F-LAM",
                "current_phase_name": "Laminagem",
                "transport_date": today + timedelta(days=2),
            },
            {
                "legacy_id": 101,
                "product_name": "K2",
                "product_type": "K2",
                "current_phase_id": "F-CURA",
                "current_phase_name": "Cura",
                "transport_date": today + timedelta(days=30),
            },
            {
                "legacy_id": 102,
                "product_name": "K3",
                "product_type": "K3",
                "current_phase_id": "F-MONT",
                "current_phase_name": "Montagem",
                "transport_date": today + timedelta(days=10),
            },
        ],
        aggregates_rows=[
            ("100", 4, 10.0),
            ("101", 6, 22.0),
            # "102" sem agregados — deve cair para defaults.
        ],
    )
    svc = OTDRiskService(session=sess, tenant_id=TENANT)
    out = await svc.otd_risk()
    assert out["model_available"] is True
    assert out["total_orders"] == 3
    # Bandas correctas + ordem descendente.
    probs = [o["late_probability"] for o in out["orders"]]
    assert probs == sorted(probs, reverse=True)
    assert out["orders"][0]["risk_band"] == "alto"
    assert out["orders"][1]["risk_band"] == "medio"
    assert out["orders"][2]["risk_band"] == "baixo"
    # high_risk_count = nº de alto.
    assert out["high_risk_count"] == 1

    # Feature row do order 102 (sem agregados) deve ter n_phases=0.
    rows_by_modelo = {r["modelo_id"]: r for r in captured["rows"]}
    assert rows_by_modelo["K3"]["n_phases"] == 0
    assert rows_by_modelo["K3"]["total_planned_hours"] == 0.0
    # phase_error_rate_mean fixo a 0.0 (sem features de operador ainda).
    assert all(r["phase_error_rate_mean"] == 0.0 for r in captured["rows"])


@pytest.mark.asyncio
async def test_otd_risk_top_n_truncates(
    monkeypatch: pytest.MonkeyPatch,
):
    """`top_n=1` devolve apenas o top mas `total_orders` mantém o N real
    (UI mostra "1 de N kayaks de risco")."""
    today = date.today()
    _patch_train_and_loader(monkeypatch, predictor=lambda rows: [0.7, 0.6])
    sess = _ScriptedSession(
        orders=[
            {
                "legacy_id": 1,
                "product_name": "A",
                "product_type": "K1",
                "current_phase_id": None,
                "current_phase_name": None,
                "transport_date": today + timedelta(days=4),
            },
            {
                "legacy_id": 2,
                "product_name": "B",
                "product_type": "K2",
                "current_phase_id": None,
                "current_phase_name": None,
                "transport_date": today + timedelta(days=4),
            },
        ],
        aggregates_rows=[],
    )
    svc = OTDRiskService(session=sess, tenant_id=TENANT)
    out = await svc.otd_risk(top_n=1)
    assert out["total_orders"] == 2
    assert len(out["orders"]) == 1


@pytest.mark.asyncio
async def test_otd_risk_slack_days_uses_today_minus_transport(
    monkeypatch: pytest.MonkeyPatch,
):
    """`slack_days` deve ser `(transport_date - today).days`. Anchored em
    +7 dias para garantir que o sinal de "risco" e a ordem ↔ feature row
    está correctos."""
    today = date.today()
    captured: dict = {}

    def _predictor(rows):
        captured["rows"] = rows
        return [0.4] * len(rows)

    _patch_train_and_loader(monkeypatch, predictor=_predictor)
    sess = _ScriptedSession(
        orders=[
            {
                "legacy_id": 555,
                "product_name": "X",
                "product_type": "K1",
                "current_phase_id": None,
                "current_phase_name": None,
                "transport_date": today + timedelta(days=7),
            }
        ],
        aggregates_rows=[("555", 3, 5.0)],
    )
    svc = OTDRiskService(session=sess, tenant_id=TENANT)
    await svc.otd_risk()
    assert captured["rows"][0]["slack_days"] == 7.0


@pytest.mark.asyncio
async def test_otd_risk_handles_missing_transport_date_gracefully(
    monkeypatch: pytest.MonkeyPatch,
):
    """Se `transport_date` for None (o SQL filtra, mas o test cobre a
    safety-net try/except no builder) → `slack_days=0.0` e item.transport_date
    serializa como None."""
    captured: dict = {}

    def _predictor(rows):
        captured["rows"] = rows
        return [0.1]

    _patch_train_and_loader(monkeypatch, predictor=_predictor)
    sess = _ScriptedSession(
        orders=[
            {
                "legacy_id": 999,
                "product_name": "Z",
                "product_type": "K0",
                "current_phase_id": None,
                "current_phase_name": None,
                "transport_date": None,
            }
        ],
        aggregates_rows=[("999", 2, 1.0)],
    )
    svc = OTDRiskService(session=sess, tenant_id=TENANT)
    out = await svc.otd_risk()
    assert captured["rows"][0]["slack_days"] == 0.0
    assert out["orders"][0]["transport_date"] is None
