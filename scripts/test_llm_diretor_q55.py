"""
Q.55 — 80 prompts ao copiloto, avaliação tripla (SCM + verify_chain + DoWhy)
==============================================================================

Vista de diretor industrial: 80 perguntas operacionais misturadas — porquês
causais, status de fábrica, previsões, e "o que devo fazer". Cada uma passa
pelo copiloto real (`gemma4:e4b`, o mesmo modelo que os operadores usam) e é
avaliada por TRÊS juízes independentes:

  1. SCM da casa (`causal_query`)  — a verdade-base determinística do NELO_DAG.
  2. `verify_chain` (5 camadas)    — o portão de coerência que já está em prod.
  3. DoWhy 0.14                    — estimativa estatística + 3 refutadores,
                                     a partir de dados sintéticos do SCM.

Um prompt causal só conta como "verde a sério" quando os três concordam:
o copiloto passou o portão E o DoWhy confirma a direção E os refutadores
não derrubam a relação.

Correr:

    python scripts/test_llm_diretor_q55.py            # 80 prompts
    python scripts/test_llm_diretor_q55.py --limit 10 # debug
    python scripts/test_llm_diretor_q55.py --json     # dump máquina
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Consola Windows é cp1252 — força UTF-8 para os acentos PT-PT não saírem
# mangled. O JSON já é gravado em UTF-8 explícito.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.copilot.causal import causal_query, verify_chain_dict
from src.copilot.causal.nelo_dag import NODES_BY_ID
from src.copilot.ollama_client import OllamaClient
from src.copilot.rlm import FactoryStateQuery, run_rlm_agent

# Reaproveita a maquinaria já testada da bateria massiva.
from scripts.test_llm_massive import (
    MODEL,
    SCENARIOS as _MASSIVE_SCENARIOS,
    _build_llm_caller,
    _compose_chain,
    _extract_kernel,
)
from scripts.dowhy_nelo_q55 import dowhy_table


# ═══════════════════════════════════════════════════════════════════════════
# Bateria — 54 cenários da massiva + 26 operacionais novos = 80
# ═══════════════════════════════════════════════════════════════════════════


def _intervention(name, q, target, do):
    return {"name": name, "category": "intervention", "question": q,
            "expected_target": target, "expected_do": do, "needs_kernel": True}


def _abduction(name, q, target, observe):
    return {"name": name, "category": "abduction", "question": q,
            "expected_target": target, "expected_observe": observe, "needs_kernel": True}


def _counterfactual(name, q, target, do):
    return {"name": name, "category": "counterfactual", "question": q,
            "expected_target": target, "expected_do": do, "needs_kernel": True}


def _state(name, q, sub_query):
    return {"name": name, "category": "state", "question": q,
            "expected_subquery": sub_query, "needs_kernel": False}


def _recommendation(name, q, levers):
    """Pergunta aberta de decisão. `levers` = palavras-chave que uma resposta
    útil tem de citar (alavancas concretas, não generalidades)."""
    return {"name": name, "category": "recommendation", "question": q,
            "expected_levers": levers, "needs_kernel": False}


_EXTRA_SCENARIOS: List[Dict[str, Any]] = [
    # ─── Intervention extra (4) ───────────────────────────────────────────
    _intervention("int_routing_tardiness",
        "Se mudarmos para a variante B (routing_variant=1), o que acontece a total_tardiness_hours?",
        "total_tardiness_hours", {"routing_variant": 1.0}),
    _intervention("int_double_shift_makespan",
        "Com 2 turnos (shift_mode=2), como muda makespan_hours?",
        "makespan_hours", {"shift_mode": 2.0}),
    _intervention("int_full_material_throughput",
        "Se material_availability_pct subir para 1.0, o que acontece a throughput_eur_day?",
        "throughput_eur_day", {"material_availability_pct": 1.0}),
    _intervention("int_new_molds_setup",
        "Se mold_age médio cair para 1 ano, como muda mold_setup_time?",
        "mold_setup_time", {"mold_age": 1.0}),

    # ─── Abduction extra (3) ──────────────────────────────────────────────
    _abduction("abd_high_curing_otd",
        "Observámos curing_time=21h. Como afecta on_time_delivery_pct?",
        "on_time_delivery_pct", {"curing_time": 21.0}),
    _abduction("abd_low_lam_workers_queue",
        "Vejo worker_count_laminagem=15. Que esperar para laminagem_queue_hours?",
        "laminagem_queue_hours", {"worker_count_laminagem": 15.0}),
    _abduction("abd_high_pintura_dur_queue",
        "pintura_duration=4.5h observado — impacto em pintura_queue_hours?",
        "pintura_queue_hours", {"pintura_duration": 4.5}),

    # ─── Counterfactual extra (3) ─────────────────────────────────────────
    _counterfactual("cf_had_cold_room",
        "E se a temperatura tivesse sido 12°C (external_temperature=12)? quality_risk_score teria mudado?",
        "quality_risk_score", {"external_temperature": 12.0}),
    _counterfactual("cf_had_22_lam",
        "Tinha sido melhor 22 laminadores (worker_count_laminagem=22)? laminagem_queue_hours?",
        "laminagem_queue_hours", {"worker_count_laminagem": 22.0}),
    _counterfactual("cf_had_low_material_otd",
        "Se material_availability_pct tivesse sido 0.75, on_time_delivery_pct teria sido?",
        "on_time_delivery_pct", {"material_availability_pct": 0.75}),

    # ─── State extra (8) — frasear como um chefe de turno fala ────────────
    _state("st_gargalo_agora", "Qual é a fase mais apertada hoje?", "bottlenecks"),
    _state("st_ordens_risco", "Temos ordens em risco de atraso?", "open_orders"),
    _state("st_competencias", "Falta gente com competências nalguma fase?", "skills_risk"),
    _state("st_defeitos_semana", "Quantos defeitos apanhámos esta semana?", "quality"),
    _state("st_wip_total", "Quanto trabalho em curso temos na fábrica?", "wip"),
    _state("st_ponto_situacao", "Dá-me o ponto de situação geral da fábrica.", "overview"),
    _state("st_lead_barco", "Quanto tempo leva um barco de ponta a ponta?", "lead_time"),
    _state("st_regras_ligadas", "Que regras automáticas estão ligadas neste momento?", "preference_rules"),

    # ─── Recommendation (8) — decisões abertas de diretor ─────────────────
    _recommendation("rec_baixar_makespan",
        "O que devo fazer para baixar o makespan?",
        ["turno", "laminag", "routing", "variante", "molde", "cura"]),
    _recommendation("rec_subir_throughput",
        "Como subo a faturação por dia na fábrica?",
        ["turno", "material", "retrabalho", "routing", "variante"]),
    _recommendation("rec_menos_retrabalho",
        "O que reduz o retrabalho na fábrica?",
        ["experi", "temperatura", "qualidade", "molde", "laminador"]),
    _recommendation("rec_melhor_otd",
        "Como melhoro a entrega no prazo das encomendas?",
        ["atraso", "tardiness", "material", "makespan", "retrabalho"]),
    _recommendation("rec_gargalo_laminagem",
        "A Laminagem está a estrangular a linha. O que faço?",
        ["laminador", "worker", "turno", "fila", "routing", "variante"]),
    _recommendation("rec_cura_lenta",
        "A cura está lenta e a atrasar tudo. O que ataco primeiro?",
        ["temperatura", "cura", "curing", "aquec"]),
    _recommendation("rec_poucos_moldes",
        "Tenho poucos moldes disponíveis. Que decisão tomo?",
        ["molde", "disponib", "setup", "manuten"]),
    _recommendation("rec_segundo_turno",
        "Vale a pena abrir um segundo turno?",
        ["turno", "shift", "throughput", "faturação", "custo"]),
]

SCENARIOS: List[Dict[str, Any]] = list(_MASSIVE_SCENARIOS) + _EXTRA_SCENARIOS


# ═══════════════════════════════════════════════════════════════════════════
# Pares causa→efeito para a tabela DoWhy
# ═══════════════════════════════════════════════════════════════════════════


def _scenario_pair(s: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """Par (causa, efeito) de um cenário causal de tratamento único.

    Multi-step (vários `do`) fica de fora — o DoWhy estima um tratamento de
    cada vez. Esses são julgados só pelo SCM + verify_chain.
    """
    if not s.get("needs_kernel"):
        return None
    src = s.get("expected_do") or s.get("expected_observe") or {}
    if len(src) != 1:
        return None
    treatment = next(iter(src.keys()))
    return (treatment, s["expected_target"])


# ═══════════════════════════════════════════════════════════════════════════
# Avaliação de um cenário
# ═══════════════════════════════════════════════════════════════════════════


def _sign(x: float) -> int:
    if x > 1e-6:
        return 1
    if x < -1e-6:
        return -1
    return 0


def _judge_dowhy(
    scenario: Dict[str, Any],
    scm_delta: float,
    dowhy_row: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Cruza a previsão DoWhy com o delta do SCM da casa.

    DoWhy dá um efeito por unidade de tratamento (ATE). O cenário fixa um
    valor concreto, então a previsão DoWhy é ATE × (valor − baseline). O
    veredicto é sobre a DIREÇÃO e a ORDEM DE GRANDEZA — o SCM tem chãos/tectos
    não-lineares, uma estimativa linear nunca bate ao cêntimo.
    """
    out: Dict[str, Any] = {
        "available": False, "direction_agrees": None,
        "magnitude_ok": None, "refuters_confirmed": None,
        "ate": None, "predicted_delta": None,
    }
    if dowhy_row is None or dowhy_row.get("error"):
        out["note"] = (dowhy_row or {}).get("error", "par não coberto pelo DoWhy")
        return out
    ate = dowhy_row.get("ate")
    if not isinstance(ate, float):
        out["note"] = "DoWhy sem estimativa"
        return out

    src = scenario.get("expected_do") or scenario.get("expected_observe") or {}
    treatment = next(iter(src.keys()))
    value = float(src[treatment])
    baseline = float(NODES_BY_ID[treatment].baseline)
    predicted = ate * (value - baseline)

    out["available"] = True
    out["ate"] = round(ate, 5)
    out["predicted_delta"] = round(predicted, 4)
    out["refuters_confirmed"] = bool(dowhy_row.get("confirmed"))
    out["direction_agrees"] = (_sign(predicted) == _sign(scm_delta))
    # Ordem de grandeza: rácio entre 0.33× e 3× quando ambos são não-triviais.
    if abs(scm_delta) < 1e-6:
        out["magnitude_ok"] = abs(predicted) < 1e-6
    elif abs(predicted) < 1e-9:
        out["magnitude_ok"] = False
    else:
        ratio = abs(predicted) / abs(scm_delta)
        out["magnitude_ok"] = 0.33 <= ratio <= 3.0
    return out


