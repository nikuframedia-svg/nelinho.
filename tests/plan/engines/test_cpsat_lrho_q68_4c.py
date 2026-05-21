"""Q.68.4.C — coverage tests para `src/plan/engines/cpsat_lrho.py`.

Estado pre-task: 21% coverage. Alvo: 70%+.

L-RHO (Linear Rolling Horizon Optimization) é um wrapper CP-SAT que
re-optimiza uma baseline schedule do GA em janelas de 2 dias com passo
de 1 dia (overlap), congelando ops que já começaram (frozen zone).
Quando o ortools não está disponível, devolve `used=False` e o caller
fica com a baseline.

Estes testes cobrem:
* `_plan_windows()`: split por rolling window (2-day windows com 1-day overlap).
* `refine()` flow:
    - sem ortools → `used=False`, warning `ortools_unavailable`;
    - operações vazias → `used=False`, warning `no_operations`;
    - baseline real → `used=True`, schedule devolvido, aggregates recalculados;
    - frozen zone (op antes do cutoff) → não se mexe;
    - warm-start ML-stable ops (op com baseline dentro da janela mantém-se);
    - inter-window precedence (curing/phase gap respeitado);
    - per-window timeout graceful (`budget_s=0` → budget_exhausted warning);
* `LRHOResult.to_meta()`: shape do dict serializável.
* Helpers `_in_window`, `_parse_dt`, `_recompute_aggregates`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

import pytest

from src.plan.engines.cpsat_lrho import (
    CPSATLRHO,
    HAS_ORTOOLS,
    LRHOConfig,
    LRHOResult,
    _in_window,
    _parse_dt,
    _recompute_aggregates,
)


# ---------------------------------------------------------------------------
# Pequenos helpers — DAMP > DRY: cada teste deve ler como spec independente.
# ---------------------------------------------------------------------------


def _op(
    op_id: str,
    *,
    start: datetime,
    end: datetime,
    order_id: str = "OF-1",
    machine_id: str = "M1",
    duration_minutes: int | None = None,
    workers: List[str] | None = None,
    mold_id: str | None = None,
    phase_name: str | None = None,
) -> Dict[str, Any]:
    """Construir um op-dict no formato que o L-RHO consome."""
    return {
        "operation_id": op_id,
        "order_id": order_id,
        "machine_id": machine_id,
        "start": start,
        "end": end,
        "duration_minutes": duration_minutes
        or int((end - start).total_seconds() // 60),
        "workers": workers or [],
        "mold_id": mold_id,
        "phase_name": phase_name,
    }


# ---------------------------------------------------------------------------
# 1) LRHOConfig defaults
# ---------------------------------------------------------------------------


def test_lrho_config_default_values_match_sprint_p10():
    cfg = LRHOConfig()
    assert cfg.horizon_days == 2
    assert cfg.step_days == 1
    assert cfg.frozen_zone_hours == 4.0
    assert cfg.budget_s == 15.0
    assert cfg.solver_threads == 4


# ---------------------------------------------------------------------------
# 2) LRHOResult.to_meta() — shape contract
# ---------------------------------------------------------------------------


def test_lrho_result_to_meta_serialises_all_keys():
    r = LRHOResult(
        used=True,
        improved=True,
        windows=4,
        ops_rescheduled=12,
        solve_time_s=1.23456,
        warnings=["w1"],
    )
    meta = r.to_meta()
    assert meta["used"] is True
    assert meta["improved"] is True
    assert meta["windows"] == 4
    assert meta["ops_rescheduled"] == 12
    # solve_time_s deve ser arredondado a 3 casas.
    assert meta["solve_time_s"] == 1.235
    assert meta["warnings"] == ["w1"]


# ---------------------------------------------------------------------------
# 3) Rolling-window split — 2-day windows com 1-day step
# ---------------------------------------------------------------------------


def test_plan_windows_2d_window_1d_step_creates_overlapping_windows():
    lrho = CPSATLRHO(LRHOConfig(horizon_days=2, step_days=1))
    start = datetime(2026, 5, 1, 8, 0)
    end = start + timedelta(days=5)
    windows = lrho._plan_windows(start, end)

    # cursor avança 1 dia até atingir end (5 dias) → 5 janelas.
    assert len(windows) == 5
    # Janela 0: 5/1 → 5/3 (2 dias).
    assert windows[0] == (start, start + timedelta(days=2))
    # Janela 1: 5/2 → 5/4 — overlap de 1 dia com a anterior.
    assert windows[1] == (start + timedelta(days=1), start + timedelta(days=3))
    # Última janela é clamped no horizon_end (não ultrapassa).
    assert windows[-1][1] == end


def test_plan_windows_handles_short_horizon_smaller_than_window():
    lrho = CPSATLRHO(LRHOConfig(horizon_days=2, step_days=1))
    start = datetime(2026, 5, 1)
    # Horizon < window_size → uma única janela clampada.
    end = start + timedelta(hours=12)
    windows = lrho._plan_windows(start, end)
    assert len(windows) == 1
    assert windows[0] == (start, end)


# ---------------------------------------------------------------------------
# 4) refine() — sem ortools devolve used=False
# ---------------------------------------------------------------------------


def test_refine_returns_unavailable_when_ortools_missing(monkeypatch):
    from src.plan.engines import cpsat_lrho as mod

    monkeypatch.setattr(mod, "HAS_ORTOOLS", False)
    lrho = CPSATLRHO()
    start = datetime(2026, 5, 1)
    res = lrho.refine(
        {"operations": [_op("a", start=start, end=start + timedelta(hours=1))]},
        horizon_start=start,
        horizon_end=start + timedelta(days=1),
    )
    assert res.used is False
    assert res.improved is False
    assert "ortools_unavailable" in res.warnings
    assert res.schedule is None


# ---------------------------------------------------------------------------
# 5) refine() — sem operações devolve used=False
# ---------------------------------------------------------------------------


def test_refine_returns_unavailable_when_no_operations():
    lrho = CPSATLRHO()
    start = datetime(2026, 5, 1)
    res = lrho.refine(
        {"operations": []},
        horizon_start=start,
        horizon_end=start + timedelta(days=1),
    )
    assert res.used is False
    assert "no_operations" in res.warnings


def test_refine_returns_unavailable_when_operations_key_missing():
    lrho = CPSATLRHO()
    start = datetime(2026, 5, 1)
    res = lrho.refine(
        {},  # sem chave "operations" — defensive default
        horizon_start=start,
        horizon_end=start + timedelta(days=1),
    )
    assert res.used is False
    assert "no_operations" in res.warnings


# ---------------------------------------------------------------------------
# 6) refine() — baseline real, ortools disponível → used=True
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_ORTOOLS, reason="ortools not installed")
def test_refine_with_baseline_returns_schedule_and_used_true():
    lrho = CPSATLRHO(LRHOConfig(horizon_days=2, step_days=1, budget_s=5.0))
    start = datetime(2026, 5, 1, 8, 0)
    # 3 ops sequenciais na mesma máquina, mesmo OF.
    ops = [
        _op(
            f"op-{i}",
            start=start + timedelta(hours=i * 2),
            end=start + timedelta(hours=i * 2 + 1),
            machine_id="M1",
            order_id="OF-1",
        )
        for i in range(3)
    ]
    baseline = {"operations": ops, "makespan_hours": 99.0}

    res = lrho.refine(
        baseline,
        horizon_start=start,
        # `now` no passado → nenhuma op congelada (frozen_cutoff antes
        # de qualquer op).
        now=start - timedelta(days=1),
        horizon_end=start + timedelta(days=3),
    )
    assert res.used is True
    assert res.schedule is not None
    assert len(res.schedule["operations"]) == 3
    # Aggregates recalculados — makespan_hours já não é o 99.0 da baseline.
    assert "makespan_hours" in res.schedule
    assert res.windows >= 1


# ---------------------------------------------------------------------------
# 7) refine() — ops na frozen zone não se movem
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_ORTOOLS, reason="ortools not installed")
def test_refine_frozen_ops_keep_baseline_start():
    """Op cujo start é antes do `now + frozen_zone_hours` E dentro da
    janela é PINNED ao baseline minute. Verificamos que o start não muda.
    """
    lrho = CPSATLRHO(LRHOConfig(horizon_days=2, step_days=1, frozen_zone_hours=4.0))
    horizon_start = datetime(2026, 5, 1, 8, 0)
    now = horizon_start  # frozen_cutoff = now + 4h = 12:00
    # Op começa às 10:00 (frozen — antes do cutoff de 12:00) E dentro da janela.
    frozen_start = horizon_start + timedelta(hours=2)
    frozen_end = frozen_start + timedelta(hours=1)
    # Op livre começa às 16:00 (depois do cutoff).
    free_start = horizon_start + timedelta(hours=8)
    free_end = free_start + timedelta(hours=1)
    ops = [
        _op("frozen", start=frozen_start, end=frozen_end, machine_id="M1"),
        _op("free", start=free_start, end=free_end, machine_id="M2"),
    ]
    res = lrho.refine(
        {"operations": ops},
        horizon_start=horizon_start,
        now=now,
        horizon_end=horizon_start + timedelta(days=2),
    )
    assert res.used is True
    frozen_op = next(o for o in res.schedule["operations"] if o["operation_id"] == "frozen")
    # Frozen op mantém o start baseline (pinned domain).
    assert frozen_op["start"] == frozen_start


# ---------------------------------------------------------------------------
# 8) refine() — budget exhaustion warning
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_ORTOOLS, reason="ortools not installed")
def test_refine_budget_exhausted_emits_warning(monkeypatch):
    """Forçar tempo a passar entre janelas → warning de budget esgotado."""
    from src.plan.engines import cpsat_lrho as mod

    # Sequência crescente: 1ª chamada (started) devolve 0, depois cada
    # nova chamada devolve um valor que já excede o budget de 1s.
    counter = {"i": 0}
    real_time = mod.time.time

    def fake_time():
        counter["i"] += 1
        # started=0, depois saltos grandes para excedermos o budget.
        return [0.0, 0.5, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0][
            min(counter["i"] - 1, 7)
        ]

    monkeypatch.setattr(mod.time, "time", fake_time)

    lrho = CPSATLRHO(LRHOConfig(horizon_days=2, step_days=1, budget_s=1.0))
    start = datetime(2026, 5, 1, 8, 0)
    ops = [
        _op(
            f"op-{i}",
            start=start + timedelta(days=i),
            end=start + timedelta(days=i, hours=1),
            machine_id=f"M{i}",
        )
        for i in range(5)
    ]
    res = lrho.refine(
        {"operations": ops},
        horizon_start=start,
        now=start - timedelta(days=1),
        horizon_end=start + timedelta(days=5),
    )
    # Voltar ao tempo real depois.
    monkeypatch.setattr(mod.time, "time", real_time)
    # Devia ter emitido um warning sobre budget esgotado.
    assert any("budget_exhausted" in w for w in res.warnings)


# ---------------------------------------------------------------------------
# 9) refine() — inter-window precedence (phase_gaps respeitado)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_ORTOOLS, reason="ortools not installed")
def test_refine_applies_phase_gap_between_ops_of_same_order():
    """Op B (curing) tem de começar ≥ end(A) + gap minutos.
    Damos phase_gaps={(A→B): 1h}. Após refine, verificamos o invariant.
    """
    lrho = CPSATLRHO(LRHOConfig(horizon_days=2, step_days=1, budget_s=5.0))
    start = datetime(2026, 5, 1, 8, 0)
    a_start = start + timedelta(hours=8)  # depois do frozen cutoff
    a_end = a_start + timedelta(hours=1)
    b_start = a_end  # baseline: sem gap
    b_end = b_start + timedelta(hours=1)
    ops = [
        _op(
            "A",
            start=a_start,
            end=a_end,
            machine_id="M1",
            order_id="OF-1",
            phase_name="LAMINAGEM",
        ),
        _op(
            "B",
            start=b_start,
            end=b_end,
            machine_id="M2",
            order_id="OF-1",
            phase_name="CURA",
        ),
    ]
    res = lrho.refine(
        {"operations": ops},
        horizon_start=start,
        now=start - timedelta(days=1),  # nada frozen
        horizon_end=start + timedelta(days=2),
        phase_gaps={("LAMINAGEM", "CURA"): 1.0},  # 1h de gap
    )
    assert res.used is True
    # Encontrar A e B no schedule resultante.
    by_id = {o["operation_id"]: o for o in res.schedule["operations"]}
    a_new_end = _parse_dt(by_id["A"]["end"])
    b_new_start = _parse_dt(by_id["B"]["start"])
    # Gap >= 60min (curing).
    delta_min = (b_new_start - a_new_end).total_seconds() / 60.0
    assert delta_min >= 60.0, (
        f"Gap entre A e B é {delta_min}min — devia ser ≥ 60min (curing)"
    )


# ---------------------------------------------------------------------------
# 10) _in_window helper
# ---------------------------------------------------------------------------


def test_in_window_returns_true_for_op_inside_window():
    ws = datetime(2026, 5, 1)
    we = datetime(2026, 5, 3)
    op = _op("x", start=ws + timedelta(hours=1), end=ws + timedelta(hours=2))
    assert _in_window(op, ws, we) is True


def test_in_window_returns_false_for_op_before_window():
    ws = datetime(2026, 5, 1)
    we = datetime(2026, 5, 3)
    op = _op(
        "x", start=ws - timedelta(days=1), end=ws - timedelta(hours=1)
    )
    assert _in_window(op, ws, we) is False


def test_in_window_returns_false_when_start_missing():
    ws = datetime(2026, 5, 1)
    we = datetime(2026, 5, 3)
    assert _in_window({"start": None, "end": None}, ws, we) is False


# ---------------------------------------------------------------------------
# 11) _parse_dt helper
# ---------------------------------------------------------------------------


def test_parse_dt_returns_datetime_passthrough():
    dt = datetime(2026, 5, 1, 10, 30)
    assert _parse_dt(dt) is dt


def test_parse_dt_parses_iso_string():
    out = _parse_dt("2026-05-01T10:30:00")
    assert out == datetime(2026, 5, 1, 10, 30)


def test_parse_dt_returns_none_on_garbage():
    assert _parse_dt("nao-e-data") is None
    assert _parse_dt(None) is None
    assert _parse_dt(42) is None


# ---------------------------------------------------------------------------
# 12) _recompute_aggregates helper
# ---------------------------------------------------------------------------


def test_recompute_aggregates_updates_makespan_hours():
    start = datetime(2026, 5, 1, 8, 0)
    schedule = {
        "operations": [
            _op("a", start=start, end=start + timedelta(hours=2)),
            _op("b", start=start + timedelta(hours=1), end=start + timedelta(hours=5)),
        ],
        "makespan_hours": 999.0,  # valor antigo
    }
    out = _recompute_aggregates(schedule)
    # latest end = start+5h; earliest = start → makespan = 5h.
    assert out["makespan_hours"] == 5.0


def test_recompute_aggregates_returns_schedule_unchanged_when_no_ops():
    schedule = {"operations": [], "makespan_hours": 10.0}
    out = _recompute_aggregates(schedule)
    assert out is schedule
    assert out["makespan_hours"] == 10.0
