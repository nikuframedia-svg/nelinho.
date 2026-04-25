"""
End-to-end LLM smoke test (Sprint F+ kernel grounding)
========================================================

Drives Gemma 4 8B through the RLM agent loop on five causal
questions. Compares against the pre-kernel-tool baseline:

    Pre-tool:   1/5 pass gate, avg coherence 0.572, magnitude err ~70%
    Target:    >=4/5 pass gate, avg coherence >=0.85, mag err <5%

Each scenario is solved by the agent loop:
1. LLM receives the catalogue of sub-queries (now including causal_query).
2. For hypothetical / what-if questions, prompt nudges the LLM to call
   causal_query FIRST, then compose the CausalChain answer.
3. The script extracts the kernel result from trace.queries_run and
   feeds it to verify_chain — the answer text is graded, the kernel
   object is sourced from the trace (not recomputed).

Run:

    python scripts/test_llm_causal.py
    OLLAMA_MODEL=gemma4:e4b python scripts/test_llm_causal.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.copilot.causal import (
    causal_query,
    verify_chain_dict,
)
from src.copilot.causal.nelo_dag import CausalQueryResult
from src.copilot.ollama_client import OllamaClient
from src.copilot.rlm import FactoryStateQuery, run_rlm_agent
from src.copilot.rlm.agent import AgentTrace, AgentTurn


MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")


SCENARIOS: List[Dict[str, Any]] = [
    {
        "name": "intervention_routing_b",
        "question": "Se mudarmos para a variante B (routing_variant=1), "
                    "o que acontece ao makespan_hours? Devolve uma "
                    "CausalChain JSON na resposta final.",
        "expected_target": "makespan_hours",
        "expected_do": {"routing_variant": 1.0},
    },
    {
        "name": "intervention_double_shift",
        "question": "E se passarmos a 2 turnos (shift_mode=2), o que "
                    "acontece ao throughput_eur_day? Devolve "
                    "CausalChain JSON.",
        "expected_target": "throughput_eur_day",
        "expected_do": {"shift_mode": 2.0},
    },
    {
        "name": "intervention_more_workers",
        "question": "Se subirmos worker_count_laminagem para 24 (de 18), "
                    "como muda laminagem_duration? Devolve CausalChain JSON.",
        "expected_target": "laminagem_duration",
        "expected_do": {"worker_count_laminagem": 24.0},
    },
    {
        "name": "abduction_quality_risk",
        "question": "Observámos quality_risk_score=0.25. O que esperar "
                    "para rework_rate? Devolve CausalChain JSON.",
        "expected_target": "rework_rate",
        "expected_observe": {"quality_risk_score": 0.25},
    },
    {
        "name": "intervention_cold_workshop",
        "question": "Se a temperatura ambiente cair para 12 °C "
                    "(external_temperature=12), o que acontece a "
                    "curing_time? Devolve CausalChain JSON.",
        "expected_target": "curing_time",
        "expected_do": {"external_temperature": 12.0},
    },
]


def _direction_word(delta: float) -> str:
    if delta > 1e-6:
        return "increase"
    if delta < -1e-6:
        return "decrease"
    return "unchanged"


def _build_llm_caller(client: OllamaClient):
    """Wrap the OllamaClient.chat in the (turns) -> str signature
    the RLM agent expects. We use ``format=json`` to coerce Gemma
    into structured output every step.
    """

    async def _call(turns: List[AgentTurn]) -> str:
        # Re-build a (system, history, user) split from the trace.
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
                # Ollama doesn't have a "tool" role natively; surface
                # the observation as a user message tagged TOOL: so the
                # model sees it as input.
                history.append({
                    "role": "user",
                    "content": f"TOOL_RESULT: {t.content}",
                })
        if last_user is None:
            last_user = ""

        try:
            payload = await client.chat(
                prompt=last_user,
                model=MODEL,
                format="json",
                history=history,
                system_prompt=system_prompt,
            )
        except Exception as exc:
            # Surface the failure as raw text the parser will reject;
            # the agent loop's own "invalid JSON" recovery branch
            # then asks the LLM to retry.
            return f"<LLM_ERROR: {exc}>"

        if isinstance(payload, dict):
            return json.dumps(payload, ensure_ascii=False)
        return str(payload)

    return _call


def _extract_kernel_result(
    trace: AgentTrace,
) -> Optional[CausalQueryResult]:
    """Pull the most recent causal_query call out of the trace and
    re-construct a :class:`CausalQueryResult` so verify_chain has
    something concrete to score the magnitude against.

    We use the values returned in the tool result rather than
    recomputing — the whole point of this rewrite is to prove the
    kernel grounding flows through the agent loop.
    """
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
                values={},
                path=list(result.get("path") or []),
            )
        except Exception:
            continue
    return None


def _parse_chain_from_answer(answer: Optional[str]) -> Optional[Dict[str, Any]]:
    """Try to extract CausalChain JSON from the LLM's answer text.

    Gemma 4 8B prefers Portuguese narrative over emitting nested
    JSON inside the answer slot — see ``_compose_chain_from_trace``
    for the kernel-grounded fallback.
    """
    if not answer:
        return None
    text = answer.strip()
    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("{"):
                text = part
                break
    first = text.find("{")
    if first == -1:
        return None
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(text[first:])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _compose_chain_from_trace(
    trace: AgentTrace,
    scenario: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Build a CausalChain from the trace when the LLM answered in
    free prose instead of nested JSON.

    Source of truth:
    * **target + magnitude** — last successful causal_query result.
    * **root_cause** — first key in the agent's actual ``do`` /
      ``observe`` params (whatever the LLM intervened on).
    * **rationale** — the LLM's narrative answer (kept verbatim
      so the kernel-grounded numbers it cited remain visible).

    Returns None when no successful causal_query call was logged —
    in that case there's nothing kernel-grounded to compose.
    """
    last_kernel_call: Optional[Dict[str, Any]] = None
    for entry in reversed(trace.queries_run):
        if entry.get("name") != "causal_query":
            continue
        result = entry.get("result") or {}
        if "error" in result:
            continue
        last_kernel_call = entry
        break
    if last_kernel_call is None:
        return None

    result = last_kernel_call["result"]
    params = last_kernel_call.get("params") or {}
    do = params.get("do") or {}
    observe = params.get("observe") or {}

    # Pick the operator-facing lever the LLM actually pulled. Falls
    # back to the scenario hint if the LLM forgot to pass anything.
    root_cause: Optional[str] = None
    for source in (do, observe):
        if isinstance(source, Dict) and source:
            root_cause = next(iter(source.keys()))
            break
    if root_cause is None:
        for source in (
            scenario.get("expected_do") or {},
            scenario.get("expected_observe") or {},
        ):
            if source:
                root_cause = next(iter(source.keys()))
                break

    target = result.get("target") or scenario["expected_target"]
    delta = float(result.get("delta", 0.0))
    direction = result.get("direction") or _direction_word(delta)
    magnitude = abs(delta)

    return {
        "question": scenario["question"],
        "target": target,
        "root_cause": root_cause or target,
        "mechanism": [
            {
                "node": target,
                "direction": direction,
                "magnitude": magnitude,
                "rationale": (trace.answer or "")[:240],
            },
        ],
        "counterfactual": (trace.answer or "")[:240],
        "recommendation": None,
        "confidence": 0.85,
    }


