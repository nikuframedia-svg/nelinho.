"""
ProdPlan ONE — RLM agent loop (Sprint F.4)
=============================================

Minimal Recursive Language Model: the LLM, instead of receiving a
200k-token factory dump in a single prompt, gets a small catalogue of
typed sub-queries and asks for exactly what it needs. Each sub-query
response is ≤100 tokens, so the running conversation grows linearly
with the number of questions asked, not with factory size.

The loop is deliberately small: it is *not* a general agent framework.
It implements **one** pattern — ``think → query → observe → …`` —
with a hard cap on iterations (``max_steps``) and a structured
protocol the LLM must respect (single JSON object per step, schema
validated by Pydantic).

Protocol
--------
At each step the LLM receives:

    # SYSTEM
    Tu és um analista da fábrica NELO. Tens acesso a sub-queries:
    - wip: Work-in-progress snapshot…
    - bottlenecks: …
    (see FactoryStateQuery.catalogue_text)

    Responde SEMPRE com um JSON deste formato:
      {"action": "query", "name": "<subquery>", "params": {...}}
      {"action": "answer", "text": "<resposta final>"}

    # USER
    <pergunta do operador>

    # (após cada query:)
    # ASSISTANT-TOOL
    {"query": "bottlenecks", "result": {...}}

The agent stops when the LLM emits ``action="answer"`` OR
``max_steps`` is reached (whichever comes first). Out-of-schema LLM
output is caught once per step, with a retry hint appended to the
conversation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, ValidationError

from src.copilot.rlm.factory_state_query import FactoryStateQuery

logger = logging.getLogger(__name__)


# ─── Protocol schemas ─────────────────────────────────────────────────────


class QueryAction(BaseModel):
    action: Literal["query"]
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)


class AnswerAction(BaseModel):
    action: Literal["answer"]
    text: str


AgentStep = Union[QueryAction, AnswerAction]


def parse_action(raw: str) -> AgentStep:
    """Turn raw LLM text into a validated :class:`AgentStep`.

    Tolerates a leading code fence (the Ollama default on some
    models) and arbitrary prose around the JSON object — we locate
    the first ``{`` and use :class:`json.JSONDecoder.raw_decode` so
    anything after the first valid object is ignored.
    """
    text = raw.strip()
    if "```" in text:
        # Prefer the content of a code-fenced block that starts with
        # a JSON object — ignore everything else.
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("{"):
                text = part
                break

    first_brace = text.find("{")
    if first_brace == -1:
        raise ValueError("LLM response contains no JSON object")

    decoder = json.JSONDecoder()
    try:
        payload, _end = decoder.raw_decode(text[first_brace:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM JSON is malformed: {exc}") from exc

    action = payload.get("action") if isinstance(payload, dict) else None
    if action == "query":
        return QueryAction(**payload)
    if action == "answer":
        return AnswerAction(**payload)
    raise ValidationError.from_exception_data(
        "AgentStep",
        [{"type": "literal_error", "loc": ("action",), "input": action}],
    )


# ─── Transcript ───────────────────────────────────────────────────────────


@dataclass
class AgentTurn:
    role: str
    content: str


@dataclass
class AgentTrace:
    """Everything the loop did — kept for audit + UI trace display."""
    question: str
    answer: Optional[str] = None
    steps_used: int = 0
    turns: List[AgentTurn] = field(default_factory=list)
    queries_run: List[Dict[str, Any]] = field(default_factory=list)
    terminated_reason: str = "complete"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "steps_used": self.steps_used,
            "terminated_reason": self.terminated_reason,
            "queries": self.queries_run,
            "turns": [{"role": t.role, "content": t.content} for t in self.turns],
        }


# ─── LLM callback contract ────────────────────────────────────────────────

# The agent only depends on a single async callback. Tests pass a
# canned sequence; production passes a wrapper over `LLMClient.chat`.
LLMCall = Callable[[List[AgentTurn]], Awaitable[str]]


# ─── System prompt ────────────────────────────────────────────────────────


SYSTEM_PROMPT_PT = """\
Tu és um analista da fábrica NELO. Respondes a perguntas do gestor em
português europeu, baseando-te apenas em factos que conseguiste obter
através de sub-queries.

Tens acesso às seguintes sub-queries (podes chamar uma por passo):

{catalogue}

Em cada passo devolves EXACTAMENTE um objecto JSON numa de duas formas:

  {{"action": "query", "name": "<subquery>", "params": {{...}}}}
  {{"action": "answer", "text": "<resposta final em português>"}}

REGRA CENTRAL — `causal_query` é a tua ferramenta universal para
QUALQUER pergunta numérica que envolve relações entre KPIs:

  - "se / e se / caso / quando X..."  → INTERVENÇÃO (do)
  - "observámos / vejo / dado que X..." → ABDUÇÃO (observe)
  - "tinha sido melhor / e se tivéssemos..." → CONTRAFACTUAL (do)
  - "se X e Y..." → MULTI-INTERVENÇÃO (do com vários nós)

Não procures sub-queries "temáticas" (não há `quality_query` nem
`temperature_query`). Para tudo o que envolva o impacto numérico de
um KPI noutro, chamas `causal_query` com os IDs canónicos abaixo.

NÓS DO NELO_DAG — usa EXACTAMENTE estes IDs em `target`, `do` e
`observe` (não inventes variantes; `curing_time` NÃO é
`curing_time_hours`; `mold_age` NÃO é `mold_age_avg`;
`routing_variant` NÃO é `variant` nem "B"):

{node_id_list}

VALORES PARA `do` E `observe` — sempre numéricos:
  - shift_mode: 1.0 (turno único) ou 2.0 (duplo)
  - routing_variant: 0.0 (primário) ou 1.0 (variante B)
  - mold_availability_pct, material_availability_pct: 0.0–1.0
  - external_temperature: graus Celsius (ex: 12.0, 19.0, 26.0)
  - quality_risk_score, rework_rate, on_time_delivery_pct: 0.0–1.0
  - todos os outros: o valor numérico cru no unit do baseline

EXEMPLOS CONCRETOS de `causal_query`:

  "Se passar a 2 turnos, throughput?":
    {{"action": "query", "name": "causal_query",
      "params": {{"target": "throughput_eur_day",
                "do": {{"shift_mode": 2.0}}}}}}

  "Variante B + 24 laminadores, makespan?":
    {{"action": "query", "name": "causal_query",
      "params": {{"target": "makespan_hours",
                "do": {{"routing_variant": 1.0,
                      "worker_count_laminagem": 24.0}}}}}}

  "Observamos rework_rate=0.20, throughput?":
    {{"action": "query", "name": "causal_query",
      "params": {{"target": "throughput_eur_day",
                "observe": {{"rework_rate": 0.20}}}}}}

QUANDO NÃO USAR `causal_query` (perguntas factuais sobre estado
actual): chama directamente `wip`, `bottlenecks`, `skills_risk`,
`quality`, `lead_time`, `mold_conflicts`, `preference_rules`,
`overview`. Estas devolvem o estado real, não fazem causal reasoning.

OUTRAS REGRAS:
- Nunca inventes números. Só usas valores vindos das sub-queries.
- No máximo {max_steps} sub-queries por turno. A seguir, "answer".
- Cita o delta com a precisão exacta retornada pelo kernel
  (ex: "+26 432 €/dia", não "+26 mil €" nem arredondamento).
- Se a sub-query devolve `error`, lê o campo `hint` ou
  `did_you_mean` antes de tentar de novo — corrige o ID e re-tenta
  UMA vez. Se ainda assim falhar, devolve "answer" a explicar.
"""


def _node_id_list_text() -> str:
    """Render every NELO_DAG node id with its category + unit, grouped
    by category. Inserted into the system prompt so the LLM has the
    canonical vocabulary in front of it at every turn."""
    from src.copilot.causal.nelo_dag import ALL_NODES, NodeCategory

    by_cat: Dict[str, List[Any]] = {}
    for node in ALL_NODES:
        by_cat.setdefault(node.category.value, []).append(node)

    order = [
        NodeCategory.INPUT.value,
        NodeCategory.PROCESS_TIME.value,
        NodeCategory.PROCESS_FLOW.value,
        NodeCategory.QUALITY.value,
        NodeCategory.OUTPUT.value,
        NodeCategory.CONFOUNDER.value,
    ]
    lines: List[str] = []
    for cat in order:
        nodes = by_cat.get(cat, [])
        if not nodes:
            continue
        lines.append(f"  [{cat}]")
        for n in nodes:
            lines.append(
                f"    {n.id}  ({n.unit}, baseline={n.baseline})"
            )
    return "\n".join(lines)


def build_system_prompt(max_steps: int) -> str:
    return SYSTEM_PROMPT_PT.format(
        catalogue=FactoryStateQuery.catalogue_text(),
        node_id_list=_node_id_list_text(),
        max_steps=max_steps,
    )


# ─── Agent loop ───────────────────────────────────────────────────────────


async def run_rlm_agent(
    *,
    question: str,
    state_query: FactoryStateQuery,
    llm: LLMCall,
    max_steps: int = 6,
) -> AgentTrace:
    """Drive the think→query→observe loop until ``max_steps`` or an
    ``answer`` step is emitted.

    Parameters
    ----------
    question:
        The operator's question. Injected as the initial user turn.
    state_query:
        The :class:`FactoryStateQuery` object the agent can poke.
    llm:
        Async callable taking the full transcript and returning the
        next raw LLM text. Tests pass a fixed-sequence stub.
    max_steps:
        Maximum number of sub-queries before the loop force-terminates.
    """
    trace = AgentTrace(question=question)
    trace.turns.append(AgentTurn(
        role="system", content=build_system_prompt(max_steps),
    ))
    trace.turns.append(AgentTurn(role="user", content=question))

    for step in range(max_steps):
        raw = await llm(trace.turns)
        trace.turns.append(AgentTurn(role="assistant", content=raw))
        try:
            action = parse_action(raw)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            # Hand the LLM a concrete correction and give it another
            # shot on the next iteration — but consume a step so
            # infinite loops on a broken model still terminate.
            trace.turns.append(AgentTurn(
                role="user",
                content=(
                    "A tua resposta não é um JSON válido no formato esperado. "
                    f"Erro: {exc}. Tenta de novo."
                ),
            ))
            trace.steps_used += 1
            continue

        if isinstance(action, AnswerAction):
            trace.answer = action.text
            trace.steps_used += 1
            trace.terminated_reason = "complete"
            return trace

        # action == query
        result = state_query.run(action.name, **action.params)
        trace.queries_run.append({
            "name": action.name,
            "params": action.params,
            "result": result,
        })
        observation = json.dumps(
            {"query": action.name, "result": result},
            default=str, ensure_ascii=False,
        )
        trace.turns.append(AgentTurn(role="tool", content=observation))
        trace.steps_used += 1

    trace.terminated_reason = "max_steps_reached"
    # Force a final answer from the LLM without consuming another query slot.
    trace.turns.append(AgentTurn(
        role="user",
        content=(
            "Atingiste o limite de sub-queries. Responde agora com "
            '{"action": "answer", "text": "..."}.'
        ),
    ))
    final = await llm(trace.turns)
    trace.turns.append(AgentTurn(role="assistant", content=final))
    try:
        final_action = parse_action(final)
        if isinstance(final_action, AnswerAction):
            trace.answer = final_action.text
    except Exception as exc:  # pragma: no cover — LLM misbehaviour
        trace.terminated_reason = f"forced_answer_parse_failed: {exc}"
    return trace


__all__ = [
    "AgentStep",
    "AgentTrace",
    "AgentTurn",
    "AnswerAction",
    "LLMCall",
    "QueryAction",
    "SYSTEM_PROMPT_PT",
    "build_system_prompt",
    "parse_action",
    "run_rlm_agent",
]
