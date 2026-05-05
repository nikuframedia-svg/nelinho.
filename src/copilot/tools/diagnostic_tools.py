"""
ProdPlan ONE — Diagnostic tool specs (Sprint Q.15.0)
=====================================================

Function-calling specifications for the 3 diagnostic handlers planned
for Sprint Q.15.D.1 → D.4. The shape matches the OpenAI / Ollama tools
API so the LLM can pick a tool by name + emit args, and the dispatch
layer in :mod:`src.copilot.service` translates the call into an HTTP
invocation against the existing ``/v1/explain/diagnostics/...``
endpoints.

Why specs first (before handlers)
---------------------------------

Q.15.0 ships the prompt + the tool scaffolding *before* D.1 ships the
ERRO-TREE handler. This means:

  * The LLM sees the tool list on every diagnostic-intent question.
  * If the corresponding capability is not Wired (per
    ``capabilities.fetch_capability_flags``), the dispatch layer
    short-circuits with a structured "tool not wired" warning so the
    LLM falls back to "describe the framework" mode honestly.
  * Once D.1 lands and the operator flips
    ``copilot.diagnostics.erro_tree.enabled = True``, the tool
    transparently becomes invocable — **no prompt rewrite needed**.

Trade-off: we ship 3 unused specs for 4-8 weeks. Worth it because the
alternative is hot-rewriting the prompt (and re-running every regression
test) for each handler delivery.

Design notes
------------

  * **Strict JSON Schema** — the LLM is invited to emit args, not
    free-form. Validation happens at dispatch (see ``service.py``).
  * **Defaults defined here** — `period_days=7`, `metric="error_rate"`.
    Avoids redundant kwargs on every call; LLM can override.
  * **Enums for trigger/metric** — pin the vocabulary so handler-side
    branching stays narrow.
  * **Required fields minimal** — the LLM should fail-fast when it's
    missing data. ``trigger`` is the only required arg for
    ``investigate_quality_drop``; everything else has a sensible default.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ───────────────────────────────────────────────────────────────────────────
# Tool 1 — investigate_quality_drop (ERRO-TREE, Sprint Q.15.D.1)
# ───────────────────────────────────────────────────────────────────────────

INVESTIGATE_QUALITY_DROP: Dict[str, Any] = {
    "name": "investigate_quality_drop",
    "description": (
        "Run the ERRO-TREE diagnostic cascade when the operator asks "
        "'porque é que a qualidade caiu?', 'porque é que o throughput desceu?', "
        "ou 'investigar fase X'. Returns a CausalChain with root_cause, "
        "evidence, recommendation, and a confidence + 95% CI. "
        "Use ONLY when capability `diagnostics.erro_tree.enabled` is Wired."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "trigger": {
                "type": "string",
                "enum": ["quality_drop", "throughput_drop", "delay_spike"],
                "description": (
                    "Which symptom prompted the investigation. "
                    "quality_drop = retrabalho subiu; "
                    "throughput_drop = €/dia caiu; "
                    "delay_spike = lead time aumentou."
                ),
            },
            "period_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 90,
                "default": 7,
                "description": (
                    "Lookback window in days. Default 7 — captures a "
                    "weekly drift without the noise of a single bad day."
                ),
            },
            "phase_id": {
                "type": "string",
                "description": (
                    "Optional — focus the investigation on a single "
                    "phase (e.g., 'LAMINAGEM'). Omit to run global."
                ),
            },
        },
        "required": ["trigger"],
    },
}


# ───────────────────────────────────────────────────────────────────────────
# Tool 2 — find_common_cause (Reichenbach, Sprint Q.15.D.2 + D.3)
# ───────────────────────────────────────────────────────────────────────────

FIND_COMMON_CAUSE: Dict[str, Any] = {
    "name": "find_common_cause",
    "description": (
        "Reichenbach common-cause analysis: when 2+ phases drift "
        "simultaneously, find the shared resource (mold, workers, "
        "material lot, transport pressure, shift, or upstream cascade) "
        "rather than diagnosing each phase isolated. "
        "Use ONLY when capability `diagnostics.reichenbach.enabled` is Wired."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "deviating_phases": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
                "description": (
                    "Phase ids that show abnormal drift in the same "
                    "window. Caller is responsible for pre-filtering "
                    "(usually via the multivariate drift monitor)."
                ),
            },
            "period_days": {
                "type": "integer",
                "minimum": 1,
                "maximum": 90,
                "default": 7,
            },
            "metric": {
                "type": "string",
                "enum": ["error_rate", "duration", "throughput"],
                "default": "error_rate",
                "description": (
                    "Which metric the phases drifted on. error_rate is "
                    "the typical signal for quality common-cause."
                ),
            },
        },
        "required": ["deviating_phases"],
    },
}


# ───────────────────────────────────────────────────────────────────────────
# Tool 3 — what_changed (Mill's method, Sprint Q.15.D.4)
# ───────────────────────────────────────────────────────────────────────────

WHAT_CHANGED: Dict[str, Any] = {
    "name": "what_changed",
    "description": (
        "Mill's method of difference: compare a 'good' period with a "
        "'bad' period and rank what changed by Cohen's d correlation. "
        "Returns a list of changes (molds, workers, volume, materials, "
        "transports, shifts, routing) with likely_cause flags. "
        "Use ONLY when capability `diagnostics.mill_diff.enabled` is Wired."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "good_period_start": {
                "type": "string",
                "format": "date",
                "description": "ISO date — start of the 'before' period.",
            },
            "good_period_end": {
                "type": "string",
                "format": "date",
                "description": "ISO date — end of the 'before' period (inclusive).",
            },
            "bad_period_start": {
                "type": "string",
                "format": "date",
                "description": "ISO date — start of the 'after' period.",
            },
            "bad_period_end": {
                "type": "string",
                "format": "date",
                "description": "ISO date — end of the 'after' period (inclusive).",
            },
            "metric": {
                "type": "string",
                "enum": ["error_rate", "throughput", "lead_time"],
                "default": "error_rate",
            },
            "phase_id": {
                "type": "string",
                "description": (
                    "Optional — restrict the comparison to one phase."
                ),
            },
        },
        "required": [
            "good_period_start",
            "good_period_end",
            "bad_period_start",
            "bad_period_end",
        ],
    },
}


# ───────────────────────────────────────────────────────────────────────────
# Registry
# ───────────────────────────────────────────────────────────────────────────

ALL_DIAGNOSTIC_TOOLS: List[Dict[str, Any]] = [
    INVESTIGATE_QUALITY_DROP,
    FIND_COMMON_CAUSE,
    WHAT_CHANGED,
]


# Maps tool name → the capability config key that gates it. Used by
# the dispatch layer to short-circuit calls when the capability isn't
# Wired AND to compose targeted "tool not wired" warnings.
TOOL_CAPABILITY_MAP: Dict[str, str] = {
    INVESTIGATE_QUALITY_DROP["name"]: "diagnostics.erro_tree.enabled",
    FIND_COMMON_CAUSE["name"]: "diagnostics.reichenbach.enabled",
    WHAT_CHANGED["name"]: "diagnostics.mill_diff.enabled",
}


def tools_for_wired_capabilities(
    flags: Dict[str, bool],
) -> List[Dict[str, Any]]:
    """Return only the tool specs whose capability is Wired.

    Used by the service to decide which tools to advertise to the LLM
    on a given request — surfacing aspirational tools would invite the
    model to invent calls that the dispatch layer would reject anyway.
    """
    return [
        tool for tool in ALL_DIAGNOSTIC_TOOLS
        if flags.get(TOOL_CAPABILITY_MAP[tool["name"]], False)
    ]


__all__ = [
    "ALL_DIAGNOSTIC_TOOLS",
    "FIND_COMMON_CAUSE",
    "INVESTIGATE_QUALITY_DROP",
    "TOOL_CAPABILITY_MAP",
    "WHAT_CHANGED",
    "tools_for_wired_capabilities",
]
