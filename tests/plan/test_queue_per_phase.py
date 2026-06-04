"""Q.160 — fila inter-fase: mediana REAL por fase (substitui o 5.2h global).

Trava quatro coisas:
  1. `FactoryState.queue_minutes_for` tem a hierarquia de fallback correcta
     (mediana da fase → mediana global → 5.2h default).
  2. O loader usa **MEDIANA** (`percentile_cont(0.5)`), NUNCA média, e calcula a
     gap entre fases consecutivas do MESMO barco (`LAG` + `OFFP_OF_ID`), per-fase
     de destino + global num só passe (`GROUPING SETS`).
  3. O decoder aplica a mediana POR FASE e mantém o axioma 6 — a cura (física) é
     o piso: `gap = max(fila, cura)`.
  4. `use_queue_time` off → fila 0 (estado one-piece-flow alvo) SEM quebrar a cura.

DAMP > DRY: cada teste lê como spec independente.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode as cpo_decode
from src.plan.cpo.state import (
    NELO_CURING_GAPS_SEED,
    FactoryState,
    _load_phase_queue_medians_db,
    normalize_phase_code,
)
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation

TENANT = UUID("11111111-1111-1111-1111-111111111111")
H_START = datetime(2026, 4, 20, 8, 0, 0)
H_END = H_START + timedelta(days=30)

_PHASES = ("LAMINAGEM", "CURA", "MONTAGEM", "PINTURA_ACABAMENTO")


# ─── helpers ─────────────────────────────────────────────────────────────────


def _state(curing: bool = False) -> FactoryState:
    s = FactoryState(tenant_id=TENANT)
    # 2 operadores aptos em cada fase usada → as ops agendam (não infeasible).
    s.skill_matrix = {p: {"W1", "W2"} for p in _PHASES}
    if curing:
        s.phase_transition_gaps = {
            (normalize_phase_code(frm), normalize_phase_code(to)): hours
            for frm, to, hours, _r, _n in NELO_CURING_GAPS_SEED
        }
    return s


def _op(order: str, seq: int, phase: str) -> SchedulingOperation:
    return SchedulingOperation(
        operation_id=f"{order}::{phase}",
        order_id=order,
        product_id="P1",
        sequence=seq,
        operation_code=phase,
        duration_minutes=30.0,
        machine_id="M1",
        phase_id=phase,
    )


def _gap_h(prev_phase: str, curr_phase: str, *, state: FactoryState, queue_on: bool) -> float:
    """Agenda prev→curr (mesma encomenda) e devolve curr.start − prev.end (horas)."""
    ops = [_op("O1", 1, prev_phase), _op("O1", 2, curr_phase)]
    machines = [SchedulingMachine(machine_id="M1", name="M1")]
    chromo = Chromosome.identity(len(ops))
    result = cpo_decode(
        chromo, ops, machines, state, H_START, H_END,
        queue_time_minutes=(5.2 * 60.0) if queue_on else None,
    )
    out = {o["operation_id"]: o for o in result["operations"]}
    prev_end = datetime.fromisoformat(out[f"O1::{prev_phase}"]["end_time"])
    curr_start = datetime.fromisoformat(out[f"O1::{curr_phase}"]["start_time"])
    return (curr_start - prev_end).total_seconds() / 3600.0


# ─── 1. queue_minutes_for: hierarquia de fallback ────────────────────────────


def test_queue_minutes_for_prefers_phase_then_global_then_default() -> None:
    s = _state()
    s.queue_median_by_phase = {"MONTAGEM": 8.0}
    s.queue_global_median_h = 3.0
    assert s.queue_minutes_for("MONTAGEM") == pytest.approx(8.0 * 60.0)  # mediana da fase
    assert s.queue_minutes_for("OUTRA") == pytest.approx(3.0 * 60.0)     # → global
    s.queue_global_median_h = None
    assert s.queue_minutes_for("OUTRA") == pytest.approx(5.2 * 60.0)     # → default seed
    s.queue_global_median_h = 3.0
    assert s.queue_minutes_for(None) == pytest.approx(3.0 * 60.0)        # None → global


# ─── 2. loader: MEDIANA, nunca média + estrutura ─────────────────────────────


class _CaptureResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def mappings(self):  # noqa: ANN201
        return self

    def all(self) -> list:
        return self._rows


class _CaptureSession:
    """Captura o SQL gerado por `_load_phase_queue_medians_db` (sem BD)."""

    def __init__(self, rows: list | None = None) -> None:
        self.sql_text = ""
        self._rows = rows or []

    async def execute(self, stmt, params=None):  # noqa: ANN001, ANN201
        self.sql_text = str(stmt)
        return _CaptureResult(self._rows)


@pytest.mark.asyncio
async def test_queue_loader_uses_median_not_mean_per_phase() -> None:
    sess = _CaptureSession()
    await _load_phase_queue_medians_db(sess, TENANT)
    sql = sess.sql_text
    assert "percentile_cont(0.5)" in sql, "tem de usar MEDIANA"
    assert "avg(" not in sql.lower(), "NUNCA média — a cauda assimétrica (p90~69h) enviesava"
    assert "LAG(" in sql, "a fila é a gap entre fases consecutivas do MESMO barco"
    assert "OFFP_OF_ID" in sql, "particiona a gap por barco"
    assert "GROUPING SETS" in sql, "per-fase + global num só passe"


@pytest.mark.asyncio
async def test_queue_loader_parses_phase_and_global_rows() -> None:
    rows = [
        {"fase_id": "18", "median_h": 8.0, "n_obs": 120},
        {"fase_id": "10", "median_h": 2.0, "n_obs": 90},
        {"fase_id": None, "median_h": 5.2, "n_obs": 9000},  # grouping () → mediana global
    ]
    by_phase, global_h = await _load_phase_queue_medians_db(_CaptureSession(rows), TENANT)
    assert by_phase == {"18": 8.0, "10": 2.0}
    assert global_h == pytest.approx(5.2)


@pytest.mark.asyncio
async def test_queue_loader_best_effort_session_none() -> None:
    by_phase, global_h = await _load_phase_queue_medians_db(None, TENANT)
    assert by_phase == {}
    assert global_h is None


# ─── 3. decoder: aplica POR FASE + mantém max(fila, cura) ────────────────────


def test_decoder_applies_per_phase_queue_not_global_constant() -> None:
    s = _state()
    s.queue_median_by_phase = {"MONTAGEM": 2.0}  # 2h, não o 5.2h global
    gap = _gap_h("LAMINAGEM", "MONTAGEM", state=s, queue_on=True)
    assert gap == pytest.approx(2.0, abs=1e-3), "usa a mediana DA FASE, não o 5.2h hardcoded"


def test_decoder_curing_is_the_floor_max_queue_cura() -> None:
    s = _state(curing=True)  # LAMINAGEM→CURA = 15h (física)
    s.queue_median_by_phase = {"CURA": 2.0}  # fila 2h < cura 15h
    gap = _gap_h("LAMINAGEM", "CURA", state=s, queue_on=True)
    assert gap == pytest.approx(15.0, abs=1e-3), "cura (física) é o piso: max(fila, cura)"


def test_decoder_queue_off_is_zero_one_piece_flow() -> None:
    s = _state()
    s.queue_median_by_phase = {"MONTAGEM": 9.0}  # ignorado quando off
    gap = _gap_h("LAMINAGEM", "MONTAGEM", state=s, queue_on=False)
    assert gap == pytest.approx(0.0, abs=1e-3), "use_queue_time off → fila 0 (fluxo unitário)"


def test_decoder_queue_off_still_enforces_curing() -> None:
    s = _state(curing=True)
    s.queue_median_by_phase = {"CURA": 0.0}
    gap = _gap_h("LAMINAGEM", "CURA", state=s, queue_on=False)
    assert gap == pytest.approx(15.0, abs=1e-3), "fila off NÃO quebra a cura"


# ─── 4. property: gap == max(fila_fase, cura) com a fila ON ──────────────────


@settings(
    deadline=None, max_examples=50,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
@given(
    queue_h=st.floats(min_value=0.0, max_value=40.0),
    cura_h=st.floats(min_value=0.0, max_value=40.0),
)
def test_property_gap_is_max_queue_cura(queue_h: float, cura_h: float) -> None:
    s = FactoryState(tenant_id=TENANT)
    s.skill_matrix = {p: {"W1", "W2"} for p in _PHASES}
    s.phase_transition_gaps = {
        (normalize_phase_code("LAMINAGEM"), normalize_phase_code("MONTAGEM")): cura_h
    }
    s.queue_median_by_phase = {"MONTAGEM": queue_h}
    gap = _gap_h("LAMINAGEM", "MONTAGEM", state=s, queue_on=True)
    expected = max(queue_h, cura_h)
    assert gap + 1e-3 >= expected
    assert gap <= expected + 1e-3
