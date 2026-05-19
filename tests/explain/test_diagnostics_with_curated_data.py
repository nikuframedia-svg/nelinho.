"""Q.36.D — pipeline causal sobre dados curados do `curated_loader`.

Cenário desenhado: um molde com taxa de erro recente ≥1.5× a histórica
e ≥50% dos erros mold-typed. As linhas ERP passam pelas funções puras de
transformação do `curated_loader` (Q.36.C) e o `ErroTreeDetector`
investiga contra elas — devolvendo `root_cause` não-None do tipo
`mold_degradation`.

Sem Postgres: a `DiagnosticsRepository` é substituída por uma fake que
serve directamente das linhas curadas produzidas pelas funções puras. O
que se prova é que os dicts que o loader gera carregam o que o detector
precisa — molde, datas, e `erro_tipo` com keyword mold-typed. O teste de
idempotência contra Postgres real corre no passo de integração.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from src.adapters.nelo.schemas import ChecklistRow, OperationRow
from src.explain.diagnostics.erro_tree import ErroTreeDetector, MoldDetector
from src.explain.diagnostics.types import TriggerType
from src.factory_data_product.etl.curated_loader import (
    checklist_to_quality_events,
    operations_to_order_phases,
)

_TENANT = UUID("00000000-0000-0000-0000-000000000001")
_INGESTION = uuid4()
_MOLD = "501"  # o molde degradado do cenário


# ───────────────────────────────────────────────────────────────────────────
# Construção do cenário: linhas ERP → curated via as funções puras Q.36.C
# ───────────────────────────────────────────────────────────────────────────


def _op(operation_id: int, started: datetime, *, mold: str | None) -> OperationRow:
    return OperationRow(
        operation_id=operation_id, work_order_id=6000 + operation_id,
        phase_id=10, phase_name="Laminagem",
        start_at=started, end_at=started + timedelta(hours=4),
        expected_at=None, standard_time_hours=4.0, temperature=20.0, humidity=50.0,
        is_return=False, severe_return=False, product_id=900,
        operation_mold_id=int(mold) if mold else None, mold_work_order_id=None,
    )


def _chk(checklist_id: int, detected: datetime, *, mold: str, description: str) -> ChecklistRow:
    return ChecklistRow(
        checklist_id=checklist_id, work_order_id=6000 + checklist_id,
        operation_id=checklist_id, phase_id=10, phase_name="Laminagem",
        description=description, description_en=None, severity=2,
        mold_repair=True, blame_chefe=False, blame_operation_id=None,
        resolved=False, state=1, verified_at=detected, updated_at=None,
        detected_at=detected, operation_mold_id=int(mold),
    )


def _build_curated_scenario() -> tuple[list[dict], list[dict]]:
    """Molde 501: na janela recente (últimos 7 dias) tem taxa de erro
    muito acima da histórica e os erros são todos mold-typed.

    - recente: 20 fases, 12 erros → 60% (≥ 15% piso, ≥ 1.5× histórico)
    - histórico (7..42 dias atrás): 60 fases, 6 erros → 10%
    Todos os erros recentes têm descrição mold-typed ("interior enrugado").
    """
    today = date.today()
    operations: list[OperationRow] = []
    incidents: list[ChecklistRow] = []
    op_id = 0
    chk_id = 0

    # Janela recente — molde 501.
    recent_day = datetime.combine(today - timedelta(days=3), datetime.min.time())
    for _ in range(20):
        op_id += 1
        operations.append(_op(op_id, recent_day, mold=_MOLD))
    for _ in range(12):
        chk_id += 1
        incidents.append(_chk(
            chk_id, recent_day, mold=_MOLD, description="Interior enrugado",
        ))

    # Janela histórica — molde 501, taxa baixa.
    hist_day = datetime.combine(today - timedelta(days=25), datetime.min.time())
    for _ in range(60):
        op_id += 1
        operations.append(_op(op_id, hist_day, mold=_MOLD))
    for _ in range(6):
        chk_id += 1
        incidents.append(_chk(
            chk_id, hist_day, mold=_MOLD, description="Interior enrugado",
        ))

    order_phase_rows = operations_to_order_phases(operations, _INGESTION)
    quality_rows = checklist_to_quality_events(incidents, _INGESTION)
    return order_phase_rows, quality_rows


# ───────────────────────────────────────────────────────────────────────────
# Fake repo — serve directamente das linhas curadas (sem Postgres)
# ───────────────────────────────────────────────────────────────────────────


class _CuratedBackedRepo:
    """`DiagnosticsRepository` mínima que consulta as linhas curadas em
    Python — a mesma semântica de janela do repo real, sem SQL."""

    def __init__(self, order_phase_rows: list[dict], quality_rows: list[dict]) -> None:
        self._phases = order_phase_rows
        self._quality = quality_rows

    async def molds_active_during(self, start: date, end: date) -> list[str]:
        return sorted({
            r["molde_id"] for r in self._phases
            if r["molde_id"] and r["data_inicio"]
            and start <= r["data_inicio"] < end
        })

    async def mold_phase_count(self, mold_id: str, start: date, end: date) -> int:
        return sum(
            1 for r in self._phases
            if r["molde_id"] == mold_id and r["data_inicio"]
            and start <= r["data_inicio"] < end
        )

    async def mold_error_count(self, mold_id: str, start: date, end: date) -> int:
        return sum(
            1 for r in self._quality
            if r["molde_id"] == mold_id and r["data_evento"]
            and start <= r["data_evento"] < end
        )

    async def mold_error_types(self, mold_id: str, start: date, end: date) -> Counter:
        return Counter(
            r["erro_tipo"] for r in self._quality
            if r["molde_id"] == mold_id and r["data_evento"]
            and start <= r["data_evento"] < end
        )

    # Helpers que o WorkerDetector / OverloadDetector chamam — sem dados,
    # para a cascata cair limpo se o molde não disparar.
    async def phase_error_rate(self, *a, **kw) -> float:
        return 0.0

    async def current_wip(self) -> int:
        return 0

    async def avg_wip_during(self, *a, **kw) -> float:
        return 0.0


def _make_orchestrator(repo) -> ErroTreeDetector:
    from src.explain.diagnostics.erro_tree import OverloadDetector, WorkerDetector
    detector = ErroTreeDetector.__new__(ErroTreeDetector)
    detector.session = None
    detector.tenant_id = _TENANT
    detector._repo = repo
    detector._detectors = [
        MoldDetector(repo),
        WorkerDetector(repo),
        OverloadDetector(repo),
    ]
    return detector


def _patch_persist(monkeypatch) -> None:
    import src.shared.decorators as decorators

    async def _noop(*a, **kw):
        return None

    monkeypatch.setattr(decorators, "_persist_firing", _noop)


# ───────────────────────────────────────────────────────────────────────────
# Testes
# ───────────────────────────────────────────────────────────────────────────


def test_curated_scenario_produces_mold_typed_erro_tipo():
    """As linhas de quality_event do loader carregam keyword mold-typed —
    é disso que o MoldDetector depende para contar os erros de molde."""
    _, quality_rows = _build_curated_scenario()
    recent = [r for r in quality_rows if r["molde_id"] == _MOLD]
    assert recent, "cenário tem de produzir quality events"
    assert all("interior enrugado" in r["erro_tipo"].lower() for r in recent)


def test_curated_scenario_keys_are_consistent():
    """order_phase e quality_event partilham o (of_id, fase_id) e o molde."""
    order_phase_rows, quality_rows = _build_curated_scenario()
    op_keys = {(r["of_id"], r["fase_id"]) for r in order_phase_rows}
    q_keys = {(r["of_id"], r["fase_id"]) for r in quality_rows}
    assert q_keys <= op_keys  # cada quality event tem o seu order_phase


@pytest.mark.asyncio
async def test_mold_detector_trips_on_curated_scenario():
    """O MoldDetector dispara para o molde degradado do cenário."""
    order_phase_rows, quality_rows = _build_curated_scenario()
    repo = _CuratedBackedRepo(order_phase_rows, quality_rows)
    det = MoldDetector(repo)
    h = await det.check(
        trigger=TriggerType.QUALITY_DROP, period_days=7, phase_id=None,
    )
    assert h is not None
    assert h.type == "mold_degradation"
    assert h.entity == _MOLD


@pytest.mark.asyncio
async def test_investigate_returns_mold_root_cause(monkeypatch):
    """O cenário desenhado → ErroTreeDetector.investigate() devolve um
    root_cause não-None do tipo mold_degradation."""
    _patch_persist(monkeypatch)
    order_phase_rows, quality_rows = _build_curated_scenario()
    repo = _CuratedBackedRepo(order_phase_rows, quality_rows)
    detector = _make_orchestrator(repo)

    result = await detector.investigate(
        trigger=TriggerType.QUALITY_DROP, period_days=7,
    )

    assert result.root_cause is not None, "esperava causa raiz, não 'sem causa'"
    assert result.root_cause.type == "mold_degradation"
    assert result.root_cause.entity == _MOLD
    assert result.root_cause.confidence >= 0.7
    chain_text = " ".join(result.chain)
    assert "Molde" in chain_text
    assert "Manutenção" in result.recommendation["action"]