async def run_one(
    client: OllamaClient,
    scenario: Dict[str, Any],
    dowhy_lookup: Dict[Tuple[str, str], Dict[str, Any]],
) -> Dict[str, Any]:
    started = time.perf_counter()
    trace = await run_rlm_agent(
        question=scenario["question"], state_query=FactoryStateQuery(),
        llm=_build_llm_caller(client), max_steps=6,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    queries = [q.get("name") for q in trace.queries_run]
    answer = trace.answer or ""
    cat = scenario["category"]

    base = {
        "name": scenario["name"], "category": cat, "question": scenario["question"],
        "elapsed_ms": elapsed_ms, "queries_run": queries,
        "terminated": trace.terminated_reason, "answer_excerpt": answer[:200],
    }

    # ── State: chamou a sub-query certa + respondeu? ──────────────────────
    if cat == "state":
        expected_sq = scenario.get("expected_subquery")
        ok = (expected_sq in queries) and bool(answer)
        base.update({"ok": ok, "verdict": "verify_chain n/a (factual)",
                     "failure": "" if ok else f"esperava sub-query {expected_sq!r}, usou {queries}"})
        return base

    # ── Forecast: chamou o world_model_forecast + citou incerteza? ────────
    if cat == "forecast":
        expected_sq = scenario.get("expected_subquery", "world_model_forecast")
        called = expected_sq in queries
        low = answer.lower()
        cites_uncertainty = any(t in low for t in (
            "p50", "p95", "p05", "traject", "trajet", "intervalo",
            "incerteza", "range", "faixa", "evoluir", "previs", "horizonte"))
        ok = called and bool(answer) and cites_uncertainty
        fail = ""
        if not called:
            fail = f"não chamou {expected_sq}"
        elif not cites_uncertainty:
            fail = "resposta sem faixa de incerteza"
        base.update({"ok": ok, "verdict": "previsão", "failure": fail})
        return base

    # ── Recommendation: respondeu e citou alavancas concretas? ────────────
    if cat == "recommendation":
        low = answer.lower()
        levers = scenario.get("expected_levers", [])
        hits = [lv for lv in levers if lv in low]
        ok = bool(answer) and len(hits) >= 1
        base.update({"ok": ok, "verdict": "recomendação",
                     "levers_hit": hits,
                     "failure": "" if ok else "resposta sem alavanca concreta"})
        return base

    # ── Causal: SCM (verdade) + verify_chain (portão) + DoWhy (2.º juiz) ──
    kernel = _extract_kernel(trace)
    expected = causal_query(
        scenario["expected_target"],
        do=scenario.get("expected_do") or {},
        observe=scenario.get("expected_observe") or {},
    )
    chain = _compose_chain(trace, scenario)
    verify_passed, coherence, layer_summary = False, 0.0, {}
    if chain is not None:
        verdict = verify_chain_dict(chain, kernel_result=kernel)
        verify_passed = verdict.passed
        coherence = round(verdict.coherence, 3)
        layer_summary = {l.name: {"score": round(l.score, 3), "passed": l.passed}
                         for l in verdict.layers}

    pair = _scenario_pair(scenario)
    dowhy_row = dowhy_lookup.get(pair) if pair else None
    dowhy = _judge_dowhy(scenario, expected.delta, dowhy_row)

    # "Verde a sério": portão passou E (se o DoWhy cobre) os 3 juízes alinham.
    triple_green = verify_passed
    if dowhy["available"]:
        triple_green = (
            verify_passed
            and bool(dowhy["direction_agrees"])
            and bool(dowhy["refuters_confirmed"])
        )

    fail = ""
    if not verify_passed:
        if chain is None:
            fail = "copiloto não produziu cadeia causal"
        else:
            fail = "verify_chain reprovou (coerência < portão)"
    elif dowhy["available"] and not dowhy["direction_agrees"]:
        fail = "DoWhy discorda da direção do SCM"
    elif dowhy["available"] and not dowhy["refuters_confirmed"]:
        fail = "refutadores DoWhy derrubaram a relação"

    base.update({
        "ok": triple_green,
        "verify_passed": verify_passed,
        "coherence": coherence,
        "scm_delta": round(expected.delta, 4),
        "kernel_delta": round(kernel.delta, 4) if kernel else None,
        "layers": layer_summary,
        "dowhy": dowhy,
        "failure": fail,
        "verdict": "tripla",
    })
    return base


# ═══════════════════════════════════════════════════════════════════════════
# Relatório de diretor
# ═══════════════════════════════════════════════════════════════════════════


def _print_row(r: Dict[str, Any], idx: int, total: int) -> None:
    mark = "PASS" if r["ok"] else "FAIL"
    cat = r["category"][:6]
    extra = ""
    if r["category"] in ("intervention", "abduction", "counterfactual", "multistep"):
        coh = r.get("coherence", 0.0)
        dw = r.get("dowhy", {})
        dws = "—"
        if dw.get("available"):
            dws = "DoWhy:dir+" if dw.get("direction_agrees") else "DoWhy:dir-"
            if not dw.get("refuters_confirmed"):
                dws += "/ref-"
        extra = f"coh={coh} {dws}"
    elif r["category"] == "recommendation":
        extra = f"alavancas={r.get('levers_hit', [])}"
    print(f"  [{idx:>3}/{total}] {mark}  {cat:<7} {r['name'][:30]:<32} "
          f"({r['elapsed_ms']:>6}ms)  {extra}")
    if not r["ok"] and r.get("failure"):
        print(f"            └─ {r['failure']}")


def _summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in results:
        by_cat[r["category"]].append(r)

    print("\n" + "=" * 78)
    print("RESUMO PARA O DIRETOR")
    print("=" * 78)
    for cat, rows in sorted(by_cat.items()):
        passed = sum(1 for r in rows if r["ok"])
        avg_ms = sum(r["elapsed_ms"] for r in rows) // max(1, len(rows))
        print(f"  {cat:<16} {passed:>2}/{len(rows):<2}   ({avg_ms} ms/pergunta)")

    total_pass = sum(1 for r in results if r["ok"])
    print(f"\n  TOTAL: {total_pass}/{len(results)} prompts verdes")

    causal = [r for r in results
              if r["category"] in ("intervention", "abduction", "counterfactual", "multistep")]
    with_dw = [r for r in causal if r.get("dowhy", {}).get("available")]
    dir_ok = sum(1 for r in with_dw if r["dowhy"].get("direction_agrees"))
    mag_ok = sum(1 for r in with_dw if r["dowhy"].get("magnitude_ok"))
    ref_ok = sum(1 for r in with_dw if r["dowhy"].get("refuters_confirmed"))
    vc_ok = sum(1 for r in causal if r.get("verify_passed"))
    print()
    print(f"  Pipeline causal ({len(causal)} prompts causais):")
    print(f"    verify_chain (portão da casa) ...... {vc_ok}/{len(causal)}")
    if with_dw:
        print(f"    DoWhy cobre ........................ {len(with_dw)} pares")
        print(f"    DoWhy concorda na direção .......... {dir_ok}/{len(with_dw)}")
        print(f"    DoWhy concorda na grandeza (±3×) ... {mag_ok}/{len(with_dw)}")
        print(f"    DoWhy refutadores confirmam ........ {ref_ok}/{len(with_dw)}")

    failures = [r for r in results if not r["ok"]]
    if failures:
        print("\n  Falhas (classe -> nº):")
        for cls, n in Counter(r.get("failure", "?") for r in failures).most_common():
            print(f"    {cls:<46} {n}")

    return {
        "total": len(results), "total_pass": total_pass,
        "by_category": {cat: {"pass": sum(1 for r in rows if r["ok"]), "n": len(rows)}
                        for cat, rows in by_cat.items()},
        "causal": {"n": len(causal), "verify_chain_pass": vc_ok,
                   "dowhy_covered": len(with_dw), "dowhy_direction": dir_ok,
                   "dowhy_magnitude": mag_ok, "dowhy_refuters": ref_ok},
    }


# ═══════════════════════════════════════════════════════════════════════════
# Entry
# ═══════════════════════════════════════════════════════════════════════════


async def amain(args) -> int:
    scenarios = SCENARIOS[: args.limit] if args.limit else SCENARIOS

    pairs = [p for p in (_scenario_pair(s) for s in scenarios) if p]
    print(f"Modelo do copiloto: {MODEL}")
    print(f"Prompts: {len(scenarios)}")
    print(f"\n[1/2] DoWhy — dataset sintético do NELO_DAG + {len(set(pairs))} pares causais")
    print("-" * 78)
    dowhy_lookup = dowhy_table(pairs, n=4000, seed=55) if pairs else {}

    print(f"\n[2/2] Copiloto — {len(scenarios)} prompts pelo loop do agente RLM")
    print("-" * 78)
    client = OllamaClient()
    results: List[Dict[str, Any]] = []
    started = time.perf_counter()
    try:
        for i, scenario in enumerate(scenarios, 1):
            r = await run_one(client, scenario, dowhy_lookup)
            results.append(r)
            _print_row(r, i, len(scenarios))
    finally:
        await client.close()
    wall = time.perf_counter() - started

    summary = _summary(results)
    print(f"\n  Tempo total do copiloto: {wall:.0f}s")

    out = Path("scripts/last_diretor_q55_run.json")
    out.write_text(json.dumps(
        {"model": MODEL, "summary": summary,
         "dowhy_table": {f"{t}->{o}": v for (t, o), v in dowhy_lookup.items()},
         "results": results},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  JSON: {out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="limitar a N prompts (debug)")
    parser.add_argument("--json", action="store_true", help="(sempre grava JSON)")
    args = parser.parse_args()
    return asyncio.run(amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
