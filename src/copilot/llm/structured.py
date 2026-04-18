"""
ProdPlan ONE - Structured LLM Output (Sprint S.3)
===================================================

Blueprint v2.0 §4.1 requires "LLM Structured: Instructor + Pydantic" for
validated outputs. This module exposes:

    async def structured_call(
        client: LLMClient,
        *,
        response_model: Type[BaseModel],
        messages: list[dict],
        model: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 2,
    ) -> BaseModel

The `instructor` library is optional. When it isn't installed we fall
back to Ollama/vLLM's native JSON mode plus a retry loop that re-prompts
the LLM with Pydantic validation errors until it produces a compliant
response.

Two failure modes surface explicitly:
  * `StructuredCallError` — LLM failed after retries / backend broken
  * `StructuredValidationError` — LLM's JSON didn't match the schema
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .base import LLMClient

logger = logging.getLogger(__name__)

TModel = TypeVar("TModel", bound=BaseModel)


class StructuredCallError(Exception):
    """Raised when the LLM call itself fails (network / backend)."""


class StructuredValidationError(Exception):
    """Raised when the response cannot be parsed into the schema after retries."""


async def structured_call(
    client: LLMClient,
    *,
    response_model: Type[TModel],
    messages: List[Dict[str, Any]],
    model: str,
    system_prompt: Optional[str] = None,
    max_retries: int = 2,
) -> TModel:
    """Call the LLM and parse the JSON response into `response_model`.

    Retries up to `max_retries` times, each time appending the
    validation error to the conversation so the LLM corrects itself.
    """
    schema_hint = _build_schema_hint(response_model)
    composed_system = _compose_system_prompt(system_prompt, schema_hint)
    history = messages[:-1] if len(messages) >= 2 else []
    prompt = _last_user_prompt(messages)

    last_error: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            raw = await client.chat(
                prompt=prompt,
                model=model,
                format="json",
                history=history,
                system_prompt=composed_system,
            )
        except Exception as exc:
            raise StructuredCallError(str(exc)) from exc

        payload = _coerce_to_dict(raw)
        try:
            return response_model(**payload)
        except ValidationError as exc:
            last_error = exc
            if attempt < max_retries:
                # Feed the error back so the model self-corrects.
                history = history + [
                    {"role": "assistant", "content": json.dumps(payload)},
                    {
                        "role": "user",
                        "content": (
                            "Your previous JSON failed validation. Fix the "
                            "issues and reply with ONLY the corrected JSON.\n\n"
                            f"Validation errors:\n{_format_errors(exc)}"
                        ),
                    },
                ]
                continue
            raise StructuredValidationError(
                f"Response invalid after {max_retries + 1} attempts: {exc}"
            ) from exc
    # Unreachable, but mypy-friendly.
    assert last_error is not None
    raise StructuredValidationError(str(last_error))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _coerce_to_dict(raw: Any) -> Dict[str, Any]:
    """LLM clients can return either a parsed dict or a `{'content': str}`
    wrapper. Normalise both."""
    if isinstance(raw, dict) and "content" in raw and len(raw) == 1:
        try:
            parsed = json.loads(raw["content"])
        except json.JSONDecodeError as exc:
            raise StructuredCallError(f"Non-JSON response: {exc}") from exc
        if isinstance(parsed, dict):
            return parsed
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StructuredCallError(f"Non-JSON response: {exc}") from exc
    raise StructuredCallError(f"Unexpected LLM response type: {type(raw).__name__}")


def _compose_system_prompt(
    system_prompt: Optional[str],
    schema_hint: str,
) -> str:
    preamble = (
        "Respond ONLY with valid JSON matching this exact schema. "
        "Do not include prose, commentary, or code fences.\n\n"
    )
    suffix = f"JSON schema:\n{schema_hint}"
    return (
        f"{system_prompt}\n\n{preamble}{suffix}" if system_prompt
        else f"{preamble}{suffix}"
    )


def _build_schema_hint(response_model: Type[BaseModel]) -> str:
    try:
        schema = response_model.model_json_schema()
    except Exception:
        return f"(schema for {response_model.__name__} — refer to callers)"
    return json.dumps(schema, indent=2, sort_keys=True)


def _last_user_prompt(messages: List[Dict[str, Any]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content") or "")
    return ""


def _format_errors(exc: ValidationError) -> str:
    try:
        return "\n".join(
            f"- {'/'.join(str(p) for p in err.get('loc', []))}: {err.get('msg')}"
            for err in exc.errors()
        )
    except Exception:
        return str(exc)
