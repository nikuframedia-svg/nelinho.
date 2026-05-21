"""
Massive LLM smoke battery (Sprint F++ — stress test the agent stack)
======================================================================

Drives Gemma 4 8B through ~50 scenarios spanning the 5 causal
question types from Blueprint v2.0 §25, with full coverage of the
NELO_DAG (23 nodes). Captures per-scenario failures into structured
buckets so the next iteration of fixes targets the real top-of-funnel
loss, not whatever last week's anecdotes pointed at.

Run:

    python scripts/test_llm_massive.py
    python scripts/test_llm_massive.py --only intervention
    python scripts/test_llm_massive.py --json  # machine-readable

Output:

* per-scenario PASS/FAIL with coherence + queries-run + failure-class
* aggregate: pass rate per category, top failure modes ranked, the
  exact node IDs that trip the LLM up.

Failure classification (buckets that point at concrete fixes):

* `parse_error`        — JSON malformed in answer slot
* `wrong_node_id`      — LLM called causal_query with a node not in DAG
* `wrong_subquery`     — LLM picked an unrelated sub-query
* `direction_error`    — kernel sign disagreed with LLM claim
* `magnitude_error`    — kernel and LLM diverged numerically (>30 %)
* `max_steps`          — agent loop ran out of budget
* `coherence_low`      — verify_chain coherence < 0.85 for any reason
* `no_kernel_call`     — what-if question without causal_query
* `unclassified`       — escape hatch
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.copilot.causal import (
    NODES_BY_ID,
    causal_query,
    verify_chain_dict,
)
from src.copilot.causal.nelo_dag import CausalQueryResult
from src.copilot.ollama_client import OllamaClient
from src.copilot.rlm import FactoryStateQuery, run_rlm_agent
from src.copilot.rlm.agent import AgentTrace, AgentTurn


MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")


# ═══════════════════════════════════════════════════════════════════════════
# Scenario battery — 5 categories, every NELO_DAG node touched as target
# ═══════════════════════════════════════════════════════════════════════════


def _intervention(name: str, q: str, target: str, do: Dict[str, float]):
    return {
        "name": name, "category": "intervention", "question": q,
        "expected_target": target, "expected_do": do,
        "needs_kernel": True,
    }


def _abduction(name: str, q: str, target: str, observe: Dict[str, float]):
    return {
        "name": name, "category": "abduction", "question": q,
        "expected_target": target, "expected_observe": observe,
        "needs_kernel": True,
    }


def _state(name: str, q: str, sub_query: str):
    return {
        "name": name, "category": "state", "question": q,
        "expected_subquery": sub_query, "needs_kernel": False,
    }


def _counterfactual(name: str, q: str, target: str, do: Dict[str, float]):
    return {
        "name": name, "category": "counterfactual", "question": q,
        "expected_target": target, "expected_do": do,
        "needs_kernel": True,
    }


def _multistep(name: str, q: str, target: str, do: Dict[str, float]):
    return {
        "name": name, "category": "multistep", "question": q,
        "expected_target": target, "expected_do": do,
        "needs_kernel": True,
    }


def _forecast(
    name: str, q: str, target: str, *,
    do: Optional[Dict[str, float]] = None,
    observe: Optional[Dict[str, float]] = None,
):
    """Sprint F+++ — forecast scenarios. The expected sub-query is
    ``world_model_forecast`` (not ``causal_query``). Wording is
    deliberately temporal/probabilistic to disambiguate."""
    return {
        "name": name, "category": "forecast", "question": q,
        "expected_target": target,
        "expected_do": do or {},
        "expected_observe": observe or {},
        "needs_kernel": False,            # uses forecast, not causal_query
        "expected_subquery": "world_model_forecast",
    }


SCENARIOS: List[Dict[str, Any]] = [
    # ─── Intervention (15) — every output node + several process_time ──
    _intervention("int_routing_b_makespan",
        "Se mudarmos para a variante B (routing_variant=1), o que acontece a makespan_hours?",
        "makespan_hours", {"routing_variant": 1.0}),
    _intervention("int_double_shift_throughput",
        "E se passarmos a 2 turnos (shift_mode=2.0), o que acontece a throughput_eur_day?",
        "throughput_eur_day", {"shift_mode": 2.0}),
    _intervention("int_more_workers_lam_duration",
        "Se subirmos worker_count_laminagem para 24, como muda laminagem_duration?",
        "laminagem_duration", {"worker_count_laminagem": 24.0}),
    _intervention("int_cold_curing",
        "Se external_temperature cair para 12, o que acontece a curing_time?",
        "curing_time", {"external_temperature": 12.0}),
    _intervention("int_hot_curing",
        "E se external_temperature subir para 26, como muda curing_time?",
        "curing_time", {"external_temperature": 26.0}),
    _intervention("int_more_pintura_workers",
        "Se worker_count_pintura subir para 10, qual o impacto em pintura_duration?",
        "pintura_duration", {"worker_count_pintura": 10.0}),
    _intervention("int_old_molds_setup",
        "Se mold_age médio subir para 6 anos, o que acontece a mold_setup_time?",
        "mold_setup_time", {"mold_age": 6.0}),
    _intervention("int_low_mold_avail",
        "Se mold_availability_pct cair para 0.6, qual o impacto em setup_count?",
        "setup_count", {"mold_availability_pct": 0.6}),
    _intervention("int_low_material_tardiness",
        "Se material_availability_pct cair para 0.7, o que acontece a total_tardiness_hours?",
        "total_tardiness_hours", {"material_availability_pct": 0.7}),
    _intervention("int_routing_throughput",
        "Routing variante B (=1) — quanto muda o throughput_eur_day?",
        "throughput_eur_day", {"routing_variant": 1.0}),
    _intervention("int_routing_setups",
        "Variante B reduz setup_count em quanto?",
        "setup_count", {"routing_variant": 1.0}),
    _intervention("int_experienced_team_quality",
        "Se operator_experience subir para 12 anos, qual o efeito em quality_risk_score?",
        "quality_risk_score", {"operator_experience": 12.0}),
    _intervention("int_lam_workers_queue",
        "Subir worker_count_laminagem para 22 — laminagem_queue_hours?",
        "laminagem_queue_hours", {"worker_count_laminagem": 22.0}),
    _intervention("int_pintura_workers_queue",
        "Se worker_count_pintura subir para 8, pintura_queue_hours desce?",
        "pintura_queue_hours", {"worker_count_pintura": 8.0}),
    _intervention("int_cold_quality",
        "Temperatura cai para 10 — risco de qualidade (quality_risk_score)?",
        "quality_risk_score", {"external_temperature": 10.0}),

    # ─── Abduction (10) — given an observation, infer downstream ──────
    _abduction("abd_high_quality_risk_rework",
        "Observámos quality_risk_score=0.25. Que esperar para rework_rate?",
        "rework_rate", {"quality_risk_score": 0.25}),
    _abduction("abd_low_material_otd",
        "Vejo material_availability_pct=0.65. Como afecta on_time_delivery_pct?",
        "on_time_delivery_pct", {"material_availability_pct": 0.65}),
    _abduction("abd_high_curing_makespan",
        "Se observarmos curing_time=22h, qual o impacto em makespan_hours?",
        "makespan_hours", {"curing_time": 22.0}),
    _abduction("abd_high_lam_duration_queue",
        "Vejo laminagem_duration=5.5h. Que esperar para laminagem_queue_hours?",
        "laminagem_queue_hours", {"laminagem_duration": 5.5}),
    _abduction("abd_high_setup_makespan",
        "Se mold_setup_time=2h, como afecta makespan_hours?",
        "makespan_hours", {"mold_setup_time": 2.0}),
    _abduction("abd_high_rework_throughput",
        "rework_rate=0.20 observado — impacto em throughput_eur_day?",
        "throughput_eur_day", {"rework_rate": 0.20}),
    _abduction("abd_high_tardiness_otd",
        "total_tardiness_hours=80 — on_time_delivery_pct?",
        "on_time_delivery_pct", {"total_tardiness_hours": 80.0}),
    _abduction("abd_high_makespan_throughput",
        "Vejo makespan_hours=320 — throughput_eur_day desce quanto?",
        "throughput_eur_day", {"makespan_hours": 320.0}),
    _abduction("abd_low_mold_avail_setup",
        "mold_availability_pct=0.7 observado — setup_count?",
        "setup_count", {"mold_availability_pct": 0.7}),
    _abduction("abd_high_quality_throughput",
        "quality_risk_score=0.30 — impacto em throughput_eur_day via rework?",
        "throughput_eur_day", {"quality_risk_score": 0.30}),

    # ─── Counterfactual (8) — "what if we had done X instead" ──────────
    _counterfactual("cf_had_routing_b",
        "E se tivéssemos escolhido a variante B (routing_variant=1)? Como teria sido o makespan?",
        "makespan_hours", {"routing_variant": 1.0}),
    _counterfactual("cf_had_double_shift",
        "Tinha sido melhor ter 2 turnos (shift_mode=2)? Quanto throughput_eur_day extra?",
        "throughput_eur_day", {"shift_mode": 2.0}),
    _counterfactual("cf_had_24_workers",
        "Tinha sido melhor ter usado 24 laminadores (worker_count_laminagem=24)? Impacto em laminagem_duration?",
        "laminagem_duration", {"worker_count_laminagem": 24.0}),
    _counterfactual("cf_had_warmer_room",
        "E se a temperatura tivesse sido 23°C (external_temperature=23)? curing_time teria mudado?",
        "curing_time", {"external_temperature": 23.0}),
    _counterfactual("cf_had_more_molds",
        "Tinhamos tido 95% disponibilidade de moldes (mold_availability_pct=0.95) — setup_count?",
        "setup_count", {"mold_availability_pct": 0.95}),
    _counterfactual("cf_had_full_material",
        "Se material_availability_pct tivesse sido 1.0, total_tardiness_hours teria sido?",
        "total_tardiness_hours", {"material_availability_pct": 1.0}),
    _counterfactual("cf_had_8_pintura",
        "E se tivéssemos tido 8 pintores (worker_count_pintura=8)? pintura_duration?",
        "pintura_duration", {"worker_count_pintura": 8.0}),
    _counterfactual("cf_had_new_molds",
        "Se mold_age médio fosse 1 ano (mold_age=1.0), quality_risk_score teria sido?",
        "quality_risk_score", {"mold_age": 1.0}),

    # ─── State (8) — pure factual lookups, NO causal_query needed ─────
    _state("st_wip", "Quantas ordens em aberto temos?", "wip"),
    _state("st_bottlenecks", "Onde está o gargalo neste momento?", "bottlenecks"),
    _state("st_skills_risk", "Que fases têm risco de competências?", "skills_risk"),
    _state("st_quality", "Quantos erros de qualidade tivemos?", "quality"),
    _state("st_open_orders", "Que ordens estão abertas?", "open_orders"),
    _state("st_overview", "Resumo geral da fábrica.", "overview"),
    _state("st_preference_rules", "Que regras de preferência estão activas?", "preference_rules"),
    _state("st_lead_time", "Qual é o lead time médio?", "lead_time"),

    # ─── Multi-step (5) — compound interventions in one question ──────
    _multistep("ms_2shifts_and_routing_b",
        "Se passarmos a 2 turnos E mudarmos para a variante B, qual o throughput_eur_day?",
        "throughput_eur_day", {"shift_mode": 2.0, "routing_variant": 1.0}),
    _multistep("ms_more_workers_and_routing",
        "24 laminadores e variante B — qual o makespan_hours esperado?",
        "makespan_hours", {"worker_count_laminagem": 24.0, "routing_variant": 1.0}),
    _multistep("ms_cold_and_old_molds",
        "Se external_temperature=14 e mold_age=5, qual o quality_risk_score?",
        "quality_risk_score", {"external_temperature": 14.0, "mold_age": 5.0}),
    _multistep("ms_low_mat_high_quality",
        "material_availability_pct=0.7 mas operator_experience=12, total_tardiness_hours?",
        "total_tardiness_hours", {"material_availability_pct": 0.7, "operator_experience": 12.0}),
    _multistep("ms_full_upgrade",
        "shift_mode=2, routing_variant=1, mold_availability_pct=0.95 — throughput_eur_day?",
        "throughput_eur_day", {"shift_mode": 2.0, "routing_variant": 1.0, "mold_availability_pct": 0.95}),

    # ─── Forecast (8) — deliberately temporal/probabilistic phrasing ──
    _forecast("fc_throughput_7_shifts",
        "Como vai evoluir throughput_eur_day nos próximos 7 turnos?",
        "throughput_eur_day"),
    _forecast("fc_makespan_14_shifts",
        "Trajectória esperada de makespan_hours num horizonte de 14 turnos.",
        "makespan_hours"),
    _forecast("fc_quality_risk_range",
        "Qual o range esperado de quality_risk_score na próxima semana (7 turnos)?",
        "quality_risk_score"),
    _forecast("fc_tardiness_band",
        "Próximos 7 turnos: faixa de incerteza de total_tardiness_hours.",
        "total_tardiness_hours"),
    _forecast("fc_throughput_double_shift",
        "Se passarmos a 2 turnos (shift_mode=2), trajectória de throughput_eur_day nos próximos 7 turnos?",
        "throughput_eur_day", do={"shift_mode": 2.0}),
    _forecast("fc_otd_trajectory",
        "Range esperado de on_time_delivery_pct ao longo de 14 turnos.",
        "on_time_delivery_pct"),
    _forecast("fc_rework_month",
        "Como vai evoluir rework_rate ao longo do mês (30 turnos)?",
        "rework_rate"),
    _forecast("fc_pintura_queue_with_intervention",
        "Trajectória de pintura_queue_hours nos próximos 7 turnos com mold_availability_pct=0.95.",
        "pintura_queue_hours", do={"mold_availability_pct": 0.95}),
]


# ═══════════════════════════════════════════════════════════════════════════
# Agent runner — same wiring as test_llm_causal.py
# ═══════════════════════════════════════════════════════════════════════════


def _direction_word(delta: float) -> str:
    if delta > 1e-6:
        return "increase"
    if delta < -1e-6:
        return "decrease"
    return "unchanged"


def _build_llm_caller(client: OllamaClient):
    async def _call(turns: List[AgentTurn]) -> str:
        system_parts = [t.content for t in turns if t.role == "system"]
        system_prompt = "\n\n".join(system_parts) if system_parts else None
        history: List[Dict[str, str]] = []
        last_user: Optional[str] = None
        for t in turns:
            if t.role == "system":
                continue
            if t.role == "user":
                if last_user is not None:
                    history.append({"role": "user", "content": last_user})
                last_user = t.content
            elif t.role == "assistant":
                history.append({"role": "assistant", "content": t.content})
            elif t.role == "tool":
                history.append({"role": "user", "content": f"TOOL_RESULT: {t.content}"})
        if last_user is None:
            last_user = ""
        try:
            payload = await client.chat(
                prompt=last_user, model=MODEL, format="json",
                history=history, system_prompt=system_prompt,
            )
        except Exception as exc:
            return f"<LLM_ERROR: {exc}>"
        if isinstance(payload, dict):
            return json.dumps(payload, ensure_ascii=False)
        return str(payload)
    return _call


def _extract_kernel(trace: AgentTrace) -> Optional[CausalQueryResult]:
    for entry in reversed(trace.queries_run):
        if entry.get("name") != "causal_query":
            continue
        result = entry.get("result") or {}
        if "error" in result:
            continue
        try:
            return CausalQueryResult(
                target=str(result.get("target")),
                target_value=float(result.get("target_value", 0.0)),
                baseline_value=float(result.get("baseline_value", 0.0)),
                delta=float(result.get("delta", 0.0)),
                values={}, path=list(result.get("path") or []),
            )
        except Exception:
            continue
    return None


def _compose_chain(trace: AgentTrace, scenario: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    last = None
    for entry in reversed(trace.queries_run):
        if entry.get("name") == "causal_query":
            r = entry.get("result") or {}
            if "error" not in r:
                last = entry
                break
    if last is None:
        return None
    result = last["result"]
    params = last.get("params") or {}
    do = params.get("do") or {}
    observe = params.get("observe") or {}
    root_cause = None
    for src in (do, observe):
        if isinstance(src, dict) and src:
            root_cause = next(iter(src.keys()))
            break
    if root_cause is None:
        for src in (scenario.get("expected_do") or {}, scenario.get("expected_observe") or {}):
            if src:
                root_cause = next(iter(src.keys()))
                break
    target = result.get("target") or scenario.get("expected_target")
    delta = float(result.get("delta", 0.0))
    return {
        "question": scenario["question"],
        "target": target,
        "root_cause": root_cause or target,
        "mechanism": [{
            "node": target,
            "direction": result.get("direction") or _direction_word(delta),
            "magnitude": abs(delta),
            "rationale": (trace.answer or "")[:240],
        }],
        "counterfactual": (trace.answer or "")[:240],
        "recommendation": None,
        "confidence": 0.85,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Failure classification — buckets that map to fixes
# ═══════════════════════════════════════════════════════════════════════════


def _classify_failure(
    scenario: Dict[str, Any],
    trace: AgentTrace,
    kernel: Optional[CausalQueryResult],
    verdict_layers: Dict[str, Dict[str, Any]],
    expected_delta: Optional[float],
) -> Tuple[str, str]:
    """Return (failure_class, detail) for a failed scenario."""

    queries = [q.get("name") for q in trace.queries_run]
    queries_with_errors = [
        q for q in trace.queries_run
        if isinstance(q.get("result"), dict) and "error" in q["result"]
    ]

    if trace.terminated_reason == "max_steps_reached":
        # Disambiguate: did it max-out because of node-id errors?
        node_errors = [
            q for q in queries_with_errors
            if "unknown DAG node" in str(q["result"].get("error", ""))
        ]
        if node_errors:
            bad_ids = sorted({
                str(q.get("params", {}).get("target", ""))
                for q in node_errors
                if q.get("name") == "causal_query"
            } | {
                str(k)
                for q in node_errors
                if q.get("name") == "causal_query"
                for k in (q.get("params", {}).get("do") or {}).keys()
            })
            return ("wrong_node_id", f"max_steps after {len(node_errors)} unknown-node attempts: {bad_ids}")
        return ("max_steps", f"queries={queries}")

    if scenario["needs_kernel"] and kernel is None:
        if not queries:
            return ("parse_error", "no actions parsed from LLM")
        if "causal_query" not in queries:
            return ("no_kernel_call", f"used: {queries}")
        # causal_query was called but every call errored.
        node_errors = [
            q for q in queries_with_errors
            if "unknown DAG node" in str(q["result"].get("error", ""))
        ]
        if node_errors:
            return ("wrong_node_id", "all causal_query attempts hit unknown nodes")
        return ("unclassified", f"queries: {queries}, errors: {[q['result'].get('error') for q in queries_with_errors]}")

    if not scenario["needs_kernel"]:
        # State queries shouldn't need the kernel.
        expected_sq = scenario.get("expected_subquery")
        if expected_sq and expected_sq not in queries:
            return ("wrong_subquery", f"expected {expected_sq!r}, used {queries}")
        if not trace.answer:
            return ("parse_error", "no answer text")
        return ("coherence_low", "answer empty or empty")

    # Kernel was called, but coherence is below the gate.
    kernel_layer = verdict_layers.get("kernel", {})
    if not kernel_layer.get("passed", True):
        if kernel and expected_delta is not None:
            if abs(kernel.delta - expected_delta) > 0.5 + abs(expected_delta) * 0.05:
                return ("direction_error", f"kernel.delta={kernel.delta:.3f} expected={expected_delta:.3f}")
        return ("magnitude_error", f"kernel layer failed: {kernel_layer}")

    return ("coherence_low", f"layers: {verdict_layers}")


# ═══════════════════════════════════════════════════════════════════════════
# Per-scenario runner
# ═══════════════════════════════════════════════════════════════════════════


async def run_one(client: OllamaClient, scenario: Dict[str, Any]) -> Dict[str, Any]:
    started = time.perf_counter()
    state_query = FactoryStateQuery()
    llm = _build_llm_caller(client)
    trace = await run_rlm_agent(
        question=scenario["question"], state_query=state_query,
        llm=llm, max_steps=6,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    queries = [q.get("name") for q in trace.queries_run]

    if scenario["category"] == "forecast":
        # Forecast scenario — must call world_model_forecast and return
        # an answer that mentions a quantile or trajectory keyword.
        expected_sq = scenario.get("expected_subquery", "world_model_forecast")
        called_forecast = expected_sq in queries
        called_kernel = "causal_query" in queries

        forecast_entry = next(
            (q for q in trace.queries_run if q.get("name") == expected_sq),
            None,
        )
        forecast_ok = bool(
            forecast_entry
            and isinstance(forecast_entry.get("result"), dict)
            and "error" not in forecast_entry["result"]
            and forecast_entry["result"].get("trajectory")
        )
        answer_lower = (trace.answer or "").lower()
        cites_uncertainty = any(
            tok in answer_lower
            for tok in (
                "p50", "p95", "p05", "trajectó", "trajetó",
                "intervalo", "incerteza", "range", "faixa",
                "evoluir", "previsão", "previsao", "horizonte",
            )
        )
        ok = forecast_ok and bool(trace.answer) and cites_uncertainty
        failure_class = ""
        detail = ""
        if not ok:
            if called_kernel and not called_forecast:
                failure_class = "wrong_world_model_choice"
                detail = "called causal_query for a forecast question"
            elif not called_forecast:
                failure_class = "no_forecast_call"
                detail = f"queries={queries}"
            elif not forecast_ok:
                err = (forecast_entry or {}).get("result", {}).get("error", "")
                failure_class = "forecast_call_errored"
                detail = err
            elif not cites_uncertainty:
                failure_class = "answer_lacks_uncertainty"
                detail = (trace.answer or "")[:120]
            else:
                failure_class = "unclassified"
                detail = ""
        return {
            "name": scenario["name"], "category": scenario["category"],
            "ok": ok, "elapsed_ms": elapsed_ms,
            "queries_run": queries, "terminated": trace.terminated_reason,
            "failure_class": failure_class, "failure_detail": detail,
            "answer_excerpt": (trace.answer or "")[:160],
        }

    if not scenario["needs_kernel"]:
        # State query — pass if expected sub-query was called and answer non-empty.
        expected_sq = scenario.get("expected_subquery")
        ok = (expected_sq in queries) and bool(trace.answer)
        failure_class = ""
        detail = ""
        if not ok:
            failure_class, detail = _classify_failure(scenario, trace, None, {}, None)
        return {
            "name": scenario["name"], "category": scenario["category"],
            "ok": ok, "elapsed_ms": elapsed_ms,
            "queries_run": queries, "terminated": trace.terminated_reason,
            "failure_class": failure_class, "failure_detail": detail,
            "answer_excerpt": (trace.answer or "")[:160],
        }

    # Causal scenario.
    kernel = _extract_kernel(trace)
    expected = causal_query(
        scenario["expected_target"],
        do=scenario.get("expected_do") or {},
        observe=scenario.get("expected_observe") or {},
    )
    chain = _compose_chain(trace, scenario)
    if chain is None:
        failure_class, detail = _classify_failure(scenario, trace, kernel, {}, expected.delta)
        return {
            "name": scenario["name"], "category": scenario["category"],
            "ok": False, "elapsed_ms": elapsed_ms,
            "queries_run": queries, "terminated": trace.terminated_reason,
            "failure_class": failure_class, "failure_detail": detail,
            "expected_delta": round(expected.delta, 4),
            "kernel_delta": round(kernel.delta, 4) if kernel else None,
            "answer_excerpt": (trace.answer or "")[:160],
        }

    verdict = verify_chain_dict(chain, kernel_result=kernel)
    layer_summary = {
        layer.name: {"score": round(layer.score, 3), "passed": layer.passed}
        for layer in verdict.layers
    }
    failure_class = ""
    detail = ""
    if not verdict.passed:
        failure_class, detail = _classify_failure(
            scenario, trace, kernel, layer_summary, expected.delta,
        )

    return {
        "name": scenario["name"], "category": scenario["category"],
        "ok": verdict.passed, "elapsed_ms": elapsed_ms,
        "coherence": round(verdict.coherence, 3),
        "kernel_delta": round(kernel.delta, 4) if kernel else None,
        "expected_delta": round(expected.delta, 4),
        "queries_run": queries, "terminated": trace.terminated_reason,
        "layers": layer_summary,
        "failure_class": failure_class, "failure_detail": detail,
        "answer_excerpt": (trace.answer or "")[:160],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════════


def _print_row(r: Dict[str, Any], idx: int, total: int) -> None:
    cat = r["category"][:6]
    name = r["name"][:32]
    elapsed = r["elapsed_ms"]
    if r["ok"]:
        coh = r.get("coherence", 1.0)
        print(f"  [{idx:>3}/{total}] PASS  {cat:<8} {name:<34} ({elapsed:>6} ms)  coh={coh}")
    else:
        cls = r.get("failure_class", "?")
        print(f"  [{idx:>3}/{total}] FAIL  {cat:<8} {name:<34} ({elapsed:>6} ms)  -> {cls}")


def _print_summary(results: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)

    by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)
    for cat, rows in sorted(by_cat.items()):
        passed = sum(1 for r in rows if r["ok"])
        cohs = [r.get("coherence", 0.0) for r in rows if "coherence" in r]
        avg_coh = sum(cohs) / len(cohs) if cohs else 0.0
        avg_ms = sum(r["elapsed_ms"] for r in rows) // len(rows)
        print(f"  {cat:<14} {passed:>2}/{len(rows):<2}  avg_coh={avg_coh:.3f}  avg_ms={avg_ms}")

    print()
    failures = [r for r in results if not r["ok"]]
    print(f"  TOTAL: {len(results) - len(failures)}/{len(results)} pass")
    print()

    if failures:
        cls_counter: Counter[str] = Counter(r.get("failure_class", "?") for r in failures)
        print("  Failure classes (top -> bottom):")
        for cls, n in cls_counter.most_common():
            print(f"    {cls:<28} {n:>3}")
        print()

    # Sub-query mix — detect prompt drift / wrong tool choice.
    sq_counter: Counter[str] = Counter()
    for r in results:
        for q in r.get("queries_run") or []:
            sq_counter[q] += 1
    if sq_counter:
        print("  Sub-query mix (calls across all scenarios):")
        for sq, n in sq_counter.most_common():
            print(f"    {sq:<28} {n:>3}")
        print()

    # Surface the bad node IDs Gemma keeps fabricating.
    bad_node_attempts: Counter[str] = Counter()
    for r in failures:
        detail = str(r.get("failure_detail", ""))
        if "unknown" in detail.lower() or r.get("failure_class") == "wrong_node_id":
            for tok in detail.replace("[", " ").replace("]", " ").replace(",", " ").split():
                tok = tok.strip("'\"`")
                if tok and not tok.isdigit() and tok not in NODES_BY_ID:
                    if "_" in tok and len(tok) > 8:
                        bad_node_attempts[tok] += 1
    if bad_node_attempts:
        print("  Bad node IDs LLM tried (top 10):")
        for nid, n in bad_node_attempts.most_common(10):
            print(f"    {nid:<40} {n:>3}")


# ═══════════════════════════════════════════════════════════════════════════
# Entry
# ═══════════════════════════════════════════════════════════════════════════


async def amain(args) -> int:
    scenarios = SCENARIOS
    if args.only:
        scenarios = [s for s in scenarios if s["category"] == args.only]
    if args.limit:
        scenarios = scenarios[: args.limit]

    print(f"Model: {MODEL}")
    print("Endpoint: http://localhost:11434")
    print(f"Scenarios: {len(scenarios)} (of {len(SCENARIOS)} total)")
    print()
    print(f"{'#':>5}  {'verdict':<6} {'cat':<8} {'name':<34}  ({'ms':>6})  detail")
    print("-" * 78)

    client = OllamaClient()
    results: List[Dict[str, Any]] = []
    started = time.perf_counter()
    try:
        for i, scenario in enumerate(scenarios, 1):
            r = await run_one(client, scenario)
            results.append(r)
            _print_row(r, i, len(scenarios))
    finally:
        await client.close()
    total_s = time.perf_counter() - started

    _print_summary(results)
    print(f"\nTotal wall time: {total_s:.1f}s")

    if args.json:
        out_path = Path("scripts/last_massive_run.json")
        out_path.write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON saved: {out_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["intervention", "abduction", "counterfactual", "state", "multistep", "forecast"])
    parser.add_argument("--limit", type=int, help="cap to N scenarios (debug)")
    parser.add_argument("--json", action="store_true", help="dump results to scripts/last_massive_run.json")
    args = parser.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
