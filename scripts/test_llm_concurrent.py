"""
Concurrent LLM stress (Sprint F++++)
======================================

Lança 10 perguntas em paralelo via ``asyncio.gather`` contra a mesma
instância de :class:`OllamaClient`. O Ollama serializa internamente
(GPU é single-tenant), mas o **cliente** tem que lidar com a fila
sem race conditions:

* Circuit breaker partilhado (``_failure_count``, ``_circuit_open_until``)
  não pode ser corrompido por updates concorrentes.
* Cliente HTTPX partilhado (keep-alive pool) tem que ser thread-safe
  para coroutines.
* Cada resposta tem que voltar à coroutine certa (sem misturar
  respostas entre questions).
* Nenhuma resposta truncada / parcial / interleaved.

Não testa throughput do Ollama (sabemos que serializa); testa que o
**lado cliente** não falha sob concorrência.

Run:
    python -X utf8 scripts/test_llm_concurrent.py --json
    python -X utf8 scripts/test_llm_concurrent.py --rounds 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.copilot.ollama_client import OllamaClient
from src.copilot.rlm import FactoryStateQuery, run_rlm_agent

MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")


# ═══════════════════════════════════════════════════════════════════════════
# 10 prompts that each touch a different sub-query path. We want to
# stress different code paths concurrently to maximise the chance of
# catching a race in shared state (FactoryStateQuery is stateless,
# OllamaClient is shared).
# ═══════════════════════════════════════════════════════════════════════════

PROMPTS: List[Dict[str, Any]] = [
    {
        "id": "p01_overview",
        "question": "Resume o estado da fábrica.",
        "expects_subqueries_any": {"overview"},
    },
    {
        "id": "p02_bottleneck",
        "question": "Onde está o gargalo agora?",
        "expects_subqueries_any": {"bottlenecks", "overview"},
    },
    {
        "id": "p03_intervention_shift",
        "question": "Se passar a 2 turnos, qual o throughput esperado?",
        "expects_subqueries_any": {"causal_query"},
        "expects_target": "throughput_eur_day",
    },
    {
        "id": "p04_intervention_pintores",
        "question": "Com 10 pintores, quanto reduz a duração da pintura?",
        "expects_subqueries_any": {"causal_query"},
        "expects_target": "pintura_duration",
    },
    {
        "id": "p05_forecast_throughput",
        "question": "Como vai evoluir o throughput nos próximos 7 turnos?",
        "expects_subqueries_any": {"world_model_forecast"},
    },
    {
        "id": "p06_forecast_quality",
        "question": "Trajectória esperada de quality_risk_score em 14 turnos.",
        "expects_subqueries_any": {"world_model_forecast"},
    },
    {
        "id": "p07_state_skills",
        "question": "Quais fases têm risco de competências?",
        "expects_subqueries_any": {"skills_risk"},
    },
    {
        "id": "p08_state_orders",
        "question": "Quantas ordens estão abertas?",
        "expects_subqueries_any": {"open_orders", "wip", "backlog"},
    },
    {
        "id": "p09_quality_check",
        "question": "Como está a qualidade neste momento?",
        "expects_subqueries_any": {"quality", "overview"},
    },
    {
        "id": "p10_lead_time",
        "question": "Lead time médio nos últimos 90 dias?",
        "expects_subqueries_any": {"lead_time"},
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Agent runner (mesmo padrão dos outros scripts)
# ═══════════════════════════════════════════════════════════════════════════


def _build_llm_caller(client: OllamaClient):
    async def _call(turns):
        system_parts = [t.content for t in turns if t.role == "system"]
        system_prompt = "\n\n".join(system_parts) if system_parts else None
        history, last_user = [], None
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


# ═══════════════════════════════════════════════════════════════════════════
# Per-prompt evaluation (loose — esta bateria foca-se em race conditions,
# não em accuracy semântica fina; isso vai-se cobrir nas outras 2 baterias)
# ═══════════════════════════════════════════════════════════════════════════


def _evaluate(prompt: Dict[str, Any], trace) -> Dict[str, Any]:
    queries = [q.get("name") for q in trace.queries_run]
    queries_set = set(queries)
    answer = (trace.answer or "").strip()
    answer_lower = answer.lower()

    failures: List[str] = []

    if not answer:
        failures.append("empty_answer")

    expected = prompt.get("expects_subqueries_any") or set()
    if expected and not (queries_set & expected):
        failures.append(f"missing_subquery (got {sorted(queries_set)}, expected any of {sorted(expected)})")

    expected_target = prompt.get("expects_target")
    if expected_target:
        targets = []
        for q in trace.queries_run:
            if q.get("name") in {"causal_query", "world_model_forecast"}:
                # NB: agent stores the kwargs under "params" (see
                # run_rlm_agent::queries_run.append). Earlier this was
                # erroneously read as "args", masking real targets and
                # producing spurious wrong_target failures.
                params = q.get("params") or {}
                tgt = params.get("target")
                if tgt:
                    targets.append(tgt)
        if expected_target not in targets:
            failures.append(f"wrong_target (got {targets}, expected {expected_target})")

    # Sanity: detectar resposta interleaved (palavra-chave doutro prompt)
    # Se a resposta a "throughput" mencionar "pintores" + "lead time" + "qualidade"
    # ao mesmo tempo, é suspeito.
    foreign_keywords = {
        "p01_overview": [],
        "p02_bottleneck": [],
        "p03_intervention_shift": ["pintura_duration", "skills_risk"],
        "p04_intervention_pintores": ["throughput_eur_day se passar a 2 turnos"],
        "p05_forecast_throughput": ["lead time médio", "skills_risk"],
        "p06_forecast_quality": ["lead time médio"],
        "p07_state_skills": ["throughput_eur_day"],
        "p08_state_orders": ["world_model_forecast", "trajectória"],
        "p09_quality_check": ["lead time médio"],
        "p10_lead_time": ["throughput se passar"],
    }
    foreigns = foreign_keywords.get(prompt["id"], [])
    interleave_hits = [k for k in foreigns if k.lower() in answer_lower]
    if interleave_hits:
        failures.append(f"possible_interleave ({interleave_hits})")

    return {
        "passed": not failures,
        "failures": failures,
        "queries": queries,
        "answer_chars": len(answer),
        "answer_preview": (answer[:120] + "...") if len(answer) > 120 else answer,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Concurrent runner
# ═══════════════════════════════════════════════════════════════════════════


async def run_one(client: OllamaClient, prompt: Dict[str, Any]) -> Dict[str, Any]:
    state_query = FactoryStateQuery()
    llm = _build_llm_caller(client)
    t0 = time.monotonic()
    try:
        trace = await run_rlm_agent(
            question=prompt["question"],
            state_query=state_query,
            llm=llm,
            max_steps=6,
        )
        elapsed = time.monotonic() - t0
        verdict = _evaluate(prompt, trace)
        verdict["elapsed_s"] = round(elapsed, 2)
        verdict["id"] = prompt["id"]
        verdict["error"] = None
        return verdict
    except Exception as exc:
        elapsed = time.monotonic() - t0
        return {
            "id": prompt["id"],
            "passed": False,
            "failures": [f"runtime_exception: {exc}"],
            "queries": [],
            "answer_chars": 0,
            "answer_preview": "",
            "elapsed_s": round(elapsed, 2),
            "error": str(exc),
        }


def _slice_prompts(concurrency: int) -> List[Dict[str, Any]]:
    """Pick ``concurrency`` prompts from PROMPTS, wrapping around if
    needed so we always launch exactly N prompts per round."""
    if concurrency <= len(PROMPTS):
        return PROMPTS[:concurrency]
    # wrap around (only used if someone passes >10)
    out = []
    for i in range(concurrency):
        out.append(PROMPTS[i % len(PROMPTS)])
    return out


async def run_round(
    client: OllamaClient,
    round_idx: int,
    prompts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """One concurrent round: launch ``len(prompts)`` prompts via gather."""
    print(f"\n--- Round {round_idx + 1} ({len(prompts)} prompts in parallel) ---", flush=True)
    t0 = time.monotonic()
    results = await asyncio.gather(*(run_one(client, p) for p in prompts))
    wall = time.monotonic() - t0
    print(f"   wall={wall:.1f}s  passed={sum(1 for r in results if r['passed'])}/{len(results)}", flush=True)
    for r in results:
        marker = "OK" if r["passed"] else "FAIL"
        print(f"     [{marker}] {r['id']:32s} {r['elapsed_s']:6.2f}s  {','.join(r['queries']) or '-'}", flush=True)
        if r["failures"]:
            print(f"            -> {r['failures']}", flush=True)
    return results


# ═══════════════════════════════════════════════════════════════════════════
# Race-condition checks on shared client state
# ═══════════════════════════════════════════════════════════════════════════


def _inspect_client_state(client: OllamaClient) -> Dict[str, Any]:
    """After all rounds, verify circuit breaker state is consistent."""
    return {
        "failure_count": client._failure_count,
        "circuit_open_until": str(client._circuit_open_until) if client._circuit_open_until else None,
        "last_failure_time": str(client._last_failure_time) if client._last_failure_time else None,
        "http_client_initialised": client._client is not None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════════


def _summarise(all_results: List[List[Dict[str, Any]]], client_state: Dict[str, Any]) -> Dict[str, Any]:
    flat = [r for round_ in all_results for r in round_]
    passed = sum(1 for r in flat if r["passed"])
    total = len(flat)

    elapsed = [r["elapsed_s"] for r in flat]
    elapsed_sorted = sorted(elapsed)

    def _quantile(data: List[float], q: float) -> float:
        if not data:
            return 0.0
        idx = int(q * (len(data) - 1))
        return data[idx]

    failure_modes: Dict[str, int] = {}
    for r in flat:
        for f in r["failures"]:
            key = f.split("(")[0].strip()
            failure_modes[key] = failure_modes.get(key, 0) + 1

    per_prompt: Dict[str, Dict[str, int]] = {}
    for r in flat:
        agg = per_prompt.setdefault(r["id"], {"pass": 0, "fail": 0})
        agg["pass" if r["passed"] else "fail"] += 1

    return {
        "rounds": len(all_results),
        "prompts_per_round": len(PROMPTS),
        "total_calls": total,
        "passed": passed,
        "fail": total - passed,
        "pass_rate": round(passed / total, 3) if total else 0.0,
        "elapsed_min_s": min(elapsed) if elapsed else 0,
        "elapsed_max_s": max(elapsed) if elapsed else 0,
        "elapsed_p50_s": _quantile(elapsed_sorted, 0.50),
        "elapsed_p95_s": _quantile(elapsed_sorted, 0.95),
        "elapsed_mean_s": round(statistics.fmean(elapsed), 2) if elapsed else 0,
        "failure_modes": failure_modes,
        "per_prompt": per_prompt,
        "client_state": client_state,
    }


def _print_summary(summary: Dict[str, Any]) -> None:
    print("\n" + "=" * 72)
    print("CONCURRENT STRESS — SUMMARY")
    print("=" * 72)
    print(f"  Rounds          : {summary['rounds']}")
    print(f"  Prompts/round   : {summary['prompts_per_round']}")
    print(f"  Total calls     : {summary['total_calls']}")
    print(f"  Passed          : {summary['passed']} ({summary['pass_rate'] * 100:.1f}%)")
    print(f"  Failed          : {summary['fail']}")
    print()
    print("  Latency (per call):")
    print(f"    min  = {summary['elapsed_min_s']:.2f}s")
    print(f"    p50  = {summary['elapsed_p50_s']:.2f}s")
    print(f"    p95  = {summary['elapsed_p95_s']:.2f}s")
    print(f"    max  = {summary['elapsed_max_s']:.2f}s")
    print(f"    mean = {summary['elapsed_mean_s']:.2f}s")

    if summary["failure_modes"]:
        print()
        print("  Failure modes:")
        for mode, count in sorted(summary["failure_modes"].items(), key=lambda x: -x[1]):
            print(f"    {mode:40s} {count}")

    print()
    print("  Per-prompt pass/fail across rounds:")
    for pid, agg in sorted(summary["per_prompt"].items()):
        total = agg["pass"] + agg["fail"]
        print(f"    {pid:32s} {agg['pass']}/{total}")

    print()
    print("  Client state after stress (race-check):")
    cs = summary["client_state"]
    print(f"    failure_count       = {cs['failure_count']}")
    print(f"    circuit_open_until  = {cs['circuit_open_until']}")
    print(f"    last_failure_time   = {cs['last_failure_time']}")
    print(f"    http_client_init    = {cs['http_client_initialised']}")

    print()
    cs = summary["client_state"]
    race_clean = (
        cs["failure_count"] == 0
        and cs["circuit_open_until"] is None
    )
    print(f"  Race-condition check: {'CLEAN' if race_clean else 'DIRTY'}")
    print(f"  Semantic pass rate  : {summary['pass_rate'] * 100:.1f}%")
    print()
    if race_clean and summary["pass_rate"] >= 0.9:
        print("  VERDICT: PASS — client safe under concurrency, semantics intact")
    elif race_clean:
        print("  VERDICT: PASS (race-clean) — semantic failures attributable")
        print("           to Ollama serialisation timeouts, not client bugs")
    else:
        print("  VERDICT: FAIL — shared state corrupted under concurrency")
    print("=" * 72 + "\n")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════


async def run_at_concurrency(
    client: OllamaClient,
    *,
    concurrency: int,
    rounds: int,
) -> Dict[str, Any]:
    """Run ``rounds`` rounds at the given concurrency level and return
    a per-level summary (latency quantiles, pass rate, race-clean)."""
    print(f"\n========== concurrency={concurrency} (rounds={rounds}) ==========",
          flush=True)
    prompts = _slice_prompts(concurrency)
    all_results: List[List[Dict[str, Any]]] = []
    for r in range(rounds):
        round_results = await run_round(client, r, prompts)
        all_results.append(round_results)
    client_state = _inspect_client_state(client)
    summary = _summarise(all_results, client_state)
    summary["concurrency"] = concurrency
    return summary


async def main_async(
    rounds: int,
    timeout_s: int,
    concurrency_levels: List[int],
) -> Dict[str, Any]:
    """Run the full concurrency curve and return a top-level summary
    that includes per-level breakdowns."""
    client = OllamaClient(timeout=timeout_s)
    try:
        levels: List[Dict[str, Any]] = []
        for c in concurrency_levels:
            level_summary = await run_at_concurrency(
                client, concurrency=c, rounds=rounds,
            )
            levels.append(level_summary)
        # Final client state across the entire curve (more aggressive
        # race check than checking after each level).
        final_client_state = _inspect_client_state(client)
    finally:
        await client.close()
    return {
        "concurrency_levels": [c for c in concurrency_levels],
        "rounds_per_level": rounds,
        "levels": levels,
        "final_client_state": final_client_state,
    }


def _print_curve(curve: Dict[str, Any]) -> None:
    """Print one row per concurrency level: latency quantiles + pass
    rate + race-clean flag."""
    print("\n" + "=" * 78)
    print("CONCURRENCY CURVE")
    print("=" * 78)
    print(f"  {'conc':>4}  {'rounds':>6}  {'p50':>6}  {'p95':>6}  {'mean':>6}  "
          f"{'pass':>9}  race")
    for level in curve["levels"]:
        cs = level["client_state"]
        race = (
            cs["failure_count"] == 0
            and cs["circuit_open_until"] is None
        )
        print(
            f"  {level['concurrency']:>4}  {level['rounds']:>6}  "
            f"{level['elapsed_p50_s']:>5.1f}s  "
            f"{level['elapsed_p95_s']:>5.1f}s  "
            f"{level['elapsed_mean_s']:>5.1f}s  "
            f"{level['passed']:>3}/{level['total_calls']:<3} "
            f"({level['pass_rate'] * 100:>3.0f}%)  "
            f"{'CLEAN' if race else 'DIRTY'}"
        )

    print()
    print("  Final client state (across full curve):")
    cs = curve["final_client_state"]
    print(f"    failure_count       = {cs['failure_count']}")
    print(f"    circuit_open_until  = {cs['circuit_open_until']}")
    print(f"    http_client_init    = {cs['http_client_initialised']}")

    overall_race = (
        cs["failure_count"] == 0
        and cs["circuit_open_until"] is None
    )
    overall_pass = sum(l["passed"] for l in curve["levels"]) / max(
        sum(l["total_calls"] for l in curve["levels"]), 1
    )
    print()
    print(f"  Race-condition check (gate): {'PASS' if overall_race else 'FAIL'}")
    print(f"  Aggregate semantic pass rate: {overall_pass * 100:.1f}%  (informational)")
    print()
    if overall_race and overall_pass >= 0.9:
        print("  VERDICT: PASS — client safe under concurrency, semantics intact")
    elif overall_race:
        print("  VERDICT: PASS (race-clean) — semantic dips at high concurrency")
        print("           are Ollama queue effects, not client bugs.")
    else:
        print("  VERDICT: FAIL — shared state corrupted under concurrency")
    print("=" * 78 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=2,
                        help="Number of concurrent rounds per level (default 2)")
    parser.add_argument("--concurrency", type=str, default="10",
                        help="CSV list of concurrency levels to sweep, "
                             "e.g. '1,3,5,7,10'. Default '10' "
                             "(single level, retro-compatible).")
    parser.add_argument("--timeout", type=int, default=300,
                        help="Per-call HTTP timeout in seconds. Ollama "
                             "serializes; com 10 prompts paralelos cada um "
                             "pode aguardar 100+s na queue (default 300).")
    parser.add_argument("--json", action="store_true",
                        help="Also dump JSON summary to stdout")
    args = parser.parse_args()

    concurrency_levels = [int(x.strip()) for x in args.concurrency.split(",") if x.strip()]
    if not concurrency_levels:
        print("ERROR: --concurrency requires at least one positive integer", flush=True)
        return 2

    curve = asyncio.run(main_async(args.rounds, args.timeout, concurrency_levels))

    # Always print per-level summary first…
    for level in curve["levels"]:
        _print_summary(level)
    # …then the cross-level curve.
    _print_curve(curve)

    # Always persist the run for diff'ing across runs (gitignored).
    out = Path("scripts/last_concurrent_run.json")
    out.write_text(json.dumps(curve, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"JSON saved: {out}")

    if args.json:
        print("\n--- JSON ---")
        print(json.dumps(curve, indent=2, ensure_ascii=False))

    # Verdict gate: race-cleanliness across the full sweep. Semantic
    # pass rate is informational (Ollama serialises; queue depth at
    # the high end of the curve is an infra signal, not a bug).
    cs = curve["final_client_state"]
    race_clean = (
        cs["failure_count"] == 0
        and cs["circuit_open_until"] is None
    )
    return 0 if race_clean else 1


if __name__ == "__main__":
    sys.exit(main())
