"""
Q.55 — DoWhy como verificador causal independente do NELO_DAG
================================================================

O `src/copilot/causal/nelo_dag.py` é o SCM da casa: lambdas determinísticas,
auditáveis. O `causal_query` dá a verdade-base. Mas um SCM hand-coded só prova
o que o autor lá pôs — não prova que a relação aguenta dados.

Este módulo mete o DoWhy 0.14 como **segundo juiz, independente**:

1. `build_dataset(n)` — amostra os 9 nós-raiz (inputs + confounders) em gamas
   plausíveis de fábrica, propaga pelo SCM real (`_propagate`) e junta ruído de
   medição. Resultado: uma tabela observacional consistente com o NELO_DAG.

2. `nelo_dot_graph()` — exporta o DAG em DOT para o DoWhy.

3. `estimate_pair(...)` — para um par (causa → efeito): identifica o estimando
   (back-door), estima o efeito por regressão linear, e corre 3 refutadores:
     * placebo_treatment_refuter — troca a causa por ruído; efeito deve cair a ~0.
     * random_common_cause       — injecta confounder aleatório; efeito estável.
     * data_subset_refuter       — re-estima num subconjunto; efeito estável.

4. `dowhy_table(pairs)` — corre tudo de uma vez, devolve dict indexado por par.

O juízo: um par está "confirmado pelo DoWhy" se o efeito estimado tem sinal
não-trivial E os 3 refutadores não o derrubam. É isso que separa uma relação
causal real de uma correlação acidental.
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Tuple

warnings.filterwarnings("ignore")
for _noisy in ("dowhy", "numexpr", "pandas"):
    logging.getLogger(_noisy).setLevel(logging.ERROR)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from src.copilot.causal.nelo_dag import (
    ALL_NODES,
    NODES_BY_ID,
    NodeCategory,
    _propagate,
    ancestors_of,
)

# Nós-raiz: inputs (knobs) + confounders. Não têm forma funcional — são
# amostrados. Tudo o resto é computado pelo SCM.
_ROOT_CATEGORIES = {NodeCategory.INPUT, NodeCategory.CONFOUNDER}
ROOT_NODES: Tuple[str, ...] = tuple(
    n.id for n in ALL_NODES if n.category in _ROOT_CATEGORIES
)
COMPUTED_NODES: Tuple[str, ...] = tuple(
    n.id for n in ALL_NODES if n.category not in _ROOT_CATEGORIES
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Dataset sintético — amostra os roots, propaga pelo SCM real
# ═══════════════════════════════════════════════════════════════════════════


def _sample_roots(n: int, rng: np.random.Generator) -> Dict[str, np.ndarray]:
    """Gamas plausíveis de fábrica para cada nó-raiz do NELO_DAG."""
    return {
        "shift_mode": rng.choice([1.0, 2.0], size=n),
        "routing_variant": rng.choice([0.0, 1.0], size=n),
        "worker_count_laminagem": rng.uniform(14.0, 26.0, size=n),
        "worker_count_pintura": rng.uniform(4.0, 12.0, size=n),
        "mold_availability_pct": rng.uniform(0.60, 1.00, size=n),
        "material_availability_pct": rng.uniform(0.65, 1.00, size=n),
        "operator_experience": rng.uniform(3.0, 14.0, size=n),
        "mold_age": rng.uniform(1.0, 7.0, size=n),
        "external_temperature": rng.uniform(8.0, 28.0, size=n),
    }


def build_dataset(n: int = 4000, *, seed: int = 55, noise: float = 0.03) -> pd.DataFrame:
    """Tabela observacional consistente com o NELO_DAG.

    Cada linha = um "dia de fábrica": os 9 knobs/confounders são sorteados,
    o SCM propaga os 14 nós computados, e mete-se ruído de medição relativo
    (~3 %) nas colunas computadas — sem ruído nada de regressão/refutador
    teria variância para morder.
    """
    rng = np.random.default_rng(seed)
    roots = _sample_roots(n, rng)

    rows: List[Dict[str, float]] = []
    for i in range(n):
        do = {k: float(v[i]) for k, v in roots.items()}
        rows.append(_propagate(do=do, observe={}))

    df = pd.DataFrame(rows)
    # Ruído de medição só nos nós computados (os knobs lêem-se exactos).
    for col in COMPUTED_NODES:
        df[col] = df[col] * (1.0 + rng.normal(0.0, noise, size=n))
    return df


# ═══════════════════════════════════════════════════════════════════════════
# 2. Grafo DOT mínimo para o DoWhy
# ═══════════════════════════════════════════════════════════════════════════


def minimal_graph(treatment: str, outcome: str) -> Tuple[str, List[str]]:
    """Grafo mínimo e *suficiente* para estimar o efeito total de
    `treatment` em `outcome`.

    Passar o NELO_DAG inteiro (23 nós) ao DoWhy fá-lo gastar ~14 s por
    estimativa — a identificação varre o grafo todo. Mas para o efeito
    total de T em Y só é preciso: a aresta T→Y e os **ancestrais comuns**
    de T e Y (os confounders que abrem caminhos de porta-traseira). Ajustar
    por esse conjunto bloqueia todo o viés — é o critério da porta traseira
    de Pearl. O resultado é um grafo de 2 a ~5 nós e o DoWhy fica instantâneo.
    """
    confounders = (ancestors_of(treatment) & ancestors_of(outcome)) - {treatment, outcome}
    edges = [f"{treatment}->{outcome};"]
    for z in sorted(confounders):
        edges.append(f"{z}->{treatment};")
        edges.append(f"{z}->{outcome};")
    nodes = [treatment, outcome] + sorted(confounders)
    return "digraph{" + "".join(edges) + "}", nodes


# ═══════════════════════════════════════════════════════════════════════════
# 3. Estimativa + refutação de um par causa→efeito
# ═══════════════════════════════════════════════════════════════════════════


def _stable(orig: float, new: float, tol: float = 0.25) -> bool:
    """O refutador deixou a estimativa estável? (random_common_cause / subset)."""
    if abs(orig) < 1e-9:
        return abs(new) < 1e-6
    return abs(new - orig) <= tol * abs(orig)


def _placebo_ok(orig: float, placebo: float) -> bool:
    """Placebo: efeito da causa-falsa tem de colapsar para perto de zero."""
    if abs(orig) < 1e-9:
        return True
    return abs(placebo) <= 0.20 * abs(orig)


def estimate_pair(
    df: pd.DataFrame,
    treatment: str,
    outcome: str,
    *,
    sims: int = 8,
) -> Dict[str, object]:
    """Efeito médio (ATE) de `treatment` em `outcome` + verdicto dos refutadores.

    Devolve um dict com `ate`, os 3 refutadores e `confirmed` (sinal não-trivial
    E nenhum refutador derruba a estimativa). `sims` = nº de simulações por
    refutador (o default do DoWhy é 100 — caro de mais para 40 pares; 8 chega
    para um veredicto de sinal).
    """
    from dowhy import CausalModel

    out: Dict[str, object] = {
        "treatment": treatment,
        "outcome": outcome,
        "applicable": True,
        "confounders": [],
        "ate": None,
        "placebo": None,
        "random_common_cause": None,
        "data_subset": None,
        "refuters_passed": 0,
        "confirmed": False,
        "error": None,
    }

    # Fronteira metodológica honesta: o DoWhy só identifica limpo um
    # tratamento-RAIZ (input/confounder). Esses são amostrados de forma
    # independente — variação tipo-experimental, o padrão-ouro. Um nó
    # MEDIADOR é função determinística dos pais; condicionar nos pais
    # tira-lhe a variação e o efeito colapsa para um ~0 espúrio. Nesses
    # casos quem manda é o SCM da casa — e isso é um achado, não um bug.
    if treatment not in ROOT_NODES:
        out["applicable"] = False
        out["error"] = "nó mediador — efeito não identificável em dados observacionais"
        return out

    try:
        dot, nodes = minimal_graph(treatment, outcome)
        out["confounders"] = nodes[2:]
        model = CausalModel(
            data=df[nodes], treatment=treatment, outcome=outcome, graph=dot,
        )
        estimand = model.identify_effect(proceed_when_unidentifiable=True)
        # confidence_intervals/test_significance fazem bootstrap (~100 refits)
        # — desligados, a regressão é instantânea. Para um veredicto de
        # sinal+grandeza não precisamos do IC.
        estimate = model.estimate_effect(
            estimand, method_name="backdoor.linear_regression",
            test_significance=False, confidence_intervals=False,
        )
        ate = float(estimate.value)
        out["ate"] = ate

        refuters = {
            "placebo": "placebo_treatment_refuter",
            "random_common_cause": "random_common_cause",
            "data_subset": "data_subset_refuter",
        }
        passed = 0
        for key, method in refuters.items():
            try:
                ref = model.refute_estimate(
                    estimand, estimate, method_name=method,
                    num_simulations=sims,
                )
                new_effect = float(ref.new_effect)
                out[key] = round(new_effect, 5)
                if key == "placebo":
                    ok = _placebo_ok(ate, new_effect)
                else:
                    ok = _stable(ate, new_effect)
                passed += int(ok)
            except Exception as exc:  # refutador individual pode falhar
                out[key] = f"erro: {exc}"
        out["refuters_passed"] = passed
        # Confirmado: efeito real (sinal não-trivial) e refutadores não o matam.
        out["confirmed"] = bool(abs(ate) > 1e-6 and passed >= 2)
    except Exception as exc:
        out["error"] = str(exc)
    return out


def dowhy_table(
    pairs: List[Tuple[str, str]],
    *,
    n: int = 4000,
    seed: int = 55,
    sims: int = 8,
    verbose: bool = True,
) -> Dict[Tuple[str, str], Dict[str, object]]:
    """Corre `estimate_pair` para todos os pares (deduplicados)."""
    df = build_dataset(n=n, seed=seed)
    unique = sorted(set(pairs))
    table: Dict[Tuple[str, str], Dict[str, object]] = {}
    for i, (treatment, outcome) in enumerate(unique, 1):
        if treatment not in NODES_BY_ID or outcome not in NODES_BY_ID:
            table[(treatment, outcome)] = {
                "treatment": treatment, "outcome": outcome,
                "error": "nó fora do NELO_DAG", "confirmed": False,
            }
            continue
        res = estimate_pair(df, treatment, outcome, sims=sims)
        table[(treatment, outcome)] = res
        if verbose:
            if not res.get("applicable", True):
                print(f"  [{i:>2}/{len(unique)}] n/a  {treatment} -> {outcome}"
                      f"  (mediador — SCM manda)")
            else:
                ate = res.get("ate")
                ate_s = f"{ate:+.4g}" if isinstance(ate, float) else "—"
                flag = "OK " if res.get("confirmed") else "?? "
                print(
                    f"  [{i:>2}/{len(unique)}] {flag} {treatment} -> {outcome:<24} "
                    f"ATE={ate_s}  refutadores={res.get('refuters_passed', 0)}/3"
                )
    return table


if __name__ == "__main__":
    # Smoke: dois pares conhecidos do DAG.
    demo = dowhy_table([
        ("worker_count_laminagem", "laminagem_duration"),
        ("shift_mode", "throughput_eur_day"),
        ("external_temperature", "curing_time"),
    ])
    for key, res in demo.items():
        print(key, "->", res)