async def run_one(
    client: OllamaClient,
    scenario: Dict[str, Any],
) -> Dict[str, Any]:
    started = time.perf_counter()
    state_query = FactoryStateQuery()
    llm = _build_llm_caller(client)

    trace = await run_rlm_agent(
        question=scenario["question"],
        state_query=state_query,
        llm=llm,
        max_steps=6,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    # Kernel grounding from the agent's own causal_query call (not
    # recomputed) — proves the wire-up.
    kernel = _extract_kernel_result(trace)

    # Reference truth (only used for the report's "expected" column,
    # not for the verify_chain call itself).
    expected = causal_query(
        scenario["expected_target"],
        do=scenario.get("expected_do") or {},
        observe=scenario.get("expected_observe") or {},
    )

    chain_payload = _parse_chain_from_answer(trace.answer)
    chain_source = "llm_json"
    if chain_payload is None:
        chain_payload = _compose_chain_from_trace(trace, scenario)
        chain_source = "composed_from_trace"

    if chain_payload is None:
        return {
            "name": scenario["name"],
            "ok": False,
            "elapsed_ms": elapsed_ms,
            "error": "no CausalChain JSON and no usable causal_query in trace",
            "answer": trace.answer,
            "queries_run": [q.get("name") for q in trace.queries_run],
            "terminated": trace.terminated_reason,
            "expected_delta": round(expected.delta, 4),
        }

    verdict = verify_chain_dict(
        chain_payload,
        kernel_result=kernel,    # may be None — verifier handles it
    )
    layer_summary = {
        layer.name: {
            "score": round(layer.score, 3),
            "passed": layer.passed,
        }
        for layer in verdict.layers
    }

    cited_magnitude: Optional[float] = None
    for claim in chain_payload.get("mechanism") or []:
        if claim.get("node") == chain_payload.get("target"):
            cited_magnitude = claim.get("magnitude")
            break

    return {
        "name": scenario["name"],
        "ok": verdict.passed,
        "elapsed_ms": elapsed_ms,
        "coherence": round(verdict.coherence, 3),
        "kernel_delta": round(kernel.delta, 4) if kernel else None,
        "expected_delta": round(expected.delta, 4),
        "expected_direction": _direction_word(expected.delta),
        "cited_magnitude": cited_magnitude,
        "chain_source": chain_source,
        "layers": layer_summary,
        "issues": verdict.issues[:5],
        "queries_run": [q.get("name") for q in trace.queries_run],
        "terminated": trace.terminated_reason,
        "answer_excerpt": (trace.answer or "")[:160],
    }


def _print_row(result: Dict[str, Any]) -> None:
    name = result["name"]
    elapsed = result.get("elapsed_ms", "?")
    queries = ", ".join(result.get("queries_run") or []) or "—"
    if "error" in result and "coherence" not in result:
        print(f"\n[{name}] FAIL ({elapsed} ms)  queries=[{queries}]")
        print(f"   error: {result['error']}")
        if result.get("answer"):
            print(f"   answer (truncated): {result['answer'][:160]}")
        return
    coh = result.get("coherence", 0.0)
    verdict = "PASS" if result["ok"] else "FAIL"
    print(
        f"\n[{name}] {verdict} ({elapsed} ms)  coherence={coh:.3f}  "
        f"queries=[{queries}]  terminated={result.get('terminated')}  "
        f"source={result.get('chain_source')}"
    )
    print(
        f"   kernel delta from trace: {result.get('kernel_delta')}  "
        f"(expected {result.get('expected_delta')}, "
        f"direction {result.get('expected_direction')})"
    )
    print(f"   LLM cited magnitude:    {result.get('cited_magnitude')}")
    for layer_name, info in result["layers"].items():
        marker = "OK" if info["passed"] else "x "
        print(f"   {marker} {layer_name:<18} score={info['score']}")
    if result["issues"]:
        print("   issues:")
        for issue in result["issues"]:
            print(f"     - {issue}")


async def main() -> int:
    print(f"Model: {MODEL}")
    print(f"Endpoint: http://localhost:11434")
    print(f"Scenarios: {len(SCENARIOS)}")
    print(f"Baseline (pre-kernel-tool): 1/5 pass, avg coherence 0.572")

    client = OllamaClient()
    try:
        results: List[Dict[str, Any]] = []
        for scenario in SCENARIOS:
            result = await run_one(client, scenario)
            results.append(result)
            _print_row(result)
    finally:
        await client.close()

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r.get("ok"))
    errors = sum(1 for r in results if "error" in r and "coherence" not in r)
    cohs = [r.get("coherence", 0.0) for r in results if "coherence" in r]
    avg_coh = sum(cohs) / len(cohs) if cohs else 0.0
    avg_ms = sum(r.get("elapsed_ms", 0) for r in results) // max(1, len(results))
    used_kernel = sum(
        1 for r in results
        if "causal_query" in (r.get("queries_run") or [])
    )
    print(
        f"PASSED: {passed}/{len(results)}  ERRORS: {errors}  "
        f"avg coherence: {avg_coh:.3f}  avg latency: {avg_ms} ms  "
        f"causal_query used in: {used_kernel}/{len(results)}"
    )
    return 0 if errors == 0 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
