"""Function-calling specs for NL→YAML rule authoring (Sprint Q.17.B).

Generates JSON-schema specs that Ollama / OpenAI / Anthropic accept as
``tools`` parameter. The schemas are derived programmatically from the
Pydantic models in ``rule_schema`` so the whitelist stays consistent
across:

- Pydantic validation at load (``rule_schema.Rule``)
- LLM function-calling constraint (this module)
- UI dropdowns / autocomplete (Q.17.C frontend reads same JSON)

Usage::

    from src.governance.yaml_policy.llm_tools import propose_rule_tool

    tools = [propose_rule_tool()]
    response = await ollama.chat_with_tools(messages=..., tools=tools)
    yaml_payload = response.tool_calls[0].arguments  # already DSL-shaped

The LLM emits only what fits the schema; impossible structures (e.g.
``then.action == "wipe_database"``) cannot be represented in the spec
and the LLM will not produce them.
"""

from __future__ import annotations

import json
from typing import Any

from .rule_schema import (
    EVENT_FIELDS,
    ACTION_PARAMS,
    ActionType,
    AxiomRequirement,
    ConditionOp,
    EventType,
)


_TOOL_NAME = "propose_rule"


def _enum_values(enum_cls: type) -> list[str]:
    return [m.value for m in enum_cls]


def _condition_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["field", "op", "value"],
        "properties": {
            "field": {
                "type": "string",
                "minLength": 1,
                "maxLength": 120,
                "description": (
                    "Field of the trigger event payload. "
                    "Allowed fields depend on the chosen event_type — "
                    "see when.event description."
                ),
            },
            "op": {
                "type": "string",
                "enum": _enum_values(ConditionOp),
                "description": (
                    "Comparison operator. eq/ne for equality; "
                    "gt/lt/gte/lte for ordering; in for set membership; "
                    "matches for regex (compiled with timeout)."
                ),
            },
            "value": {
                "description": (
                    "Comparison value. JSON-typed: string, number, "
                    "boolean, array (for op=in), or object."
                ),
            },
        },
    }


def _trigger_schema() -> dict[str, Any]:
    event_descriptions = "; ".join(
        f"{ev.value}: fields={sorted(EVENT_FIELDS[ev])}"
        for ev in EventType
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["event", "conditions"],
        "properties": {
            "event": {
                "type": "string",
                "enum": _enum_values(EventType),
                "description": (
                    f"The event type the rule subscribes to. Each event "
                    f"exposes a fixed set of fields that conditions can "
                    f"reference: {event_descriptions}"
                ),
            },
            "conditions": {
                "type": "array",
                "items": _condition_schema(),
                "description": (
                    "Conditions are AND-joined. For OR semantics, emit "
                    "two separate rules. Empty list = unconditional fire."
                ),
            },
        },
    }


def _action_schema() -> dict[str, Any]:
    action_descriptions = "; ".join(
        f"{a.value}: params={sorted(ACTION_PARAMS[a])}"
        for a in ActionType
    )
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "params"],
        "properties": {
            "action": {
                "type": "string",
                "enum": _enum_values(ActionType),
                "description": (
                    f"The action type to dispatch. Each action accepts a "
                    f"fixed set of params: {action_descriptions}. "
                    f"modify_fitness.multiplier must be in [0.5, 1.5]; "
                    f"notify.channel must be one of "
                    f"alerts|timeline|dashboard|governance."
                ),
            },
            "params": {
                "type": "object",
                "description": (
                    "Action-specific parameters; keys must match the "
                    "params list of the chosen action type."
                ),
            },
        },
    }


def _constraints_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "axioms_required": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": _enum_values(AxiomRequirement),
                },
                "description": (
                    "Spelke axioms the rule pledges to preserve. The "
                    "Q.17.E sandbox dry-runs each axiom and refuses "
                    "activation if any fails."
                ),
            },
        },
    }


def _safety_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "max_fires_per_day": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10000,
                "default": 10,
                "description": (
                    "Hard cap on rule firings per UTC day. Excess "
                    "auto-suspends the rule and alerts the admin."
                ),
            },
            "expires": {
                "type": "string",
                "format": "date",
                "description": (
                    "ISO date after which the rule auto-suspends. "
                    "Omit for no expiry."
                ),
            },
        },
    }


def _rule_object_schema() -> dict[str, Any]:
    """Full JSON Schema for a single Rule.

    This is the ``arguments`` payload the LLM emits when it picks the
    ``propose_rule`` tool. The runtime then ``Rule.model_validate(args)``
    — Pydantic catches anything the JSON-schema didn't.
    """
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["id", "description", "when", "then"],
        "properties": {
            "id": {
                "type": "string",
                "minLength": 3,
                "maxLength": 120,
                "pattern": r"^[a-z0-9][a-z0-9._-]*$",
                "description": (
                    "Stable rule identifier; lowercase alphanumeric "
                    "with - . _ separators (no doubles). Used in audit "
                    "trails. Example: 'paulo-friday-replacement-2026'."
                ),
            },
            "description": {
                "type": "string",
                "minLength": 4,
                "maxLength": 400,
                "description": (
                    "Human-readable description in PT-PT. Shown in "
                    "the diff modal at approval time."
                ),
            },
            "when": _trigger_schema(),
            "then": {
                "type": "array",
                "minItems": 1,
                "maxItems": 10,
                "items": _action_schema(),
                "description": "Actions dispatched in order when conditions match.",
            },
            "constraints": _constraints_schema(),
            "safety": _safety_schema(),
        },
    }


def propose_rule_tool() -> dict[str, Any]:
    """Return the OpenAI/Ollama-compatible function-calling tool spec.

    The shape matches both the OpenAI ``tools`` parameter and the Ollama
    ``tools`` parameter (which is OpenAI-compatible since 0.4).

    The LLM is instructed to call this tool when the user describes a
    rule in natural language. The returned ``arguments`` will already be
    a valid Rule JSON because the JSON Schema enforces the whitelists.
    """
    return {
        "type": "function",
        "function": {
            "name": _TOOL_NAME,
            "description": (
                "Propose a declarative business rule from natural-language input. "
                "The LLM should extract: (1) the trigger event and conditions, "
                "(2) the action(s) to dispatch, (3) which Spelke axioms the rule "
                "preserves, (4) safety knobs (rate limit, expiry). "
                "ALL FIELDS ARE WHITELISTED — the LLM cannot invent event types, "
                "action types, condition operators, or per-event field names. "
                "If the user request cannot be expressed within the whitelists, "
                "respond in chat without calling this tool, explaining the gap."
            ),
            "parameters": _rule_object_schema(),
        },
    }


def propose_rule_tool_json() -> str:
    """Convenience: JSON-encoded tool spec for clients that need a string."""
    return json.dumps(propose_rule_tool(), indent=2, sort_keys=False)


# ---------------------------------------------------------------------------
# Inverse: convert a validated Rule back to YAML for the diff modal preview
# ---------------------------------------------------------------------------


def rule_to_yaml_dict(rule_args: dict[str, Any]) -> dict[str, Any]:
    """Re-shape an LLM-emitted rule into the YAML structure for ``tenant_rules.yaml``.

    The LLM's tool-call arguments map 1:1 to Rule's Pydantic shape, so
    this is essentially a passthrough plus a wrapper version envelope.
    Used by the Q.17.C diff modal to render side-by-side current vs
    proposed.
    """
    # Validate first — never preview an invalid rule.
    from .rule_schema import Rule

    rule = Rule.model_validate(rule_args)
    return rule.model_dump(mode="json", exclude_none=True, exclude_defaults=False)
