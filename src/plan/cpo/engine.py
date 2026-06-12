"""
ProdPlan ONE — CPO v4 Engine
=============================

Orchestrates: baseline greedy → GA exploration → safety net → result.

Implements `SchedulingAdapter`-compatible output (`SchedulingResult` dict)
so callers can swap it in via `adapter.configure(engine=SchedulerEngine.CPO_V4)`.

Sprint E scope: permutation GA with 3 mutation operators, OX crossover,
population 100, generations 50.
Sprint F scope: FRRMAB-driven operator selection (6 ops), MAP-Elites 3D
archive for diversity-preserving elitism, surrogate-model skip filter,
and stagnation restart. All four features are gated by `CPOConfig` flags
so Sprint E tests keep their exact behaviour when flags are left off.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.plan.cpo.chromosome import Chromosome
from src.plan.cpo.decoder import decode
from src.plan.cpo.fitness import (
    _NORM_IDLE_H,
    _NORM_MAKESPAN_H,
    _NORM_TARDINESS_H,
    FitnessConfig,
    compute_fitness,
)
from src.plan.cpo.frrmab import FRRMAB
from src.plan.cpo.greedy_pipeline import GreedyPipeline, PHASE_BUDGETS_S
from src.plan.cpo.mapelites import MAPElites3D
from src.plan.cpo.safety_net import _gather_violations, apply_safety_net
from src.plan.cpo.state import FactoryState
from src.plan.cpo.surrogate import CPOSurrogateLayer
from src.plan.engines.scheduling_adapter import SchedulingMachine, SchedulingOperation
from src.shared.time import utc_now_naive

logger = logging.getLogger(__name__)


# Sprint P.8/P.9 decoder defaults — match `planning.queue_time.median_h` and
# `planning.buffer.post_desmolde_h` seeded in Sprint L.4.
_DECODER_QUEUE_TIME_MIN = 5.2 * 60.0
_DECODER_POST_DESMOLDE_MIN = 4.0 * 60.0

# Q.138.D — budget defaults para produção com 200 ordens × 10 fases (~1500 ops).
# Era 60s/30s: dava só 3 gerações. 150s/120s dá ~40 gerações com pop=100.
# Tests que querem o valor legado passam os budgets explicitamente ao CPOConfig.
_TOTAL_BUDGET_S_DEFAULT: float = 150.0
_GA_BUDGET_S_DEFAULT: float = 120.0
_TIME_LIMIT_S_DEFAULT: float = _GA_BUDGET_S_DEFAULT


@dataclass
class CPOConfig:
    population_size: int = 100
    # Sprint A E1 — Blueprint v2.0 §5.5 requires 200 generations for the
    # FRRMAB window (window=200) to produce a stable reward signal.
    # Was 50 in Sprint E/F; tests that want the old value pass
    # `generations=50` explicitly.
    generations: int = 200
    tournament_size: int = 5
    crossover_rate: float = 0.60
    mutation_rate: float = 0.30
    elitism_size: int = 5
    seed: Optional[int] = 42
    # Q.138.D — era 30s (cortava ao 3.º passe com 1500 ops × pop=100).
    # Agora segue _TIME_LIMIT_S_DEFAULT → ga_budget_s.
    time_limit_sec: float = _TIME_LIMIT_S_DEFAULT

    # -------------------- Sprint F adaptive flags -------------------- #
    use_frrmab: bool = True
    use_mapelites: bool = True
    # Sprint C 4.2 E2 — default ON. The layer is self-gated: `record()`
    # is a no-op until we have ≥ min_samples_to_train, and
    # `should_skip_candidate()` returns False until the model is trained.
    # So flipping this to True is a pure win — nothing happens on small
    # runs, and big runs automatically gain the 80% pre-screen benefit.
    use_surrogate: bool = True
    use_restart: bool = True
    stagnation_limit_generations: int = 20
    restart_random_fraction: float = 0.50

    # -------------------- Sprint P v2.0 cascade flags ---------------- #
    # Sprint Q.9 Onda 2.1+2.2 — flipped from False to True after each
    # flag's regression suite went green. The 4 Spelke property tests
    # in `tests/plan/test_preview_delta_property.py` are the primary
    # gate; if a future change breaks one of those, revert the
    # responsible flag here, don't disable the test.
    #: Explicit greedy 8-phase pipeline instead of the embedded decoder.
    use_greedy_pipeline: bool = True
    #: Schedule backwards from `ProductionOrder.transport_date` (PL14).
    use_backwards_scheduling: bool = True
    #: Honor dual-resource requirement in Laminagem (WF11).
    use_hungarian_pair_assignment: bool = True
    #: Queue time (5.2h median) between consecutive phases (PL22).
    use_queue_time: bool = True
    #: Buffer pós-Desmolde (PL21 — 95% of errors detected at Desmolde).
    use_post_desmolde_buffer: bool = True
    #: MAP-Elites v2.0 axes (lam_util / tardiness_transport / idle_pct).
    use_v2_mapelites_axes: bool = True
    #: CP-SAT Rolling Horizon L-RHO as the 5th cascade phase. Aligned
    #: with `default_configs.py` ("planning", "cpo.use_cpsat_lrho", True).
    use_cpsat_lrho: bool = True
    #: Treat chromosome.routing_choices as an A/B selector per op.
    use_routing_variants: bool = True
    #: Q.166 — otimizador GLOBAL CP-SAT (makespan) substitui a GA. Default False
    #: (opt-in até validado em prod); o robô liga-o via tenant config. Sem ortools
    #: → fallback ao greedy. Budget = `cpsat_budget_s` (ou maior, do robô).
    use_cpsat_global: bool = False
    #: nº de threads de pesquisa do CP-SAT global.
    cpsat_num_workers: int = 16  # Q.174.F1: 8→16 (medir cpsat_solve_time_s)
    #: determinismo do CP-SAT (max_deterministic_time) — para testes reproduzíveis.
    cpsat_deterministic: bool = False
    #: Q.173.P — isenção dos guardrails SOFT do gate axioma-7 quando o
    #: candidato CP-SAT corta o makespan em >= esta fração vs baseline
    #: (decisão Luis 2026-06-11; 0 = desligado). Hard guardrails (tardiness,
    #: late orders, OTD, cap 1.5×) vetam SEMPRE. Config:
    #: `cpo.cpsat_gate.soft_waiver_gain`.
    cpsat_gate_soft_waiver_gain: float = 0.5

    # -------------------- Sprint P.12 phase budgets ------------------ #
    #: Total cascade budget (seconds). Sub-budgets MUST sum to ≤ this value.
    # Q.138.D — usa constantes _TOTAL_BUDGET_S_DEFAULT / _GA_BUDGET_S_DEFAULT
    # definidas acima do dataclass (isentas de H0 por serem _UPPER_SNAKE).
    total_budget_s: float = _TOTAL_BUDGET_S_DEFAULT
    greedy_budget_s: float = 2.0
    ga_budget_s: float = _GA_BUDGET_S_DEFAULT
    mapelites_budget_s: float = 5.0
    cpsat_budget_s: float = 15.0
    workforce_budget_s: float = 3.0

    def __post_init__(self) -> None:
        # Belt-and-braces: ensure the GA budget doesn't exceed total. The
        # decoder-level `time_limit_sec` is kept in sync with `ga_budget_s`
        # so a caller that tightens one of them doesn't see the GA happily
        # run over the consolidated budget.
        if self.ga_budget_s > self.total_budget_s:
            self.ga_budget_s = self.total_budget_s
        # A zero time_limit is used by tests that want synchronous decoding
        # without GA iteration; leave that case alone.
        if self.time_limit_sec > self.ga_budget_s and self.ga_budget_s > 0:
            self.time_limit_sec = self.ga_budget_s
        # Guard: tournament_size < 1 causes IndexError in _tournament() because
        # sample(scored, 0) returns [] and competitors[0] would raise.
        if self.tournament_size < 1:
            self.tournament_size = 1

    def phase_budget_total(self) -> float:
        return (
            self.greedy_budget_s
            + self.ga_budget_s
            + self.mapelites_budget_s
            + self.cpsat_budget_s
            + self.workforce_budget_s
        )


# Q.173.P — guardrails SOFT do safety_net (toleram ruído da GA). Os HARD
# (num_late_orders, total_tardiness_hours, otd_delivery, makespan 1.5×cap)
# nunca são isentados. Decisão do Luis 2026-06-11: um candidato CP-SAT que
# corta o makespan em >X% (default 50%) não pode ser vetado por 0,25pp de
# idle_ratio — foi exatamente isso que manteve o plano live em 22.297h
# (~2,5 anos) vs ~690h durante dias (auditoria 2026-06-11).
_SOFT_GATE_METRICS = frozenset({
    "throughput_eur_day",
    "avg_quality_risk",
    "setups",
    "total_idle_hours",
    "lam_utilization",
    "idle_ratio",
})


def _cpsat_gate_decision(
    candidate: Dict[str, Any],
    baseline: Dict[str, Any],
    *,
    soft_waiver_gain: float = 0.0,
) -> Tuple[bool, Dict[str, Any]]:
    """Q.169.D — gate COMPLETO do axioma 7 para o caminho CP-SAT.

    O gate antigo só comparava makespan e forçava safety_net_triggered=False:
    um candidato CP-SAT que melhorasse makespan mas degradasse tardiness/
    qualidade/idle/lam_utilization substituía o baseline sem ninguém ver
    (gap confirmado pela matriz de paridade Q.169.A). Agora:

      aceita ⟺ ZERO violações nas 9 dimensões do safety_net
               E melhoria ESTRITA em makespan OU tardiness
               (com o objetivo tardiness+makespan do Q.169.D, um candidato
               pode trocar makespan por menos atraso — ambos contam).

    Q.173.P — `soft_waiver_gain` (config `cpo.cpsat_gate.soft_waiver_gain`,
    0 = desligado): quando o candidato corta o makespan em pelo menos esta
    fração vs baseline, as violações SOFT são ISENTADAS (registadas em
    `waived_soft`); as HARD vetam sempre. Os op-sets já são comensuráveis:
    desde Q.173.Q o candidato CP-SAT inclui as reparações (merge-back).

    Pura → testável isolada. Devolve (aceite, meta) — meta vai para
    cpo_meta.cpsat_gate (auditoria; fora do hash)."""
    cm = float(candidate.get("makespan_hours", 1e18) or 1e18)
    bm = float(baseline.get("makespan_hours", 1e18) or 1e18)
    ct = float(candidate.get("total_tardiness_hours", 0.0) or 0.0)
    bt = float(baseline.get("total_tardiness_hours", 0.0) or 0.0)
    violations = _gather_violations(candidate, baseline)
    improves = cm < bm or ct < bt

    makespan_gain = (bm - cm) / bm if bm > 0 else 0.0
    waived: List[Tuple[str, str]] = []
    if soft_waiver_gain > 0 and makespan_gain >= soft_waiver_gain:
        waived = [v for v in violations if v[0] in _SOFT_GATE_METRICS]
        violations = [v for v in violations if v[0] not in _SOFT_GATE_METRICS]

    reason = "ok"
    if violations:
        reason = f"{len(violations)} violações: " + "; ".join(
            f"{metric}({msg})" for metric, msg in violations[:3]
        )
    elif not improves:
        reason = (
            f"sem melhoria estrita (makespan {cm:.1f}h vs {bm:.1f}h, "
            f"tardiness {ct:.1f}h vs {bt:.1f}h)"
        )
    elif waived:
        reason = (
            f"ok (makespan -{makespan_gain:.0%}; {len(waived)} guardrail(s) "
            "soft isentado(s) pela melhoria)"
        )

    meta = {
        "accepted": not violations and improves,
        "reason": reason,
        "makespan_h": round(cm, 1),
        "baseline_makespan_h": round(bm, 1),
        "tardiness_h": round(ct, 1),
        "baseline_tardiness_h": round(bt, 1),
        "violations": [f"{metric}: {msg}" for metric, msg in violations],
        "waived_soft": [f"{metric}: {msg}" for metric, msg in waived],
        "soft_waiver_gain": soft_waiver_gain,
        "makespan_gain": round(makespan_gain, 4),
    }
    return meta["accepted"], meta


class CPOv4Engine:
    """Hyper-heuristic scheduler for DRCFFS-R (NELO production)."""

    def __init__(
        self,
        state: FactoryState,
        config: Optional[CPOConfig] = None,
        fitness_config: Optional[FitnessConfig] = None,
        surrogate: Optional[CPOSurrogateLayer] = None,
        mapelites: Optional[MAPElites3D] = None,
    ) -> None:
        self.state = state
        self.config = config or CPOConfig()
        self.fitness_config = fitness_config or FitnessConfig()

        # Sprint Q.9 Onda 1.1 — Camada 1 wire. `FactoryState.load()` populates
        # `state.preference_rules` with the confirmed Camada-1 rules for this
        # tenant; `fitness.compute_fitness` reads them off `FitnessConfig`. The
        # two have lived next to each other since Sprint E.4 with no callable
        # in between, so rules were detected → confirmed → ignored. Copy them
        # in here when the caller didn't pre-load a fitness_config that
        # already carries rules (the explicit-overrides case).
        if (
            getattr(state, "preference_rules", None)
            and not self.fitness_config.preference_rules
        ):
            self.fitness_config.preference_rules = list(state.preference_rules)

        # Sprint Q.13.E E.1 — Capacity 1.5× factor for retrabalho-heavy
        # phases (Plan v4 §3.3). FactoryState.load() populates
        # `historical_error_rates`; we forward them onto the fitness
        # config and bump the factor from 1.0 → 1.5 so the GA stops
        # over-promising throughput on Lixagem água / Pintura Acab /
        # Lixagem polim. Callers that hand-craft a FitnessConfig with
        # explicit phase_error_rates / capacity factor keep their
        # values (no overwrite).
        rates = getattr(state, "historical_error_rates", None) or {}
        if rates and not self.fitness_config.phase_error_rates:
            self.fitness_config.phase_error_rates = dict(rates)
            if self.fitness_config.rework_capacity_factor <= 1.0:
                self.fitness_config.rework_capacity_factor = 1.5

        self._rng = random.Random(self.config.seed)

        # Adaptive layers — created lazily so Sprint E tests that don't
        # construct these directly still get defaults driven by config.
        self._frrmab = FRRMAB(rng=self._rng) if self.config.use_frrmab else None
        self._mapelites = (
            mapelites if mapelites is not None
            else (MAPElites3D() if self.config.use_mapelites else None)
        )
        self._surrogate = (
            surrogate if surrogate is not None
            else CPOSurrogateLayer(enabled=self.config.use_surrogate)
        )

    def _try_cpsat_global(
        self,
        baseline: Dict[str, Any],
        operations: List[SchedulingOperation],
        machines: List[SchedulingMachine],
        horizon_start: datetime,
        horizon_end: datetime,
        product_price_eur: Optional[Dict[str, Any]],
        start_floors: Optional[Dict[str, datetime]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Q.166.F — corre o CP-SAT global; devolve (result, gate_meta).

        result=None ⇒ cai na GA. Q.173.P: o gate_meta é devolvido SEMPRE
        (aceite, rejeitado, exceção ou indisponível) para o commit final
        carregar `cpo_meta.cpsat_gate` — a auditoria 2026-06-11 provou que
        a rejeição morria com o result descartado e o veto só era visível
        em logs truncáveis. O greedy `baseline` dá o warm-start."""
        try:
            from src.plan.engines.cpsat_global import (
                greedy_hint_minutes,
                run_cpsat_global,
            )
            from src.plan.engines.cpsat_scheduler import CPSATConfig

            cfg = CPSATConfig(
                budget_s=float(self.config.cpsat_budget_s),
                num_workers=int(self.config.cpsat_num_workers),
                deterministic=bool(self.config.cpsat_deterministic),
            )
            hint = greedy_hint_minutes(baseline, horizon_start)
            result = run_cpsat_global(
                self.state, operations, machines, horizon_start, horizon_end,
                config=cfg, greedy_hint=hint, product_price_eur=product_price_eur,
                start_floors=start_floors,  # Q.174.F6
            )
        except Exception as exc:  # pragma: no cover — fallback robusto
            logger.warning("CP-SAT global falhou (%s) — fallback ao greedy/GA", exc)
            return None, {"accepted": False, "reason": f"exception: {exc}"}
        if result is None:
            return None, {
                "accepted": False,
                "reason": "cpsat indisponível (sem ortools / sem solução / "
                          "0 ops elegíveis)",
            }
        accepted, gate_meta = _cpsat_gate_decision(
            result, baseline,
            soft_waiver_gain=float(self.config.cpsat_gate_soft_waiver_gain),
        )
        result.setdefault("cpo_meta", {})["cpsat_gate"] = gate_meta
        if not accepted:
            logger.info(
                "CP-SAT global REJEITADO pelo gate axioma-7: %s — mantém greedy/GA",
                gate_meta.get("reason"),
            )
            return None, gate_meta
        result["safety_net_triggered"] = False
        logger.info(
            "CP-SAT global ACEITE: makespan %.1fh (baseline %.1fh), "
            "tardiness %.1fh (baseline %.1fh), violações hard=0 "
            "(soft isentadas=%d)",
            gate_meta["makespan_h"], gate_meta["baseline_makespan_h"],
            gate_meta["tardiness_h"], gate_meta["baseline_tardiness_h"],
            len(gate_meta.get("waived_soft", [])),
        )
        return result, gate_meta

    def schedule(
        self,
        operations: List[SchedulingOperation],
        machines: List[SchedulingMachine],
        horizon_start: Optional[datetime] = None,
        horizon_end: Optional[datetime] = None,
        *,
        product_price_eur: Optional[Dict[str, Any]] = None,
        boost_inputs: Optional[Dict[str, int]] = None,
        start_floors: Optional[Dict[str, datetime]] = None,
    ) -> Dict[str, Any]:
        # Q.173.S — boost_inputs (work_order_id → effective_boost) chegam
        # ANTES do solve e reordenam o priority_order do decoder em todos
        # os caminhos greedy/GA. O CP-SAT global não os consome direto —
        # herda-os via warm-start (hint do baseline com boosts) e o seu
        # objetivo é tardiness+makespan sobre due dates reais.
        started = time.time()
        horizon_start = horizon_start or utc_now_naive()
        horizon_end = horizon_end or (horizon_start + timedelta(weeks=4))

        if not operations:
            return _empty_result(horizon_start)

        n = len(operations)

        # 1. Baseline greedy (chromosome = identity permutation)
        # Sprint P.1 — explicit 8-phase pipeline when opted-in.
        baseline_chromo = Chromosome.identity(n)
        queue_time_min = (
            _DECODER_QUEUE_TIME_MIN if self.config.use_queue_time else None
        )
        post_desmolde_min = (
            _DECODER_POST_DESMOLDE_MIN if self.config.use_post_desmolde_buffer else None
        )
        greedy_meta: Optional[Dict[str, Any]] = None
        if self.config.use_greedy_pipeline:
            pipeline = GreedyPipeline(
                self.state, budget_s=self.config.greedy_budget_s,
            )
            result = pipeline.run(
                baseline_chromo, operations, machines, horizon_start, horizon_end,
                queue_time_minutes=queue_time_min,
                post_desmolde_buffer_minutes=post_desmolde_min,
                boost_inputs=boost_inputs,
                start_floors=start_floors,  # Q.174.F6
            )
            baseline = result.schedule
            greedy_meta = result.to_meta()
        else:
            baseline = decode(
                baseline_chromo, operations, machines, self.state,
                horizon_start, horizon_end,
                queue_time_minutes=queue_time_min,
                post_desmolde_buffer_minutes=post_desmolde_min,
                product_price_eur=product_price_eur,
                boost_inputs=boost_inputs,
                start_floors=start_floors,  # Q.174.F6
            )
        # Q.153.A3 — escalar as referências de normalização da fitness ao
        # baseline ANTES de o avaliar, para o GA ter gradiente real em
        # pontualidade/horizonte. `ref = max(constante, valor_baseline)`:
        # com a dívida herdada (~619 000h) uma constante fixa fazia o termo
        # colar em 1.0 e o GA ficava cego ao "mais pontual".
        self.fitness_config.norm_ref_makespan_h = max(
            _NORM_MAKESPAN_H, float(baseline.get("makespan_hours", 0) or 0),
        )
        self.fitness_config.norm_ref_tardiness_h = max(
            _NORM_TARDINESS_H, float(baseline.get("tardiness_beyond_today_h", 0) or 0),
        )
        self.fitness_config.norm_ref_idle_h = max(
            _NORM_IDLE_H, float(baseline.get("total_idle_hours", 0) or 0),
        )

        baseline_fit = compute_fitness(baseline, self.fitness_config)
        logger.info(
            f"CPO baseline: makespan={baseline['makespan_hours']:.1f}h, "
            f"tardy={baseline['num_late_orders']}, "
            f"newly_late={baseline.get('num_newly_late', 0)}, "
            f"fitness={baseline_fit:.2f}"
        )

        # Q.166.F — otimizador GLOBAL CP-SAT (makespan) substitui a GA quando ON.
        # O greedy baseline acima serve de WARM-START (hint) + comparação de
        # segurança (axioma 7: nunca pior que o baseline). Sem ortools / sem solução
        # / makespan não-melhor → cai na GA abaixo (fallback gracioso).
        cpsat_gate_meta: Optional[Dict[str, Any]] = None
        if self.config.use_cpsat_global:
            cpsat_result, cpsat_gate_meta = self._try_cpsat_global(
                baseline, operations, machines, horizon_start, horizon_end,
                product_price_eur, start_floors=start_floors,  # Q.174.F6
            )
            if cpsat_result is not None:
                return cpsat_result

        # Surrogate context (static across the run, cheap to precompute).
        total_duration = sum(float(op.duration_minutes) for op in operations)
        surrogate_ctx = {
            "n_ops": n,
            "n_orders": len({op.order_id for op in operations}),
            "avg_duration_min": (total_duration / n) if n else 0.0,
        }

        # 2. GA exploration
        best = baseline
        best_fit = baseline_fit

        # Seed MAP-Elites with the baseline so restart/injection always
        # has at least one viable elite to draw from.
        if self._mapelites is not None:
            self._mapelites.insert(baseline_chromo, baseline_fit, baseline, generation=0)

        population = [Chromosome.random(n, self._rng) for _ in range(self.config.population_size - 1)]
        population.append(baseline_chromo.clone())

        # Stagnation tracking for restart logic.
        last_best_fit = baseline_fit
        stagnation_count = 0
        total_skips = 0
        total_real_evals = 0
        gen = 0

        for gen in range(self.config.generations):
            if time.time() - started > self.config.time_limit_sec:
                logger.info(f"CPO budget exhausted at generation {gen}")
                break

            # ----- Evaluate --------------------------------------------
            scored: List[Tuple[float, Chromosome, Optional[Dict[str, Any]]]] = []
            for chromo in population:
                if self._surrogate.should_skip_candidate(chromo, surrogate_ctx):
                    # Use the baseline fitness as a pessimistic placeholder —
                    # the tournament will deprioritize this candidate, but it
                    # stays in the pool so its genes can still recombine.
                    scored.append((baseline_fit * 2, chromo, None))
                    total_skips += 1
                    continue

                result = decode(
                    chromo, operations, machines, self.state,
                    horizon_start, horizon_end,
                    queue_time_minutes=queue_time_min,
                    post_desmolde_buffer_minutes=post_desmolde_min,
                    product_price_eur=product_price_eur,
                    boost_inputs=boost_inputs,
                    start_floors=start_floors,  # Q.174.F6
                )
                fit = compute_fitness(result, self.fitness_config)
                scored.append((fit, chromo, result))
                total_real_evals += 1

                # Sprint C 4.2 E3 — reward the FRRMAB operator immediately
                # after this child is evaluated. The previous
                # `_update_frrmab_rewards(scored)` at end-of-generation
                # only rewarded children that SURVIVED the tournament,
                # biasing the bandit toward operators whose kids happened
                # to persist — unrelated to their true fitness contribution.
                # Doing it here guarantees every produced child gives a
                # reward signal regardless of whether it gets selected.
                op_name_used = getattr(chromo, "_frrmab_op", None)
                parent_fit_at_mutation = getattr(
                    chromo, "_frrmab_parent_fit", None,
                )
                if (
                    op_name_used is not None
                    and parent_fit_at_mutation is not None
                    and self._frrmab is not None
                ):
                    reward = max(
                        0.0,
                        (parent_fit_at_mutation - fit)
                        / (abs(parent_fit_at_mutation) + 1e-6),
                    )
                    self._frrmab.record(op_name_used, reward)
                    chromo._frrmab_op = None  # type: ignore[attr-defined]
                    chromo._frrmab_parent_fit = None  # type: ignore[attr-defined]

                # Track best + MAP-Elites + surrogate sample
                # Note: best_chromo was tracked here but never read downstream
                # (the decode result is in `best`); removed to avoid confusion.
                if fit < best_fit:
                    best_fit = fit
                    best = result
                if self._mapelites is not None:
                    self._mapelites.insert(chromo, fit, result, generation=gen)
                self._surrogate.record(chromo, surrogate_ctx, fit)

            # ----- Stagnation detection --------------------------------
            if best_fit < last_best_fit - 1e-9:
                last_best_fit = best_fit
                stagnation_count = 0
            else:
                stagnation_count += 1

            # ----- Selection + reproduction ----------------------------
            scored.sort(key=lambda t: t[0])

            elite_count = max(
                self.config.elitism_size,
                int(0.05 * self.config.population_size),  # explicit top-5%
            )
            elite_scored = scored[:elite_count]
            next_pop: List[Chromosome] = [c.clone() for (_, c, _) in elite_scored]

            # Periodic diversity injection from MAP-Elites.
            if (
                self._mapelites is not None
                and (gen + 1) % self._mapelites.injection_period_generations == 0
                and not self._mapelites.is_empty()
            ):
                for elite in self._mapelites.inject_random_candidates(
                    self.config.population_size, self._rng
                ):
                    if len(next_pop) >= self.config.population_size:
                        break
                    next_pop.append(elite)

            # Restart after prolonged stagnation — 50% random, 50% mixed
            # between existing elite and MAP-Elites samples.
            if (
                self.config.use_restart
                and stagnation_count >= self.config.stagnation_limit_generations
            ):
                next_pop = self._restart_population(
                    n=n,
                    current_elite=elite_scored,
                )
                stagnation_count = 0
                logger.info(f"CPO restart at generation {gen} (stagnation reached)")

            while len(next_pop) < self.config.population_size:
                p1 = self._tournament(scored)
                p2 = self._tournament(scored)
                if self._rng.random() < self.config.crossover_rate:
                    child = self._crossover_ox(p1, p2)
                else:
                    child = p1.clone()
                if self._rng.random() < self.config.mutation_rate:
                    child, op_name, parent_fit = self._mutate_with_frrmab(child, scored)
                    # FRRMAB reward comes from the NEXT generation's
                    # evaluation — store the parent fitness so we can
                    # compute the reward after decode.
                    child._frrmab_op = op_name  # type: ignore[attr-defined]
                    child._frrmab_parent_fit = parent_fit  # type: ignore[attr-defined]
                next_pop.append(child)

            # Update FRRMAB rewards from the previous generation's children.
            self._update_frrmab_rewards(scored)

            population = next_pop

        # 3. Safety net — best candidate vs. baseline
        best["engine_used"] = "cpo_v4"
        best_final = apply_safety_net(best, baseline)

        elapsed = time.time() - started
        best_final["solve_time_sec"] = round(elapsed, 3)
        best_final["status"] = "optimal" if not best_final.get("safety_net_triggered") else "safety_net"
        cpo_meta: Dict[str, Any] = {
            # Q.173.P — etiqueta do motor SEMPRE presente (a auditoria
            # 2026-06-11 encontrou 182/206 commits sem `engine`) e o veredicto
            # do gate CP-SAT persiste mesmo em rejeição — auditável pela BD,
            # não só por logs truncáveis.
            "engine": "greedy_ga",
            **({"cpsat_gate": cpsat_gate_meta} if cpsat_gate_meta else {}),
            "baseline_fitness": round(baseline_fit, 2),
            "best_fitness": round(best_fit, 2),
            "improvement_pct": round(
                100.0 * (baseline_fit - best_fit) / max(baseline_fit, 1e-6), 2
            ),
            "generations_run": gen + 1 if operations else 0,
            "real_evaluations": total_real_evals,
            "surrogate_skips": total_skips,
            "frrmab": self._frrmab.snapshot() if self._frrmab is not None else None,
            "mapelites": self._mapelites.snapshot() if self._mapelites is not None else None,
            "surrogate": self._surrogate.snapshot() if self._surrogate is not None else None,
        }
        if greedy_meta is not None:
            cpo_meta["greedy_pipeline"] = greedy_meta
        cpo_meta["phase_budgets"] = {
            "total": self.config.total_budget_s,
            "greedy": self.config.greedy_budget_s,
            "ga": self.config.ga_budget_s,
            "mapelites": self.config.mapelites_budget_s,
            "cpsat": self.config.cpsat_budget_s,
            "workforce": self.config.workforce_budget_s,
        }
        cpo_meta["flags"] = {
            "use_greedy_pipeline": self.config.use_greedy_pipeline,
            "use_queue_time": self.config.use_queue_time,
            "use_post_desmolde_buffer": self.config.use_post_desmolde_buffer,
            "use_backwards_scheduling": self.config.use_backwards_scheduling,
            "use_hungarian_pair_assignment": self.config.use_hungarian_pair_assignment,
            "use_v2_mapelites_axes": self.config.use_v2_mapelites_axes,
            "use_cpsat_lrho": self.config.use_cpsat_lrho,
            "use_routing_variants": self.config.use_routing_variants,
        }
        # FASE 0.2 (DEVA-01) — surface ML wiring so the API caller can
        # tell whether the predictor was actually live this run.
        cpo_meta["quality_risk_predictor_used"] = (
            self.fitness_config.quality_risk_predictor is not None
        )
        # Q.160 — fila inter-fase MEDIDA por fase (diagnóstico: que fase acumula
        # WIP / parte o one-piece-flow). Não entra no hash do commit (cpo_meta
        # é excluído). Vazio quando o state não trouxe histórico de of_fp.
        cpo_meta["queue_median_by_phase"] = dict(
            getattr(self.state, "queue_median_by_phase", {}) or {}
        )
        cpo_meta["queue_global_median_h"] = getattr(
            self.state, "queue_global_median_h", None
        )
        best_final["cpo_meta"] = cpo_meta
        return best_final

    # ------------------------------------------------------------------ #
    # FRRMAB integration                                                 #
    # ------------------------------------------------------------------ #

    def _mutate_with_frrmab(
        self,
        chromo: Chromosome,
        scored: List[Tuple[float, Chromosome, Optional[Dict[str, Any]]]],
    ) -> Tuple[Chromosome, Optional[str], float]:
        """Apply mutation via FRRMAB (or the legacy random picker)."""
        # Parent fitness is this chromosome's fitness in `scored` if present.
        parent_fit = self._lookup_fitness(chromo, scored)
        if self._frrmab is None:
            return self._mutate(chromo), None, parent_fit
        op_name, op_fn = self._frrmab.select()
        return op_fn(chromo, self._rng), op_name, parent_fit

    def _update_frrmab_rewards(
        self,
        scored: List[Tuple[float, Chromosome, Optional[Dict[str, Any]]]],
    ) -> None:
        """After each generation, turn parent→child fitness deltas into
        FRRMAB rewards. The reward is zero when no improvement."""
        if self._frrmab is None:
            return
        for fit, chromo, _ in scored:
            op_name = getattr(chromo, "_frrmab_op", None)
            parent_fit = getattr(chromo, "_frrmab_parent_fit", None)
            if op_name is None or parent_fit is None:
                continue
            denom = abs(parent_fit) + 1e-6
            reward = max(0.0, (parent_fit - fit) / denom)
            self._frrmab.record(op_name, reward)
            # Clear so we don't double-count next generation.
            chromo._frrmab_op = None  # type: ignore[attr-defined]
            chromo._frrmab_parent_fit = None  # type: ignore[attr-defined]

    @staticmethod
    def _lookup_fitness(
        chromo: Chromosome,
        scored: List[Tuple[float, Chromosome, Optional[Dict[str, Any]]]],
    ) -> float:
        for fit, c, _ in scored:
            if c is chromo:
                return fit
        return 0.0

    # ------------------------------------------------------------------ #
    # Restart                                                            #
    # ------------------------------------------------------------------ #

    def _restart_population(
        self,
        n: int,
        current_elite: List[Tuple[float, Chromosome, Optional[Dict[str, Any]]]],
    ) -> List[Chromosome]:
        pop_size = self.config.population_size
        rand_count = max(1, int(self.config.restart_random_fraction * pop_size))
        elite_count = pop_size - rand_count

        mixed: List[Chromosome] = []

        # Take from MAP-Elites if available (most diverse elite source).
        if self._mapelites is not None and not self._mapelites.is_empty():
            mixed.extend(self._mapelites.sample(elite_count, self._rng))

        # Fill remaining from current generation's elite list.
        for _, c, _ in current_elite:
            if len(mixed) >= elite_count:
                break
            mixed.append(c.clone())

        # Random genomes to seed exploration.
        while len(mixed) < pop_size:
            mixed.append(Chromosome.random(n, self._rng))

        return mixed[:pop_size]

    # ------------------------------------------------------------------ #
    # GA operators                                                       #
    # ------------------------------------------------------------------ #

    def _tournament(
        self,
        scored: List[Tuple[float, Chromosome, Dict[str, Any]]],
    ) -> Chromosome:
        competitors = self._rng.sample(scored, min(self.config.tournament_size, len(scored)))
        competitors.sort(key=lambda t: t[0])
        return competitors[0][1]

    def _crossover_ox(self, p1: Chromosome, p2: Chromosome) -> Chromosome:
        """Order Crossover (OX) — preserves relative order of ops from each parent."""
        n = len(p1.permutation)
        if n < 2:
            return p1.clone()
        a, b = sorted(self._rng.sample(range(n), 2))
        child_perm = [-1] * n
        child_perm[a:b + 1] = p1.permutation[a:b + 1]
        fill = [x for x in p2.permutation if x not in child_perm[a:b + 1]]
        j = 0
        for i in range(n):
            if child_perm[i] == -1:
                child_perm[i] = fill[j]
                j += 1
        child = Chromosome(
            permutation=child_perm,
            edd_gap=(p1.edd_gap + p2.edd_gap) // 2,
            buffer_pct=(p1.buffer_pct + p2.buffer_pct) / 2,
            quality_weight=(p1.quality_weight + p2.quality_weight) / 2,
        )
        return child

    def _mutate(self, chromo: Chromosome) -> Chromosome:
        """Pick one of 3 operators at random: swap, insert, perturb_scalars."""
        op = self._rng.choice(("swap", "insert", "scalars"))
        child = chromo.clone()
        if op == "swap" and len(child.permutation) >= 2:
            i, j = self._rng.sample(range(len(child.permutation)), 2)
            child.permutation[i], child.permutation[j] = child.permutation[j], child.permutation[i]
        elif op == "insert" and len(child.permutation) >= 2:
            i = self._rng.randrange(len(child.permutation))
            j = self._rng.randrange(len(child.permutation))
            v = child.permutation.pop(i)
            child.permutation.insert(j, v)
        else:  # scalars
            child.edd_gap = max(5, min(30, child.edd_gap + self._rng.randint(-3, 3)))
            child.buffer_pct = max(0.0, min(0.3, child.buffer_pct + self._rng.uniform(-0.05, 0.05)))
            child.quality_weight = max(0.0, min(1.0, child.quality_weight + self._rng.uniform(-0.1, 0.1)))
        return child


def _empty_result(horizon_start: datetime) -> Dict[str, Any]:
    return {
        "success": True,
        "engine_used": "cpo_v4",
        "operations": [],
        "makespan_hours": 0.0,
        "total_tardiness_hours": 0.0,
        "num_late_orders": 0,
        "setups": 0,
        "avg_utilization": 0.0,
        "warnings": ["No operations provided"],
        "infeasible_op_ids": [],
        "status": "empty",
        "solve_time_sec": 0.0,
    }
