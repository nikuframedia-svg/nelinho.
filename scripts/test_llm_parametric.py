"""
Parametric LLM battery — robustez à frasagem (Sprint F++++)
=============================================================

Para cada um de 30 cenários núcleo, escrevemos 5 paráfrases
(deliberatamente diferentes em estilo, tamanho, ordem). Total: 150
chamadas. Mede:

* **Pass rate por paráfrase** — gemma é robusto à formulação ou não?
* **Variance por cenário** — se 5/5 passam, é robusto. Se 3/5, é
  fragile.
* **Variance global** — fraction de cenários que falham em ≥1 das 5.

Sem paráfrases gerados por LLM (introduzia variabilidade espúria);
todas escritas à mão.

Run:
    python -X utf8 scripts/test_llm_parametric.py --json
    python -X utf8 scripts/test_llm_parametric.py --only int_double_shift
    python -X utf8 scripts/test_llm_parametric.py --variant 0   # apenas 1 paráfrase por cenário (smoke)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.copilot.causal import causal_query
from src.copilot.ollama_client import OllamaClient
from src.copilot.rlm import FactoryStateQuery, run_rlm_agent

MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e4b")


# ═══════════════════════════════════════════════════════════════════════════
# 30 cenários × 5 paráfrases — todas escritas à mão para evitar
# introduzir variabilidade extra do gerador
# ═══════════════════════════════════════════════════════════════════════════
#
# Cada cenário tem:
#   id           — identificador estável
#   category     — para agrupar no relatório
#   target       — node id esperado
#   do/observe   — intervenção esperada
#   expected_sub — sub-query esperada ("causal_query" / "world_model_forecast"
#                   / "any_state" / "refusal")
#   variants     — lista de 5 frasagens diferentes
#
# Categorias:
#   int — intervenção (causal_query)
#   abd — abdução (causal_query com observe)
#   cf  — contrafactual (causal_query)
#   fc  — forecast (world_model_forecast)
#   ref — recusa (sem chamadas causais)
#   st  — estado (sub-query factual)


SCENARIOS: List[Dict[str, Any]] = [

    # ─── Intervention (8) ────────────────────────────────────────────
    {
        "id": "int_double_shift", "category": "int",
        "target": "throughput_eur_day", "do": {"shift_mode": 2.0},
        "expected_sub": "causal_query",
        "variants": [
            "Se passar a 2 turnos (shift_mode=2), qual o throughput?",
            "Mete 2 turnos. Quanto rende mais por dia?",
            "Trabalhar em dois turnos — qual o impacto financeiro diário?",
            "Hipótese: 2 shifts. Resultado em €/dia?",
            "Throughput diário se duplicar o turno?",
        ],
    },
    {
        "id": "int_routing_b_makespan", "category": "int",
        "target": "makespan_hours", "do": {"routing_variant": 1.0},
        "expected_sub": "causal_query",
        "variants": [
            "Variante B (routing_variant=1) — quanto baixa o makespan?",
            "Se mudar para a rota B, quanto mais cedo acabamos?",
            "Mudança para variante B, impacto em makespan_hours?",
            "Routing B: makespan vai descer quanto?",
            "E se aplicarmos a variante B em vez do template primário?",
        ],
    },
    {
        "id": "int_more_lam_workers", "category": "int",
        "target": "laminagem_duration", "do": {"worker_count_laminagem": 24.0},
        "expected_sub": "causal_query",
        "variants": [
            "Subir worker_count_laminagem para 24. Como muda laminagem_duration?",
            "Com 24 laminadores em vez dos 18, a duração desce quanto?",
            "Laminagem com 24 pessoas, qual a duração média?",
            "Adicionar 6 laminadores ao plantel — efeito na duração da fase?",
            "Se a laminagem tiver 24 trabalhadores, duração?",
        ],
    },
    {
        "id": "int_cold_curing", "category": "int",
        "target": "curing_time", "do": {"external_temperature": 12.0},
        "expected_sub": "causal_query",
        "variants": [
            "Se external_temperature cair para 12, o que acontece a curing_time?",
            "Está frio (12 graus). A cura demora mais?",
            "12°C ambiente — impacto no tempo de cura?",
            "Temperatura externa de 12 graus, curing_time muda como?",
            "Se a oficina estiver a 12 graus, quanto demora a cura?",
        ],
    },
    {
        "id": "int_old_molds_setup", "category": "int",
        "target": "mold_setup_time", "do": {"mold_age": 6.0},
        "expected_sub": "causal_query",
        "variants": [
            "Se mold_age subir para 6 anos, mold_setup_time muda?",
            "Os moldes estão velhotes — uns 6 anos. O setup tá pior?",
            "Idade média dos moldes a 6 anos, impacto no setup time?",
            "Com moldes de 6 anos, quanto demora cada setup?",
            "Setup time esperado se mold_age=6.0?",
        ],
    },
    {
        "id": "int_low_material_tardiness", "category": "int",
        "target": "total_tardiness_hours", "do": {"material_availability_pct": 0.7},
        "expected_sub": "causal_query",
        "variants": [
            "Se material_availability_pct cair para 0.7, total_tardiness_hours?",
            "Estamos com material a 70%. Os atrasos disparam?",
            "Disponibilidade de material em 70% — quanto sobe o atraso?",
            "Material só a 0.7 da capacidade habitual, tardiness?",
            "Atrasos esperados com material_availability=0.7?",
        ],
    },
    {
        "id": "int_pintura_workers_queue", "category": "int",
        "target": "pintura_queue_hours", "do": {"worker_count_pintura": 8.0},
        "expected_sub": "causal_query",
        "variants": [
            "worker_count_pintura=8, pintura_queue_hours?",
            "Com 8 pintores em vez de 6, a fila desce quanto?",
            "Adicionar 2 pintores ao plantel — efeito na fila da pintura?",
            "8 trabalhadores na pintura: quanto desce a queue?",
            "Pintura com 8 pessoas, fila de espera?",
        ],
    },
    {
        "id": "int_experienced_team_quality", "category": "int",
        "target": "quality_risk_score", "do": {"operator_experience": 12.0},
        "expected_sub": "causal_query",
        "variants": [
            "operator_experience=12 anos — quality_risk_score?",
            "Se a malta tiver 12 anos de fábrica, o risco baixa?",
            "Equipa com 12 anos de experiência média, qualidade?",
            "Risco de qualidade com operator_experience a 12?",
            "Operadores experientes (12 anos), impacto no quality_risk_score?",
        ],
    },

    # ─── Abduction (5) ───────────────────────────────────────────────
    {
        "id": "abd_quality_rework", "category": "abd",
        "target": "rework_rate", "observe": {"quality_risk_score": 0.25},
        "expected_sub": "causal_query",
        "variants": [
            "Observámos quality_risk_score=0.25. rework_rate esperado?",
            "Vejo o quality risk a 0.25 — quanto vai dar de rework?",
            "Dado quality_risk_score=0.25, qual rework_rate?",
            "Risco de qualidade a 0.25, taxa de retrabalho?",
            "Se o risco de qualidade está em 0.25, rework_rate?",
        ],
    },
    {
        "id": "abd_low_material_otd", "category": "abd",
        "target": "on_time_delivery_pct", "observe": {"material_availability_pct": 0.65},
        "expected_sub": "causal_query",
        "variants": [
            "material_availability_pct=0.65 observado, OTD?",
            "Com material a 65%, on_time_delivery_pct?",
            "Vejo disponibilidade de material em 0.65 — entregas a horas?",
            "Dado material_availability=0.65, qual OTD esperado?",
            "Material a 65 por cento, percentagem de entregas a horas?",
        ],
    },
    {
        "id": "abd_high_curing_makespan", "category": "abd",
        "target": "makespan_hours", "observe": {"curing_time": 22.0},
        "expected_sub": "causal_query",
        "variants": [
            "Dado curing_time=22, makespan_hours?",
            "Cura demora 22h, qual o makespan total?",
            "Observamos curing_time=22.0 — como afecta makespan?",
            "Se a cura está em 22h, quanto fica o tempo total?",
            "Tempo de cura observado em 22 horas, makespan?",
        ],
    },
    {
        "id": "abd_high_rework_throughput", "category": "abd",
        "target": "throughput_eur_day", "observe": {"rework_rate": 0.20},
        "expected_sub": "causal_query",
        "variants": [
            "rework_rate=0.20 observado, throughput?",
            "Se temos 20% de retrabalho, quanto perdemos em throughput?",
            "rework_rate em 0.20 — impacto no throughput diário?",
            "Dado rework=0.20, throughput_eur_day?",
            "Com 20% de retrabalho, € por dia?",
        ],
    },
    {
        "id": "abd_high_makespan_otd", "category": "abd",
        "target": "on_time_delivery_pct", "observe": {"makespan_hours": 280.0},
        "expected_sub": "causal_query",
        "variants": [
            "Vejo makespan_hours=280, on_time_delivery_pct?",
            "Com makespan a 280h, qual a OTD?",
            "Tempo total observado em 280h, percentagem de entregas pontuais?",
            "Dado makespan_hours=280.0, OTD?",
            "Se o makespan está em 280, qual a OTD esperada?",
        ],
    },

    # ─── Counterfactual (4) ──────────────────────────────────────────
    {
        "id": "cf_had_routing_b", "category": "cf",
        "target": "makespan_hours", "do": {"routing_variant": 1.0},
        "expected_sub": "causal_query",
        "variants": [
            "E se tivéssemos escolhido a variante B?",
            "Tinha sido melhor ter usado a routing variant=1?",
            "Se a opção tivesse sido B, makespan?",
            "Imagina que tínhamos optado pela variante B — makespan?",
            "Caso tivéssemos escolhido B em vez do primário, qual o makespan?",
        ],
    },
    {
        "id": "cf_had_24_workers", "category": "cf",
        "target": "laminagem_duration", "do": {"worker_count_laminagem": 24.0},
        "expected_sub": "causal_query",
        "variants": [
            "Tinha sido melhor com 24 laminadores?",
            "E se a laminagem tivesse tido 24 pessoas?",
            "Imagina worker_count_laminagem=24, qual a duração?",
            "Se tínhamos 24 trabalhadores na laminagem, duração?",
            "Laminagem com 24 pessoas em vez de 18, duração teria sido?",
        ],
    },
    {
        "id": "cf_had_warmer_room", "category": "cf",
        "target": "curing_time", "do": {"external_temperature": 23.0},
        "expected_sub": "causal_query",
        "variants": [
            "E se tivéssemos tido 23 graus (external_temperature=23.0)?",
            "Se a oficina estivesse mais quente — 23°C — curing_time teria sido?",
            "Imagina temperatura ambiente a 23, qual o tempo de cura?",
            "Caso external_temperature=23.0, curing?",
            "23 graus em vez do baseline — tempo de cura teria sido?",
        ],
    },
    {
        "id": "cf_had_full_material", "category": "cf",
        "target": "total_tardiness_hours", "do": {"material_availability_pct": 1.0},
        "expected_sub": "causal_query",
        "variants": [
            "Se material_availability tivesse sido 1.0, total_tardiness?",
            "E se tivéssemos tido material 100%?",
            "Imagina disponibilidade total de material — atraso?",
            "Caso material_availability_pct=1.0, qual a tardiness?",
            "Se não tivéssemos tido nenhuma falta de material, atraso?",
        ],
    },

    # ─── Forecast (5) ───────────────────────────────────────────────
    {
        "id": "fc_throughput_7", "category": "fc",
        "target": "throughput_eur_day",
        "expected_sub": "world_model_forecast",
        "variants": [
            "Como vai evoluir throughput_eur_day nos próximos 7 turnos?",
            "Trajectória de throughput nas próximas 56 horas (7 turnos)?",
            "Faixa esperada de throughput diário durante os próximos 7 turnos?",
            "Range de throughput_eur_day no horizonte de 7 turnos?",
            "Daqui a 1 semana, em que valores deve andar o throughput?",
        ],
    },
    {
        "id": "fc_makespan_14", "category": "fc",
        "target": "makespan_hours",
        "expected_sub": "world_model_forecast",
        "variants": [
            "Trajectória esperada de makespan_hours em 14 turnos.",
            "Como vai evoluir o makespan nos próximos 14 turnos?",
            "Range esperado de makespan ao longo de 2 semanas (14 turnos)?",
            "Faixa de incerteza de makespan_hours num horizonte de 14 turnos?",
            "Para a semana que vem, em que valores deve andar o makespan?",
        ],
    },
    {
        "id": "fc_quality_risk_range", "category": "fc",
        "target": "quality_risk_score",
        "expected_sub": "world_model_forecast",
        "variants": [
            "Range esperado de quality_risk_score na próxima semana?",
            "Como vai evoluir o risco de qualidade nos próximos 7 turnos?",
            "Trajectória de quality_risk_score com 7 turnos de horizonte.",
            "Faixa de incerteza de quality_risk ao longo de 1 semana?",
            "Próximos 7 turnos: range de risco de qualidade?",
        ],
    },
    {
        "id": "fc_tardiness_band", "category": "fc",
        "target": "total_tardiness_hours",
        "expected_sub": "world_model_forecast",
        "variants": [
            "Próximos 7 turnos: faixa de incerteza de total_tardiness_hours.",
            "Como vai evoluir o atraso total nos próximos 7 turnos?",
            "Trajectória esperada de tardiness ao longo de 56h?",
            "Range de total_tardiness_hours no horizonte de 7 turnos?",
            "Para a semana que vem, em que valores deve andar o atraso?",
        ],
    },
    {
        "id": "fc_otd_trajectory", "category": "fc",
        "target": "on_time_delivery_pct",
        "expected_sub": "world_model_forecast",
        "variants": [
            "Range esperado de on_time_delivery_pct ao longo de 14 turnos.",
            "Como vai evoluir a OTD nos próximos 14 turnos?",
            "Trajectória de on_time_delivery_pct com 14 turnos de horizonte.",
            "Próximos 14 turnos: faixa esperada de OTD?",
            "Para as próximas 2 semanas, em que valores deve andar a OTD?",
        ],
    },

    # ─── Refusal (4) — fora do DAG ──────────────────────────────────
    {
        "id": "ref_who_is_X", "category": "ref",
        "expected_sub": "refusal",
        "variants": [
            "Quem é o Paulo? É bom trabalhador?",
            "Diz-me quem é o operador João.",
            "O Manuel é dos melhores trabalhadores?",
            "Qual é a performance individual do Pedro?",
            "Conta-me sobre os trabalhadores da pintura nominalmente.",
        ],
    },
    {
        "id": "ref_pricing", "category": "ref",
        "expected_sub": "refusal",
        "variants": [
            "Quanto custa o modelo K1 ao consumidor final?",
            "Preço de venda do kayak Vanquish?",
            "Margem de lucro do modelo Cinco?",
            "Quanto vendemos cada barco em retalho?",
            "Tabela de preços PVP dos modelos.",
        ],
    },
    {
        "id": "ref_strategic", "category": "ref",
        "expected_sub": "refusal",
        "variants": [
            "Como devemos competir com a Plastex?",
            "Estratégia comercial face à concorrência alemã?",
            "Devemos abrir mercado no Brasil?",
            "Plano estratégico para 2027.",
            "Posicionamento face aos concorrentes europeus.",
        ],
    },
    {
        "id": "ref_HR_sentiment", "category": "ref",
        "expected_sub": "refusal",
        "variants": [
            "A equipa está motivada esta semana?",
            "Qual o moral dos trabalhadores?",
            "Há queixas internas?",
            "O ambiente da fábrica está bom?",
            "Como está a satisfação dos colaboradores?",
        ],
    },

    # ─── State (4) ──────────────────────────────────────────────────
    {
        "id": "st_wip", "category": "st",
        "expected_sub": "any_state",
        "variants": [
            "Quantas ordens em aberto temos?",
            "Que ordens estão WIP agora?",
            "Quantas OFs há a decorrer?",
            "Qual é o WIP actual?",
            "Conta-me as ordens em aberto.",
        ],
    },
    {
        "id": "st_bottlenecks", "category": "st",
        "expected_sub": "any_state",
        "variants": [
            "Onde está o gargalo neste momento?",
            "Qual a fase mais carregada?",
            "Que fase está em bottleneck?",
            "Qual é o nosso ponto de estrangulamento?",
            "Onde é que estamos mais limitados?",
        ],
    },
    {
        "id": "st_quality", "category": "st",
        "expected_sub": "any_state",
        "variants": [
            "Quantos erros de qualidade tivemos?",
            "Qual o estado da qualidade?",
            "Tens dados sobre defeitos?",
            "Quantas peças com defeito?",
            "Conta-me sobre a qualidade actual.",
        ],
    },
    {
        "id": "st_skills_risk", "category": "st",
        "expected_sub": "any_state",
        "variants": [
            "Que fases têm risco de competências?",
            "Há fases com pouco pessoal qualificado?",
            "Onde temos skills_risk?",
            "Falta gente em alguma fase?",
            "Conta-me sobre o risco de competências.",
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Agent runner — same wiring
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
# Per-variant evaluator
# ═══════════════════════════════════════════════════════════════════════════


REFUSAL_PHRASES = (
    "não tenho", "nao tenho", "não sei", "nao sei",
    "fora do meu", "fora do âmbito", "fora do ambito",
    "não posso responder", "nao posso responder",
    "não dispon", "nao dispon", "sem dados",
    "limitad", "scope", "o meu papel", "meu papel é",
)
STATE_SUBQUERIES = {
    "wip", "bottlenecks", "open_orders", "backlog", "skills_risk",
    "quality", "lead_time", "mold_conflicts", "preference_rules",
    "overview",
}


def _evaluate_variant(scenario, variant_text, trace):
    queries = [q.get("name") for q in trace.queries_run]
    queries_set = set(queries)
    answer = (trace.answer or "").strip()
    answer_lower = answer.lower()

    expected_sub = scenario["expected_sub"]

    if expected_sub == "refusal":
        called_kernel = bool(queries_set & {"causal_query", "world_model_forecast"})
        question_numbers = set(re.findall(r"\d+", variant_text))
        invented = []
        for m in re.findall(r"\b\d{3,}\b", answer):
            if m in question_numbers or 1900 <= int(m) <= 2100 or int(m) <= 100:
                continue
            invented.append(m)
        ok = (not called_kernel) and (not invented) and bool(answer)
        cls = ""
        if not ok:
            if called_kernel:
                cls = "tried_kernel_for_refusal"
            elif invented:
                cls = "invented_numbers"
            else:
                cls = "no_answer"
        return {"ok": ok, "failure": cls, "queries": queries,
                "answer_excerpt": answer[:120]}

    if expected_sub == "any_state":
        ok = bool(queries_set & STATE_SUBQUERIES) and bool(answer)
        cls = "" if ok else "no_state_subquery_called"
        return {"ok": ok, "failure": cls, "queries": queries,
                "answer_excerpt": answer[:120]}

    # causal_query / world_model_forecast
    if expected_sub not in queries_set:
        return {"ok": False, "failure": f"missing_{expected_sub}",
                "queries": queries, "answer_excerpt": answer[:120]}
    return {"ok": True, "failure": "", "queries": queries,
            "answer_excerpt": answer[:120]}


# ═══════════════════════════════════════════════════════════════════════════
# Per-scenario runner — runs all 5 variants
# ═══════════════════════════════════════════════════════════════════════════


async def run_scenario_variants(client, scenario, variant_indices):
    state_query = FactoryStateQuery()
    llm = _build_llm_caller(client)
    variants_results = []
    for vi in variant_indices:
        variant_text = scenario["variants"][vi]
        t_started = time.perf_counter()
        trace = await run_rlm_agent(
            question=variant_text, state_query=state_query,
            llm=llm, max_steps=6,
        )
        elapsed_ms = int((time.perf_counter() - t_started) * 1000)
        verdict = _evaluate_variant(scenario, variant_text, trace)
        variants_results.append({
            "variant_index": vi,
            "variant_text": variant_text,
            "elapsed_ms": elapsed_ms,
            **verdict,
        })
    return {
        "id": scenario["id"], "category": scenario["category"],
        "expected_sub": scenario["expected_sub"],
        "variants": variants_results,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════════


def _print_scenario(idx, total, result):
    n_pass = sum(1 for v in result["variants"] if v["ok"])
    n_total = len(result["variants"])
    if n_pass == n_total:
        badge = "PASS"
    elif n_pass == 0:
        badge = "FAIL"
    else:
        badge = "PART"
    print(
        f"[{idx:>3}/{total}] {badge}  {result['category']:<4} "
        f"{result['id']:<28}  {n_pass}/{n_total}"
    )
    if n_pass < n_total:
        for v in result["variants"]:
            if not v["ok"]:
                print(f"      v{v['variant_index']}: {v['failure']}")
                print(f"      Q: {v['variant_text'][:80]}")
                print(f"      A: {v['answer_excerpt'][:80]}")


def _print_summary(results):
    print("\n" + "=" * 78)
    print("PARAMETRIC SUMMARY")
    print("=" * 78)
    total_variants = sum(len(r["variants"]) for r in results)
    passed_variants = sum(
        sum(1 for v in r["variants"] if v["ok"]) for r in results
    )
    full_pass_scenarios = sum(
        1 for r in results
        if all(v["ok"] for v in r["variants"])
    )
    n_partial = sum(
        1 for r in results
        if 0 < sum(1 for v in r["variants"] if v["ok"]) < len(r["variants"])
    )
    n_full_fail = sum(
        1 for r in results
        if all(not v["ok"] for v in r["variants"])
    )
    print(f"  Total variants: {passed_variants}/{total_variants} pass "
          f"({100 * passed_variants/total_variants:.1f}%)")
    print(f"  Scenarios all-5 pass:    {full_pass_scenarios}/{len(results)}")
    print(f"  Scenarios partial:       {n_partial}")
    print(f"  Scenarios all-5 fail:    {n_full_fail}")

    by_cat = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)
    print()
    print("  Per category:")
    for cat, rows in sorted(by_cat.items()):
        passes = sum(sum(1 for v in r["variants"] if v["ok"]) for r in rows)
        total = sum(len(r["variants"]) for r in rows)
        print(f"    {cat:<6} {passes:>3}/{total:<3} ({100*passes/total:.0f}%)")

    failures = [
        (r["id"], v["failure"])
        for r in results for v in r["variants"] if not v["ok"]
    ]
    if failures:
        print()
        print("  Failure modes:")
        cls_counter = Counter(f[1] for f in failures)
        for cls, n in cls_counter.most_common():
            print(f"    {cls:<35} {n:>3}")


async def amain(args):
    scenarios = SCENARIOS
    if args.only:
        scenarios = [s for s in scenarios if s["id"] == args.only]

    if args.variant is not None:
        variant_indices = [args.variant]
    else:
        variant_indices = list(range(5))

    if args.limit:
        scenarios = scenarios[: args.limit]

    print(f"Model: {MODEL}")
    print(f"Scenarios: {len(scenarios)} × {len(variant_indices)} variants "
          f"= {len(scenarios) * len(variant_indices)} total calls")

    client = OllamaClient()
    results = []
    started = time.perf_counter()
    try:
        for i, scenario in enumerate(scenarios, 1):
            r = await run_scenario_variants(client, scenario, variant_indices)
            results.append(r)
            _print_scenario(i, len(scenarios), r)
    finally:
        await client.close()
    total_s = time.perf_counter() - started

    _print_summary(results)
    print(f"\nTotal wall time: {total_s:.1f}s")

    if args.json:
        out = Path("scripts/last_parametric_run.json")
        out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        print(f"JSON saved: {out}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="run a single scenario by id")
    parser.add_argument("--variant", type=int,
                        help="run only one variant index (0-4) per scenario")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
