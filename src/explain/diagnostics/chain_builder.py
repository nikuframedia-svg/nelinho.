"""
ProdPlan ONE — CausalChain emission for diagnostic handlers (Q.15.D.5)
=======================================================================

The 3 D.1-D.4 handlers (ERRO-TREE, Reichenbach, Mill's) produce
``Hypothesis`` and ``Change`` objects. To feed the Camada-4 ABL
training pipeline (Q.13.D) they have to be lifted into the canonical
``CausalChain`` Pydantic shape that ``verify_chain_dict`` validates
against the 5-layer schema (syntactic, DAG-consistent, direction,
NLI, kernel).

This module is the bridge:

  * :func:`build_chain_from_hypothesis` — Hypothesis → CausalChain
  * :func:`build_chain_from_mill_changes` — best Change → CausalChain
  * :func:`record_diagnostic_chain` — build → verify → record_causal_audit

Hypothesis-type → DAG-node mapping
-----------------------------------

Each diagnostic ``type`` corresponds to a NELO_DAG node. The mapping
is hard-coded (small lookup table; documented inline). When a future
hypothesis type doesn't have a known mapping, this module returns
``None`` rather than fabricating an invalid chain. The ABL job
receives only chains the verifier accepts; rejected ones never land
in the training corpus.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from src.copilot.causal.chain import (
    AristotleAnnotation,
    CausalChain,
    CausalClaim,
)
from src.explain.diagnostics.types import Hypothesis, TriggerType

logger = logging.getLogger(__name__)


# Hypothesis type → (root_cause_dag_node, default_target, mechanism_path)
# The mechanism path is the ordered list of intermediate nodes the
# claim emits — must form a valid path in NELO_DAG so the
# `_layer_direction` verifier accepts it.
_HYPOTHESIS_TO_DAG: Dict[str, Dict[str, Any]] = {
    "mold_degradation": {
        # Path validated against NELO_DAG:
        #   mold_age → quality_risk_score → rework_rate → throughput_eur_day
        "root_cause": "mold_age",
        "target": "throughput_eur_day",
        "mechanism": [
            ("mold_age", "increase",
             "Molde degradado tem geometria mais incerta."),
            ("quality_risk_score", "increase",
             "Lote completo passa a ser de risco elevado."),
            ("rework_rate", "increase",
             "Mais barcos voltam para reparação."),
            ("throughput_eur_day", "decrease",
             "Linha perde €/dia em retrabalho."),
        ],
        "aristotle": AristotleAnnotation(
            material="Molde físico desgastado.",
            efficient="Operador da Prep. Molde detecta a degradação tarde.",
            final="Throughput €/dia.",
        ),
    },
    "shared_mold": {
        "root_cause": "mold_age",
        "target": "throughput_eur_day",
        "mechanism": [
            ("mold_age", "increase",
             "Molde partilhado por múltiplas fases tem desgaste alto."),
            ("quality_risk_score", "increase",
             "Risco de qualidade sobe nas fases afectadas."),
            ("rework_rate", "increase",
             "Retrabalho sobe nas fases que partilham o molde."),
            ("throughput_eur_day", "decrease",
             "Throughput cai porque várias fases atrasam."),
        ],
        "aristotle": AristotleAnnotation(
            material="Molde físico — recurso partilhado.",
            final="Throughput €/dia.",
        ),
    },
    "worker_skill": {
        # Path: operator_experience → quality_risk_score → rework_rate
        "root_cause": "operator_experience",
        "target": "rework_rate",
        "mechanism": [
            ("operator_experience", "decrease",
             "Operador com experiência abaixo da fase exige."),
            ("quality_risk_score", "increase",
             "Probabilidade de defeito sobe na operação."),
            ("rework_rate", "increase",
             "Mais barcos voltam para reparação."),
        ],
        "aristotle": AristotleAnnotation(
            efficient="Operador específico identificado.",
            final="Quality risk + rework rate.",
        ),
    },
    "shared_workers": {
        "root_cause": "operator_experience",
        "target": "rework_rate",
        "mechanism": [
            ("operator_experience", "decrease",
             "Operador partilhado sobrecarregado afecta competência."),
            ("quality_risk_score", "increase",
             "Sobrecarga eleva a probabilidade de defeito."),
            ("rework_rate", "increase",
             "Retrabalho sobe nas fases que partilham o operador."),
        ],
        "aristotle": AristotleAnnotation(
            efficient="Operador partilhado com sobrecarga horária.",
            final="Quality risk + rework rate.",
        ),
    },
    "overload": {
        # Path: laminagem_queue_hours → makespan_hours → throughput_eur_day
        "root_cause": "laminagem_queue_hours",
        "target": "throughput_eur_day",
        "mechanism": [
            ("laminagem_queue_hours", "increase",
             "Fila de Laminagem cresce, pressão sobe."),
            ("makespan_hours", "increase",
             "Plano alarga-se."),
            ("throughput_eur_day", "decrease",
             "Linha perde capacidade efectiva."),
        ],
        "aristotle": AristotleAnnotation(
            formal="Plano CPO sob pressão.",
            final="Throughput €/dia.",
        ),
    },
    "shared_transport_pressure": {
        # Path: makespan_hours → throughput_eur_day (direct)
        "root_cause": "makespan_hours",
        "target": "throughput_eur_day",
        "mechanism": [
            ("makespan_hours", "increase",
             "Pressão de expedição força aceleração transversal."),
            ("throughput_eur_day", "decrease",
             "Linha perde €/dia sob pressão."),
        ],
        "aristotle": AristotleAnnotation(
            formal="Plano de transporte sob pressão.",
            final="Throughput €/dia.",
        ),
    },
    "cascade_effect": {
        # Cascade types default to mold_age → quality_risk_score →
        # rework_rate (most common cascade in NELO history).
        "root_cause": "mold_age",
        "target": "rework_rate",
        "mechanism": [
            ("mold_age", "increase",
             "Causa raiz upstream identificada via cascata."),
            ("quality_risk_score", "increase",
             "Defeitos propagam-se para a fase a jusante."),
            ("rework_rate", "increase",
             "Retrabalho a jusante."),
        ],
        "aristotle": AristotleAnnotation(
            material="Cascata upstream identificada.",
            final="Rework rate.",
        ),
    },
}


# Mill's diff Change category → mapping. Mostly mirrors hypothesis
# but Mill's reports "shifts", not "hypotheses with confidence", so
# the rationale lines mention the magnitude when known.
_MILL_CATEGORY_TO_DAG: Dict[str, Dict[str, Any]] = {
    "mold": _HYPOTHESIS_TO_DAG["mold_degradation"],
    "worker": _HYPOTHESIS_TO_DAG["worker_skill"],
    "volume": _HYPOTHESIS_TO_DAG["overload"],
    "transport": _HYPOTHESIS_TO_DAG["shared_transport_pressure"],
}


def build_chain_from_hypothesis(
    hypothesis: Hypothesis,
    *,
    trigger: TriggerType,
    handler: str = "erro_tree",
) -> Optional[CausalChain]:
    """Lift a Hypothesis into a verifiable CausalChain.

    Returns ``None`` when the hypothesis type isn't mapped — the
    audit pipeline ignores None and the LLM falls back to the
    "improvising" warning rather than emitting a chain that fails
    verification.

    ``handler`` is included in the question template for traceability:
    a chain in the ABL corpus carries enough context that
    ``where did this row come from?`` is answerable from the chain
    text alone.
    """
    template = _HYPOTHESIS_TO_DAG.get(hypothesis.type)
    if template is None:
        logger.debug(
            "build_chain_from_hypothesis: no DAG mapping for type=%s",
            hypothesis.type,
        )
        return None

    mechanism_claims = [
        CausalClaim(node=node, direction=direction, rationale=rationale)
        for node, direction, rationale in template["mechanism"]
    ]
    return CausalChain(
        question=(
            f"[{handler}] Why did {trigger.value} happen? "
            f"(entity: {hypothesis.entity})"
        ),
        target=template["target"],
        root_cause=template["root_cause"],
        mechanism=mechanism_claims,
        confidence=hypothesis.confidence,
        evidence=list(hypothesis.evidence),
        recommendation=_recommendation_for(hypothesis),
        aristotle=template.get("aristotle"),
        counterfactual=_counterfactual_for(hypothesis),
    )


def build_chain_from_mill_change(
    change: Any,            # Change dataclass; avoid circular import
    *,
    metric: str,
    phase_id: Optional[str] = None,
) -> Optional[CausalChain]:
    """Lift the strongest Mill's-diff Change into a CausalChain.

    Returns ``None`` when the change category isn't mapped (material /
    shift / routing today have no chain because the underlying data
    isn't there yet).
    """
    template = _MILL_CATEGORY_TO_DAG.get(change.category)
    if template is None:
        return None

    mechanism_claims = [
        CausalClaim(node=node, direction=direction, rationale=rationale)
        for node, direction, rationale in template["mechanism"]
    ]
    target_text = (
        f"{metric} on phase {phase_id}" if phase_id else metric
    )
    return CausalChain(
        question=(
            f"[mill_diff] What changed for {target_text}? "
            f"(top: {change.change})"
        ),
        target=template["target"],
        root_cause=template["root_cause"],
        mechanism=mechanism_claims,
        confidence=float(change.correlation),
        evidence=list(change.evidence),
        recommendation=None,  # Mill's diff is descriptive, not prescriptive.
        aristotle=template.get("aristotle"),
    )


async def record_diagnostic_chain(
    *,
    session: Any,
    tenant_id: UUID,
    conversation_id: UUID,
    chain: Optional[CausalChain],
) -> bool:
    """Verify + persist via :func:`record_causal_audit` (Q.13.D).

    Returns ``True`` when the chain was persisted; ``False`` when the
    chain was None / verification failed / persist crashed (best-effort).
    Caller (the orchestrator's investigate / find_common_cause /
    what_changed methods) treats this as a side-effect — the diagnostic
    result still reaches the operator regardless.
    """
    if chain is None:
        return False
    try:
        from src.copilot.causal.runtime import record_causal_audit
        msg = await record_causal_audit(
            session=session,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            chain_dict=chain.model_dump(),
        )
        return msg is not None
    except Exception as exc:
        logger.warning(
            "record_diagnostic_chain: failed (%s) — chain not persisted",
            exc,
        )
        return False


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────


def _recommendation_for(hypothesis: Hypothesis) -> Optional[str]:
    """Map hypothesis type to a one-line operator action."""
    rec_map = {
        "mold_degradation": (
            f"Manutenção do molde {hypothesis.entity} (~4h, ~€400)."
        ),
        "shared_mold": (
            f"Reagendar produção que use o molde {hypothesis.entity} "
            "para um molde alternativo enquanto se faz manutenção."
        ),
        "worker_skill": (
            f"Trocar {hypothesis.entity} por operador mais experiente "
            "OU emparelhar com sénior para supervisão."
        ),
        "shared_workers": (
            f"Aliviar a carga de {hypothesis.entity} — atrasar barcos "
            "não-urgentes nas fases envolvidas."
        ),
        "overload": (
            "Atrasar barcos não-urgentes para reduzir WIP."
        ),
        "shared_transport_pressure": (
            "Negociar adiamento de barcos não-críticos da expedição "
            "próxima OU mobilizar turno extra."
        ),
        "cascade_effect": (
            f"Resolver a fase upstream em {hypothesis.entity} — "
            "a downstream resolve-se sozinha."
        ),
    }
    return rec_map.get(hypothesis.type)


def _counterfactual_for(hypothesis: Hypothesis) -> Optional[str]:
    """One-sentence counterfactual for the chain's contract."""
    cf_map = {
        "mold_degradation": (
            f"Se o molde {hypothesis.entity} estivesse em manutenção há "
            "1 semana, o retrabalho estaria perto da média histórica."
        ),
        "shared_mold": (
            f"Se houvesse molde de reserva para {hypothesis.entity}, "
            "as fases afectadas trabalhariam em paralelo."
        ),
        "worker_skill": (
            f"Se {hypothesis.entity} tivesse 6 meses extra de tier, "
            "a taxa de erro alinharia com a média da fase."
        ),
        "shared_workers": (
            f"Se {hypothesis.entity} cumprisse só 40h/semana, as duas "
            "fases drift-ariam menos juntas."
        ),
        "overload": (
            "Se o WIP estivesse no nível normal (~350), o makespan "
            "regrediria e o throughput recuperaria."
        ),
        "shared_transport_pressure": (
            "Se a expedição grande não estivesse na próxima semana, "
            "as fases não estariam a fazer overtime simultâneo."
        ),
        "cascade_effect": None,  # cascades are downstream-only narratives.
    }
    return cf_map.get(hypothesis.type)


__all__ = [
    "build_chain_from_hypothesis",
    "build_chain_from_mill_change",
    "record_diagnostic_chain",
]
