# Causal stack architecture

**Sprint F.1 – F.5** wired a three-layer causal reasoning surface on
top of the Copilot LLM:

```
            ┌────────────────────────────────────────────┐
            │  User question (PT-PT, free text)          │
            └──────────────────────┬─────────────────────┘
                                   │
                                   ▼
           ┌───────────────────────────────────────────┐
           │  RLM mini-agent  (src/copilot/rlm/)       │
           │  • typed sub-queries on FactoryState      │
           │  • max_steps cap (default 5)              │
           │  • PT-PT system prompt with catalogue     │
           └──────────────────────┬────────────────────┘
                                  │
                                  ▼
           ┌───────────────────────────────────────────┐
           │  LLM  (Ollama / vLLM via factory.py)      │
           │  • JSON-mode response per step            │
           │  • emits CausalChain on "answer"          │
           └──────────────────────┬────────────────────┘
                                  │
                                  ▼
           ┌───────────────────────────────────────────┐
           │  verify_chain  (src/copilot/causal/)      │
           │  5 layers:                                │
           │   1. syntactic                            │
           │   2. DAG-consistent                       │
           │   3. direction (reachable root→target)    │
           │   4. NLI (rule-based recommendation/      │
           │       mechanism coherence + kernel sign)  │
           │   5. kernel (NELO_DAG causal_query)       │
           │  coherence = Π layer_scores; gate 0.85    │
           └──────────────────────┬────────────────────┘
                                  │
                                  ▼
           ┌───────────────────────────────────────────┐
           │  Trust Index (8th component) + UI        │
           └───────────────────────────────────────────┘
```

## NELO_DAG (F.1)

`src/copilot/causal/nelo_dag.py` — pure-Python SCM:

- **23 nodes** across 6 categories: input / process_time /
  process_flow / quality / output / confounder.
- **3 confounders** (operator_experience, mold_age,
  external_temperature) — no modelled parents, carry baseline only.
- Each non-input node has a functional form; `causal_query(target,
  do=…, observe=…)` propagates in Kahn topological order.
- Baselines recomputed per query — `delta` reports the
  intervention's *effect*, not the declared baseline's gap.

## CausalChain (F.2)

`src/copilot/causal/chain.py` — Pydantic contract + 5-layer validator.
The LLM's answer is a structured object the frontend can render
without surprises, and the coherence score becomes the 8th Trust
Index component.

## POETIQ iterative (F.3)

`src/copilot/poetiq_iterative.py` — wires the Sprint P.13 scaffold
(`poetiq_expanded.POETIQLoop`) with real callbacks:

| Step | Default |
|---|---|
| **Optimize** | CPO engine (caller-provided wrapper) |
| **Evaluate** | kernel-only rubric + issue classification |
| **Iterate** | deterministic critique → delta hints |
| **Test** | perturbation probes (`drop_worker`, `block_machine`, `mold_unavailable`) |
| **Qualify** | threshold 0.80 AND no safety violation |

Real LLM iterator slots in via `iterator=` arg when Ollama is wired.

## RLM (F.4)

`src/copilot/rlm/factory_state_query.py` + `agent.py` — 10 typed
sub-queries (wip, bottlenecks, open_orders, backlog, skills_risk,
quality, lead_time, mold_conflicts, preference_rules, overview).
Each response capped at ~800 chars so the conversation stays within
the prompt budget.

## Causal entropy (I.5)

`src/plan/cpo/causal_entropy.py` — Shannon entropy over the
schedule's load across machine / workers / mould. Fitness gets a
`0.05 × (1 − entropy_score)` penalty for concentrated plans. Sprint
I.5 — doesn't require LLM runtime, always on when `w_causal_entropy > 0`.

## What's deferred

- **I.2 ABLkit** — LLM/kernel divergence tracking → DPO pair.
- **I.3 DoWhy-GCM** — needs `dowhy` dep. Gives attribution per node.
- **I.4 PCMCI+** — needs `tigramite` dep. Discovers new DAG edges
  from 3-month time series.

Add deps + these modules once there's ≥3 months of real NELO data.
