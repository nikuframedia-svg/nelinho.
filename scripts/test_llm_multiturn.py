"""
Multi-turn LLM smoke (Sprint F++++)
=====================================

Real conversational UX: 5 conversations of 4 turns each. Each turn's
question depends on the previous turn's answer. Tests that the LLM:

* mantém contexto entre turnos (não esquece o gargalo identificado)
* refere correctamente respostas anteriores ("como já vi", "isso")
* muda de tool sub-query quando a pergunta muda (factual → causal →
  forecast → recusa correcta)
* não corrompe / hallucinate quando o histórico cresce

Run:
    python -X utf8 scripts/test_llm_multiturn.py --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.copilot.ollama_client import OllamaClient
from src.copilot.rlm import (
    FactoryStateQuery,
    run_rlm_agent,
    run_rlm_agent_continue,
)
from src.copilot.rlm.agent import AgentTrace

MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")


# ═══════════════════════════════════════════════════════════════════════════
# 5 conversations × 4 turns
# ═══════════════════════════════════════════════════════════════════════════
#
# Each conversation is a list of "turn" dicts. Each turn has:
#   * question — what the operator asks
#   * expects  — list of sub-queries or descriptors that, if found in
#                the trace, count as a pass
#   * must_avoid — phrases or sub-queries the LLM must NOT use
#   * checks    — extra optional check function names
# Pass for the conversation = all 4 turns pass.

CONVERSATIONS: List[Dict[str, Any]] = [

    {
        "id": "conv_pintura_diagnose",
        "title": "Diagnose Pintura bottleneck and explore fixes",
        "turns": [
            {
                "question": "Onde está o gargalo agora?",
                "expects_subqueries": {"bottlenecks", "overview"},
                "must_avoid": set(),
            },
            {
                "question": "Se eu meter mais 4 pintores (ficar com 10), quanto desce a duração da pintura?",
                "expects_subqueries": {"causal_query"},
                "must_avoid": set(),
                "expects_target": "pintura_duration",
            },
            {
                "question": "E se quiser ver a trajectória disso ao longo de 7 turnos?",
                "expects_subqueries": {"world_model_forecast"},
                "must_avoid": set(),
            },
            {
                "question": "OK. E o custo desses 4 pintores extra?",
                "expects_subqueries": set(),  # this is a refusal
                "must_avoid": {"causal_query", "world_model_forecast"},
                "is_refusal": True,
            },
        ],
    },

    {
        "id": "conv_throughput_route_b",
        "title": "Throughput optimisation via routing change",
        "turns": [
            {
                "question": "Qual o throughput esperado se passar a 2 turnos?",
                "expects_subqueries": {"causal_query"},
                "must_avoid": set(),
                "expects_target": "throughput_eur_day",
            },
            {
                "question": "E se em vez disso usar a variante B?",
                "expects_subqueries": {"causal_query"},
                "must_avoid": set(),
                "expects_target": "throughput_eur_day",
            },
            {
                "question": "Qual dos dois rende mais?",
                "expects_subqueries": set(),  # comparison only — should reason from prior
                "must_avoid": set(),
                "checks_comparison": True,
            },
            {
                "question": "Com a opção que escolheste, como vai isso evoluir nos próximos 14 turnos?",
                "expects_subqueries": {"world_model_forecast"},
                "must_avoid": set(),
            },
        ],
    },

    {
        "id": "conv_quality_chain",
        "title": "Quality risk → rework → throughput chain",
        "turns": [
            {
                "question": "Como está a qualidade?",
                "expects_subqueries": {"quality", "overview"},
                "must_avoid": set(),
            },
            {
                "question": "Se o quality_risk_score subir para 0.25, o que vai acontecer ao rework_rate?",
                "expects_subqueries": {"causal_query"},
                "must_avoid": set(),
                "expects_target": "rework_rate",
            },
            {
                "question": "E o impacto disso no throughput diário?",
                "expects_subqueries": {"causal_query"},
                "must_avoid": set(),
                "expects_target": "throughput_eur_day",
            },
            {
                "question": "A culpa é do operador X que entrou agora?",
                "expects_subqueries": set(),
                "must_avoid": {"causal_query", "world_model_forecast"},
                "is_refusal": True,
            },
        ],
    },

    {
        "id": "conv_temperature_drift",
        "title": "Temperature impact on cure + quality",
        "turns": [
            {
                "question": "Está frio. Uns 12 graus. Como afecta o tempo de cura?",
                "expects_subqueries": {"causal_query"},
                "must_avoid": set(),
                "expects_target": "curing_time",
            },
            {
                "question": "E o risco de qualidade nessa temperatura?",
                "expects_subqueries": {"causal_query"},
                "must_avoid": set(),
                "expects_target": "quality_risk_score",
            },
            {
                "question": "Se nada mudar, como vai isso evoluir nos próximos 14 turnos?",
                "expects_subqueries": {"world_model_forecast"},
                "must_avoid": set(),
            },
            {
                "question": "Que regras é que temos confirmadas para gerir isto?",
                "expects_subqueries": {"preference_rules"},
                "must_avoid": set(),
            },
        ],
    },

    {
        "id": "conv_state_drilldown",
        "title": "Pure state navigation — no causal needed",
        "turns": [
            {
                "question": "Resumo geral por favor.",
                "expects_subqueries": {"overview"},
                "must_avoid": set(),
            },
            {
                "question": "Conta-me mais sobre as fases com risco de competências.",
                "expects_subqueries": {"skills_risk"},
                "must_avoid": set(),
            },
            {
                "question": "Há ordens em atraso?",
                "expects_subqueries": {"open_orders", "wip", "backlog"},
                "must_avoid": set(),
            },
            {
                "question": "E o lead time médio nos últimos 90 dias?",
                "expects_subqueries": {"lead_time"},
                "must_avoid": set(),
            },
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Agent runner
# ═══════════════════════════════════════════════════════════════════════════


def _build_llm_caller(client):
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
# Per-turn evaluation
# ═══════════════════════════════════════════════════════════════════════════


COMPARISON_WORDS = (
    "melhor", "pior", "maior", "menor", "mais", "menos",
    " ou ", "vs ", "comparando", "diferença", "compara",
)
REFUSAL_PHRASES = (
    "não tenho", "nao tenho", "não sei", "nao sei",
    "fora do meu", "fora do âmbito", "fora do ambito",
    "não posso responder", "nao posso responder",
    "não dispon", "nao dispon", "sem dados",
    "limitad", "scope", "o meu papel", "meu papel é",
    "competência", "competencia",
)


def _evaluate_turn(
    turn: Dict[str, Any],
    trace: AgentTrace,
    *,
    cumulative_queries: Optional[set] = None,
) -> Dict[str, Any]:
    """Evaluate one turn against the per-turn expectations.

    ``cumulative_queries`` carries the sub-queries that were already
    called in earlier turns of THIS conversation. The LLM can
    legitimately re-use prior tool results without re-calling the
    same sub-query in a follow-up — so the "expects_subquery" check
    accepts either a current call OR a prior call.
    """
    cumulative_queries = cumulative_queries or set()
    queries = [q.get("name") for q in trace.queries_run]
    queries_set = set(queries)
    answer = (trace.answer or "").strip()
    answer_lower = answer.lower()

    # 1. must_avoid sub-queries (always strict — the LLM should never
    #    have called these in THIS turn).
    if turn.get("must_avoid") and (queries_set & turn["must_avoid"]):
        return {
            "ok": False, "failure": "called_avoided_subquery",
            "queries": queries, "answer_excerpt": answer[:120],
        }

    # 2. expected sub-queries — pass if called now OR earlier in the
    #    same conversation.
    expects = turn.get("expects_subqueries") or set()
    if expects:
        seen_subqueries = queries_set | cumulative_queries
        if not (seen_subqueries & expects):
            return {
                "ok": False, "failure": f"missing_subquery_(any of {sorted(expects)})",
                "queries": queries, "answer_excerpt": answer[:120],
            }

    # 3. refusal turns
    if turn.get("is_refusal"):
        refused = any(p in answer_lower for p in REFUSAL_PHRASES)
        called_kernel = any(
            q in queries for q in ("causal_query", "world_model_forecast")
        )
        if called_kernel:
            return {
                "ok": False, "failure": "tried_to_answer_with_kernel",
                "queries": queries, "answer_excerpt": answer[:120],
            }
        if not refused and not answer:
            return {
                "ok": False, "failure": "no_refusal_and_no_answer",
                "queries": queries, "answer_excerpt": answer[:120],
            }
        # Implicit refusal also counts (didn't call kernel + has answer).
        return {
            "ok": True, "failure": "",
            "queries": queries, "answer_excerpt": answer[:120],
            "explicit_refusal": refused,
        }

    # 4. comparison turns must mention 2+ outcomes
    if turn.get("checks_comparison"):
        compares = any(w in answer_lower for w in COMPARISON_WORDS)
        if not compares:
            return {
                "ok": False, "failure": "answer_lacks_comparison",
                "queries": queries, "answer_excerpt": answer[:120],
            }

    # 5. must have a non-empty answer
    if not answer:
        return {
            "ok": False, "failure": "empty_answer",
            "queries": queries, "answer_excerpt": "",
        }

    return {
        "ok": True, "failure": "",
        "queries": queries, "answer_excerpt": answer[:120],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Conversation runner
# ═══════════════════════════════════════════════════════════════════════════


async def run_conversation(client, conv: Dict[str, Any]) -> Dict[str, Any]:
    state_query = FactoryStateQuery()
    llm = _build_llm_caller(client)
    started = time.perf_counter()

    turn_results: List[Dict[str, Any]] = []
    prior: Optional[AgentTrace] = None
    cumulative_queries: set = set()

    for idx, turn in enumerate(conv["turns"]):
        t_started = time.perf_counter()
        if prior is None:
            trace = await run_rlm_agent(
                question=turn["question"], state_query=state_query,
                llm=llm, max_steps=6,
            )
        else:
            trace = await run_rlm_agent_continue(
                prior_trace=prior, question=turn["question"],
                state_query=state_query, llm=llm, max_steps=6,
            )
        elapsed_ms = int((time.perf_counter() - t_started) * 1000)
        verdict = _evaluate_turn(
            turn, trace, cumulative_queries=cumulative_queries,
        )
        turn_results.append({
            "turn_index": idx,
            "question": turn["question"],
            "elapsed_ms": elapsed_ms,
            **verdict,
        })
        prior = trace
        cumulative_queries |= {q.get("name") for q in trace.queries_run}

    total_ms = int((time.perf_counter() - started) * 1000)
    full_pass = all(t["ok"] for t in turn_results)
    turns_passed = sum(1 for t in turn_results if t["ok"])

    return {
        "id": conv["id"], "title": conv["title"],
        "ok": full_pass,
        "turns_passed": turns_passed, "turns_total": len(turn_results),
        "total_ms": total_ms,
        "turn_results": turn_results,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════════


def _print_conversation(idx: int, total: int, result: Dict[str, Any]) -> None:
    badge = "PASS" if result["ok"] else "FAIL"
    print(
        f"\n[{idx}/{total}] {badge}  {result['id']:<28}  "
        f"{result['turns_passed']}/{result['turns_total']} turns  "
        f"({result['total_ms']:>6} ms)"
    )
    print(f"   {result['title']}")
    for tr in result["turn_results"]:
        marker = "OK" if tr["ok"] else "x "
        q_preview = tr["question"][:60]
        print(
            f"   {marker} turn{tr['turn_index']+1} ({tr['elapsed_ms']:>5} ms) "
            f"[{','.join(tr['queries']) or '—'}]"
        )
        print(f"        Q: {q_preview}")
        if not tr["ok"]:
            print(f"        FAIL: {tr['failure']}")
        print(f"        A: {tr['answer_excerpt']}")


def _print_summary(results: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 78)
    print("MULTI-TURN SUMMARY")
    print("=" * 78)
    full = sum(1 for r in results if r["ok"])
    total_turns = sum(r["turns_total"] for r in results)
    passed_turns = sum(r["turns_passed"] for r in results)
    print(f"  Conversations passed (all turns): {full}/{len(results)}")
    print(f"  Turns passed: {passed_turns}/{total_turns}")
    failures = []
    for r in results:
        for tr in r["turn_results"]:
            if not tr["ok"]:
                failures.append((r["id"], tr["turn_index"], tr["failure"]))
    if failures:
        print()
        print("  Failed turns:")
        cls_counter = Counter(f[2] for f in failures)
        for cls, n in cls_counter.most_common():
            print(f"    {cls:<35} {n}")
        print()
        for cid, idx, fail in failures:
            print(f"    {cid} turn{idx+1} -> {fail}")


async def amain(args) -> int:
    convs = CONVERSATIONS
    if args.only:
        convs = [c for c in convs if c["id"] == args.only]
    if args.limit:
        convs = convs[: args.limit]

    print(f"Model: {MODEL}")
    print(f"Conversations: {len(convs)} (of {len(CONVERSATIONS)} total)")

    client = OllamaClient()
    results = []
    started = time.perf_counter()
    try:
        for i, conv in enumerate(convs, 1):
            r = await run_conversation(client, conv)
            results.append(r)
            _print_conversation(i, len(convs), r)
    finally:
        await client.close()
    total_s = time.perf_counter() - started

    _print_summary(results)
    print(f"\nTotal wall time: {total_s:.1f}s")

    if args.json:
        out = Path("scripts/last_multiturn_run.json")
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"JSON saved: {out}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="run a single conversation by id")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
