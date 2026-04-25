"""
Adversarial LLM battery — onde dói (Sprint F++++)
====================================================

A bateria normal (test_llm_massive.py, 54/54) cobre perguntas
formais e bem-formadas. A REALIDADE da Nelo é gestor a falar em
estilo casual, com erros, abreviaturas, perguntas ambíguas,
perguntas fora do DAG, e perguntas que misturam ideias.

Este ficheiro testa o sistema em CONDIÇÕES REAIS:

* Linguagem de gestor (informal, verbos imperativos, abreviaturas)
* Perguntas ambíguas com múltiplas interpretações válidas
* Comparações ("é melhor X ou Y?")
* Multi-step composto (precisa de 2+ chamadas)
* RECUSA correcta — perguntas FORA do DAG (Copilot tem de dizer
  "não tenho dados sobre isso", não inventar)
* Typos + erros de português + mistura PT/EN

Run:
    python -X utf8 scripts/test_llm_adversarial.py --json
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
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.copilot.causal import causal_query
from src.copilot.ollama_client import OllamaClient
from src.copilot.rlm import FactoryStateQuery, run_rlm_agent


MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")


# ═══════════════════════════════════════════════════════════════════════════
# Adversarial scenarios — 30 cenários distribuídos por 6 buckets
# ═══════════════════════════════════════════════════════════════════════════


def _hard_intervention(name, q, target, do):
    """Interventions phrased like a real Nelo manager (casual,
    abbreviated, sometimes ambiguous)."""
    return {
        "name": name, "category": "casual", "question": q,
        "expected_target": target, "expected_do": do,
        "expected_subquery": "causal_query",
    }


def _ambiguous(name, q, *, valid_subqueries, valid_targets):
    """Multi-interpretation questions. Pass if LLM picks ANY of
    the valid sub-queries and gives a useful answer."""
    return {
        "name": name, "category": "ambiguous", "question": q,
        "valid_subqueries": valid_subqueries,
        "valid_targets": valid_targets,
    }


def _comparison(name, q, target, do_a, do_b):
    """'É melhor X ou Y?' — needs 2+ causal_query calls + comparison."""
    return {
        "name": name, "category": "comparison", "question": q,
        "expected_target": target,
        "scenarios": [do_a, do_b],
    }


def _refusal(name, q, *, reason):
    """Question outside the DAG. Pass = LLM refuses gracefully
    (says 'não tenho dados' rather than inventing)."""
    return {
        "name": name, "category": "refusal", "question": q,
        "reason": reason,
    }


def _typo_pt(name, q, target, do):
    """Casual / mistyped Portuguese — "se subir os turno", "throuput",
    "qta merda" — same content, broken surface form."""
    return {
        "name": name, "category": "typo", "question": q,
        "expected_target": target, "expected_do": do,
    }


def _forecast_casual(name, q, target):
    """Forecast question phrased without obvious "trajectória"
    keyword — tests whether the LLM recognises temporal intent."""
    return {
        "name": name, "category": "forecast_casual", "question": q,
        "expected_target": target,
        "expected_subquery": "world_model_forecast",
    }


SCENARIOS: List[Dict[str, Any]] = [

    # ─── Casual / operário (8) — typical Nelo manager voice ──────────
    _hard_intervention("cas_2_turnos_casual",
        "Mete 2 turnos. Quanto rende mais por dia?",
        "throughput_eur_day", {"shift_mode": 2.0}),
    _hard_intervention("cas_pintura_4_pessoas",
        "E se eu pôr 4 pintores em vez dos 6? Como fica a duração?",
        "pintura_duration", {"worker_count_pintura": 4.0}),
    _hard_intervention("cas_sair_lam_24",
        "Subir laminagem para 24 — vai descer a duração quanto?",
        "laminagem_duration", {"worker_count_laminagem": 24.0}),
    _hard_intervention("cas_frio_pavilhao",
        "Está frio no pavilhão (uns 12 graus). A cura demora mais?",
        "curing_time", {"external_temperature": 12.0}),
    _hard_intervention("cas_moldes_velhos",
        "Os moldes estão velhotes — uns 6 anos de média. O setup tá pior?",
        "mold_setup_time", {"mold_age": 6.0}),
    _hard_intervention("cas_material_curto",
        "Estamos com material a 70%. Os atrasos disparam?",
        "total_tardiness_hours", {"material_availability_pct": 0.7}),
    _hard_intervention("cas_variante_b_atalho",
        "Variante B faz menos setups, ou faz mais?",
        "setup_count", {"routing_variant": 1.0}),
    _hard_intervention("cas_pessoal_experiente",
        "Se a malta tiver 12 anos de fábrica em média, o risco de qualidade desce?",
        "quality_risk_score", {"operator_experience": 12.0}),

    # ─── Ambíguas (5) — múltiplas interpretações válidas ─────────────
    _ambiguous("amb_qual_problema",
        "Qual é o nosso maior problema agora?",
        valid_subqueries={"bottlenecks", "skills_risk", "quality", "overview"},
        valid_targets=set()),
    _ambiguous("amb_como_estamos",
        "Como é que estamos hoje?",
        valid_subqueries={"overview", "wip", "bottlenecks"},
        valid_targets=set()),
    _ambiguous("amb_falta_pessoal",
        "Há fases com falta de pessoal?",
        valid_subqueries={"skills_risk", "overview"},
        valid_targets=set()),
    _ambiguous("amb_qualidade",
        "A qualidade está pior?",
        valid_subqueries={"quality", "preference_rules"},
        valid_targets=set()),
    _ambiguous("amb_o_que_atrasa",
        "O que está a atrasar a fábrica?",
        valid_subqueries={"bottlenecks", "overview", "lead_time"},
        valid_targets=set()),

    # ─── Comparação (5) — precisa de 2 causal_query + comparar ───────
    _comparison("comp_2turnos_vs_b",
        "É melhor passar a 2 turnos ou mudar para a variante B?",
        "throughput_eur_day",
        {"shift_mode": 2.0}, {"routing_variant": 1.0}),
    _comparison("comp_24_vs_b_makespan",
        "Para baixar o makespan, é melhor 24 laminadores ou variante B?",
        "makespan_hours",
        {"worker_count_laminagem": 24.0}, {"routing_variant": 1.0}),
    _comparison("comp_temp_quente_vs_frio",
        "A cura é mais rápida com 12 ou com 26 graus?",
        "curing_time",
        {"external_temperature": 12.0}, {"external_temperature": 26.0}),
    _comparison("comp_mold_avail_high_vs_low",
        "Setups são menos com moldes a 95% ou a 75% disponibilidade?",
        "setup_count",
        {"mold_availability_pct": 0.95}, {"mold_availability_pct": 0.75}),
    _comparison("comp_material_full_vs_70",
        "Os atrasos são menores com material a 100% ou a 70%?",
        "total_tardiness_hours",
        {"material_availability_pct": 1.0}, {"material_availability_pct": 0.7}),

    # ─── Recusa correcta (5) — fora do DAG, LLM tem de não inventar ──
    _refusal("ref_quem_e_paulo",
        "Quem é o Paulo? É bom trabalhador?",
        reason="employee_specific data not in DAG"),
    _refusal("ref_preco_kayak_modelo_K1",
        "Quanto custa o modelo K1 ao consumidor final?",
        reason="commercial pricing not in DAG"),
    _refusal("ref_lucro_anual",
        "Qual foi o lucro líquido da Nelo em 2025?",
        reason="financial reports not in DAG"),
    _refusal("ref_estrategia_concorrencia",
        "Como devemos competir com a Plastex?",
        reason="strategic / market data not in DAG"),
    _refusal("ref_motivacao_equipa",
        "A equipa está motivada esta semana?",
        reason="HR sentiment not in DAG"),

    # ─── Typos / erros de PT (4) ─────────────────────────────────────
    _typo_pt("typo_throput",
        "se a temperatura sobe pra 25 graus o throuput muda?",
        "throughput_eur_day", {"external_temperature": 25.0}),
    _typo_pt("typo_concordancia",
        "Se eu mete dois turno o makespam vai descer?",
        "makespan_hours", {"shift_mode": 2.0}),
    _typo_pt("typo_workers_lam",
        "subir os trabalhadores da laminagem para 22 fas a duração baxar?",
        "laminagem_duration", {"worker_count_laminagem": 22.0}),
    _typo_pt("typo_qualidade_typo",
        "kalidade vai mal se a tempraturra cair pra 11?",
        "quality_risk_score", {"external_temperature": 11.0}),

    # ─── Forecast casual (3) — sem palavras óbvias ───────────────────
    _forecast_casual("fcc_proximo_mes",
        "Como é que isto vai estar daqui a um mês?",
        "throughput_eur_day"),
    _forecast_casual("fcc_semana_que_vem",
        "Para a semana que vem, o makespan deve andar entre quanto e quanto?",
        "makespan_hours"),
    _forecast_casual("fcc_caminhos",
        "Como é que o atraso vai evoluir nos próximos 14 turnos se nada mudar?",
        "total_tardiness_hours"),
]


# ═══════════════════════════════════════════════════════════════════════════
# Agent runner (reuse the wiring proven in test_llm_massive.py)
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


def _kernel_for(scenario):
    """Compute the kernel ground truth for scenarios that have one."""
    target = scenario.get("expected_target")
    if not target:
        return None
    return causal_query(
        target,
        do=scenario.get("expected_do") or {},
        observe=scenario.get("expected_observe") or {},
    )


# ═══════════════════════════════════════════════════════════════════════════
# Per-scenario runner with category-specific evaluation
# ═══════════════════════════════════════════════════════════════════════════


async def run_one(client, scenario):
    started = time.perf_counter()
    state_query = FactoryStateQuery()
    llm = _build_llm_caller(client)
    trace = await run_rlm_agent(
        question=scenario["question"], state_query=state_query,
        llm=llm, max_steps=8,  # extra room for comparison scenarios
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    queries = [q.get("name") for q in trace.queries_run]
    answer = (trace.answer or "").strip()
    answer_lower = answer.lower()
    cat = scenario["category"]

    base = {
        "name": scenario["name"], "category": cat,
        "elapsed_ms": elapsed_ms,
        "queries_run": queries, "terminated": trace.terminated_reason,
        "answer_excerpt": answer[:160],
    }

    # ─── Casual intervention / typo — same eval as massive ─────────
    if cat in ("casual", "typo"):
        kernel_call = next(
            (q for q in trace.queries_run if q.get("name") == "causal_query"
             and isinstance(q.get("result"), dict) and "error" not in q["result"]),
            None,
        )
        ok = kernel_call is not None and bool(answer)
        cls = ""
        if not ok:
            if "causal_query" not in queries:
                cls = "no_kernel_call"
            else:
                cls = "kernel_errored"
        return {**base, "ok": ok, "failure_class": cls}

    # ─── Ambiguous — pass if any valid sub-query was used ──────────
    if cat == "ambiguous":
        valid = scenario["valid_subqueries"]
        ok = bool(set(queries) & valid) and bool(answer)
        cls = "" if ok else "wrong_subquery_for_ambiguous"
        return {**base, "ok": ok, "failure_class": cls,
                "expected_any_of": sorted(valid)}

    # ─── Comparison — pass if 2 causal_query calls AND answer
    #     mentions comparison (melhor / mais / X ou Y) ─────────────
    if cat == "comparison":
        kernel_calls = [
            q for q in trace.queries_run
            if q.get("name") == "causal_query"
            and isinstance(q.get("result"), dict) and "error" not in q["result"]
        ]
        comparison_words = (
            "melhor", "pior", "maior", "menor", "mais", "menos",
            "vs ", " ou ", "comparar", "diferença",
        )
        compares = any(w in answer_lower for w in comparison_words)
        ok = len(kernel_calls) >= 2 and compares
        cls = ""
        if not ok:
            if len(kernel_calls) < 2:
                cls = f"only_{len(kernel_calls)}_kernel_calls"
            elif not compares:
                cls = "answer_lacks_comparison"
        return {**base, "ok": ok, "failure_class": cls,
                "kernel_calls": len(kernel_calls)}

    # ─── Refusal — pass if the LLM stayed in its lane:
    #     1) didn't pretend the question is answerable via the DAG
    #        (no causal_query / world_model_forecast calls), AND
    #     2) didn't fabricate big KPI-shaped numbers, AND
    #     3) gave an actual answer (not empty).
    #
    # An explicit "não tenho dados" phrase is a STRONG signal but
    # we don't require it — the LLM can refuse implicitly ("o meu
    # papel é...", "esta análise está fora do meu scope...") and
    # that's still a correct refusal as long as it didn't try to
    # answer with kernel-grounded numbers.
    if cat == "refusal":
        called_causal_tools = bool(set(queries) & {
            "causal_query", "world_model_forecast",
        })

        # Explicit refusal phrases — informational only, used when
        # we report the failure mode.
        refusal_phrases = (
            "não tenho", "nao tenho", "não sei", "nao sei",
            "fora do meu", "fora do âmbito", "fora do ambito",
            "não posso responder", "nao posso responder",
            "não dispon", "nao dispon", "não cobre", "nao cobre",
            "sem dados", "não está", "nao esta", "não consta",
            "não conheço", "nao conheço",
            "limitad", "scope",
            "o meu papel", "meu papel é",
            "competência", "competencia", "âmbito", "ambito",
            "não é a minha", "nao e a minha",
        )
        explicit_refusal = any(p in answer_lower for p in refusal_phrases)

        # "Invented number" detector — calibrated:
        #   * ignore 4-digit values that look like years (1900-2100)
        #   * ignore any number that already appeared in the question
        #     (the LLM repeating "2025" from the user's prompt is not
        #      invention).
        import re
        question_numbers = set(re.findall(r"\d+", scenario["question"]))
        invented = []
        for m in re.findall(r"\b\d{3,}\b", answer):
            if m in question_numbers:
                continue                           # echoing the user
            value = int(m)
            if 1900 <= value <= 2100:
                continue                           # year reference
            if value <= 100:
                continue                           # too small to be a fake KPI
            invented.append(m)

        ok = (
            not called_causal_tools
            and not invented
            and bool(answer)
        )
        cls = ""
        if not ok:
            if called_causal_tools:
                cls = "tried_to_answer_with_kernel"
            elif invented:
                cls = "refused_but_invented_numbers"
            else:
                cls = "no_answer"
        return {**base, "ok": ok, "failure_class": cls,
                "invented_numbers": invented,
                "explicit_refusal_phrase": explicit_refusal}

    # ─── Forecast casual — same as forecast in massive battery ─────
    if cat == "forecast_casual":
        forecast_call = next(
            (q for q in trace.queries_run if q.get("name") == "world_model_forecast"
             and isinstance(q.get("result"), dict) and "error" not in q["result"]),
            None,
        )
        kernel_used = "causal_query" in queries
        cites_uncertainty = any(
            tok in answer_lower
            for tok in (
                "p50", "p95", "p05", "trajec", "intervalo", "incerteza",
                "range", "faixa", "evolu", "horizon", "previsão", "previsao",
                "deve andar", "esperado", "estimativa",
            )
        )
        ok = bool(forecast_call) and bool(answer) and cites_uncertainty
        cls = ""
        if not ok:
            if kernel_used and not forecast_call:
                cls = "wrong_world_model_choice"
            elif not forecast_call:
                cls = "no_forecast_call"
            elif not cites_uncertainty:
                cls = "answer_lacks_uncertainty"
        return {**base, "ok": ok, "failure_class": cls}

    return {**base, "ok": False, "failure_class": "unknown_category"}


# ═══════════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════════


def _print_row(r, idx, total):
    cat = r["category"][:8]
    name = r["name"][:34]
    elapsed = r["elapsed_ms"]
    if r["ok"]:
        print(f"  [{idx:>3}/{total}] PASS  {cat:<10} {name:<36} ({elapsed:>6} ms)")
    else:
        cls = r.get("failure_class", "?")
        print(f"  [{idx:>3}/{total}] FAIL  {cat:<10} {name:<36} ({elapsed:>6} ms)  -> {cls}")


def _print_summary(results):
    print("\n" + "=" * 80)
    print("ADVERSARIAL SUMMARY")
    print("=" * 80)
    by_cat = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)
    for cat, rows in sorted(by_cat.items()):
        passed = sum(1 for r in rows if r["ok"])
        avg_ms = sum(r["elapsed_ms"] for r in rows) // len(rows)
        print(f"  {cat:<18} {passed:>2}/{len(rows):<2}  avg_ms={avg_ms}")

    failures = [r for r in results if not r["ok"]]
    print()
    print(f"  TOTAL: {len(results) - len(failures)}/{len(results)} pass")
    if failures:
        cls_counter = Counter(r.get("failure_class", "?") for r in failures)
        print()
        print("  Failure classes:")
        for cls, n in cls_counter.most_common():
            print(f"    {cls:<32} {n:>3}")
        print()
        print("  Failed scenarios (top 10):")
        for r in failures[:10]:
            print(f"    {r['name']:<34}  -> {r.get('failure_class','?')}")
            ans = r.get("answer_excerpt", "")
            if ans:
                print(f"      answer: {ans[:140]}")


async def amain(args):
    scenarios = SCENARIOS
    if args.only:
        scenarios = [s for s in scenarios if s["category"] == args.only]
    if args.limit:
        scenarios = scenarios[: args.limit]

    print(f"Model: {MODEL}")
    print(f"Adversarial scenarios: {len(scenarios)} (of {len(SCENARIOS)} total)")
    print()
    client = OllamaClient()
    results = []
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
        out = Path("scripts/last_adversarial_run.json")
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"JSON saved: {out}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=[
        "casual", "ambiguous", "comparison", "refusal",
        "typo", "forecast_casual",
    ])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
