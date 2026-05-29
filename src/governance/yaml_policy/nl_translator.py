"""Q.17.C — Natural-language → Rule translator via Ollama.

Two-stage pipeline:

1. **Generate.** Ollama receives the user's PT-PT natural-language input
   plus a system prompt that embeds the function-calling schema. The
   LLM is instructed to respond with a single JSON object matching the
   ``propose_rule`` tool's ``arguments`` shape.

2. **Validate.** The JSON is parsed and run through
   :class:`Rule.model_validate`. If validation fails, we retry **once**
   with the validation error appended to the prompt so the LLM can
   self-correct. Two failures → ``RuleTranslationError``.

The whitelist (12 events × 9 actions × 8 ops × 7 axioms) is enforced at
both layers — the system prompt cites it; Pydantic re-checks. The LLM
cannot invent action types because (a) the prompt says it can't and (b)
the validator would refuse.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from src.copilot.ollama_client import OllamaClient
from src.governance.yaml_policy.llm_tools import propose_rule_tool
from src.governance.yaml_policy.rule_schema import Rule
from src.shared.config import settings

_log = logging.getLogger(__name__)


class RuleTranslationError(RuntimeError):
    """Raised when the LLM fails to produce a valid Rule after retries."""

    def __init__(self, message: str, *, last_response: str | None = None,
                 last_validation_error: str | None = None):
        super().__init__(message)
        self.last_response = last_response
        self.last_validation_error = last_validation_error


def _build_system_prompt() -> str:
    """Serialize the function-calling spec into a system prompt body.

    Embedding the JSON schema directly gives the LLM all the whitelist
    constraints; instruction-following models follow the schema closely
    even without native tool calling.
    """
    spec = propose_rule_tool()
    spec_json = json.dumps(spec["function"]["parameters"], indent=2, ensure_ascii=False)

    return f"""És o autor de regras declarativas para o ProdPlan ONE (sistema de scheduling \
de uma fábrica de caiaques NELO).

O utilizador descreve uma regra de negócio em PT-PT. A tua tarefa: traduzir essa descrição \
para um objecto JSON que respeita ESTRITAMENTE o seguinte JSON Schema:

```json
{spec_json}
```

Regras absolutas:

1. **Responde APENAS com um objecto JSON válido** — sem markdown, sem prefácios, sem texto fora do JSON.
2. **Não inventes campos**: usa só os enums e fields do schema. Eventos, actions, ops, axioms são whitelist fechado.
3. Cada `when.conditions[*].field` tem que estar na lista de fields do `event` escolhido (ver descrição do enum).
4. Cada `then[*].params` tem que ter chaves dentro do whitelist do action escolhido.
5. `id` é slug em minúsculas (ex: "paulo-friday-replacement-2026"); descritivo, sem espaços.
6. `description` em PT-PT, 1-2 frases — usado pelo aprovador humano para decidir.
7. `safety.requires_human_approval` é sempre true (não emitir).
8. `safety.kill_switch` é sempre "admin_only" (não emitir).
9. `modify_fitness.multiplier` em [0.5, 1.5] (±50% máximo).
10. Se o pedido do utilizador NÃO cabe no schema (ex: action que não existe), responde com \
`{{"error": "<explicação curta em PT do que falta>"}}` em vez de inventar.

Cuidado: a versão do schema impõe `additionalProperties: false` em todos os blocos. Qualquer \
chave extra é rejeitada pelo validador.
"""


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract a JSON object from the LLM response.

    Handles common wrappings:
    - Markdown code fences (```json ... ```)
    - Leading/trailing text outside the JSON block
    - Sometimes the LLM emits ``{ ... }`` followed by an explanation
    """
    text = text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        # Find the language tag's end and the closing fence
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # If the first { is not at position 0, try to slice from it
    first_brace = text.find("{")
    if first_brace > 0:
        text = text[first_brace:]

    # Ensure we stop at the matching closing brace (handle trailing prose)
    depth = 0
    end = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end > 0:
        text = text[:end]

    return json.loads(text)


async def translate_nl_to_rule(
    nl_text: str,
    *,
    ollama: OllamaClient | None = None,
    model: str | None = None,
    max_retries: int = 1,
) -> Rule:
    """Translate natural-language rule description to a validated Rule.

    Args:
        nl_text: The user's PT-PT description (e.g. "Quando molde K1 7 ML 03
            atingir 850 usos, propor manutenção").
        ollama: Optional client (defaults to a freshly constructed one).
        model: Override model id; defaults to ``settings.ollama_model``.
        max_retries: How many self-correction attempts after the first
            failure. Default 1 — if it can't self-correct in one round,
            it's better to surface the error to the user.

    Returns:
        Validated :class:`Rule` (status defaults to PROPOSED).

    Raises:
        RuleTranslationError when the LLM doesn't produce valid JSON or
        the JSON fails Pydantic validation after retries.
    """
    if not nl_text or not nl_text.strip():
        raise RuleTranslationError("nl_text is empty")

    client = ollama or OllamaClient()
    model_id = model or getattr(settings, "ollama_model", "gemma4:e4b")
    system_prompt = _build_system_prompt()

    history: list[dict[str, str]] = []
    last_text: str | None = None
    last_error: str | None = None
    user_msg = nl_text.strip()

    for attempt in range(max_retries + 1):
        _log.info(
            "rule translation attempt %d/%d for nl_text len=%d",
            attempt + 1, max_retries + 1, len(user_msg),
        )
        try:
            response = await client.chat(
                prompt=user_msg,
                model=model_id,
                format="json",
                system_prompt=system_prompt,
                history=history,
                num_ctx=8192,
                num_predict=2048,
            )
        except Exception as exc:
            raise RuleTranslationError(f"Ollama call failed: {exc}") from exc

        # Q.117.F — OllamaClient.chat(format="json") devolve o JSON JÁ
        # parseado (dict). Versões antigas / mocks de teste devolvem o
        # envelope raw {"message":{"content":"<json str>"}} ou
        # {"response":"<json str>"}. O código anterior só lia o envelope,
        # por isso dava SEMPRE "empty response" com o client real — o
        # rule-author nunca funcionava live. Suporta ambas as formas.
        pre_parsed: dict[str, Any] | None = None
        if isinstance(response, dict):
            inner = (
                (response.get("message") or {}).get("content")
                or response.get("response")
                or response.get("content")
            )
            if isinstance(inner, str) and inner.strip():
                last_text = inner
            else:
                pre_parsed = response
                last_text = json.dumps(response, ensure_ascii=False)
        else:
            last_text = str(response) if response else None

        if not last_text:
            raise RuleTranslationError("Ollama returned an empty response")

        # Parse JSON
        try:
            parsed = pre_parsed if pre_parsed is not None else _extract_json_object(last_text)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = f"JSON parse error: {exc}"
            _log.warning("parse failure on attempt %d: %s", attempt + 1, exc)
            if attempt >= max_retries:
                raise RuleTranslationError(
                    "LLM did not return valid JSON after retries",
                    last_response=last_text,
                    last_validation_error=last_error,
                ) from exc
            history.extend([
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": last_text},
            ])
            user_msg = (
                f"A resposta anterior não era JSON válido: {exc}. "
                "Responde de novo com APENAS um objecto JSON, sem prefácio nem markdown."
            )
            continue

        # If LLM signalled it can't represent the request, surface that as error.
        if isinstance(parsed, dict) and "error" in parsed and "id" not in parsed:
            raise RuleTranslationError(
                f"LLM refused: {parsed['error']}",
                last_response=last_text,
            )

        # Validate via Pydantic
        try:
            return Rule.model_validate(parsed)
        except ValidationError as exc:
            last_error = str(exc)
            _log.warning("validation failure on attempt %d: %s", attempt + 1, exc)
            if attempt >= max_retries:
                raise RuleTranslationError(
                    "LLM-emitted rule failed Pydantic validation after retries",
                    last_response=last_text,
                    last_validation_error=last_error,
                ) from exc
            history.extend([
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": last_text},
            ])
            user_msg = (
                "A regra que emitiste falhou validação Pydantic com o seguinte erro:\n"
                f"{last_error}\n\n"
                "Corrige e responde de novo com APENAS o JSON corrigido."
            )

    raise RuleTranslationError(
        "exhausted retries without producing a valid rule",
        last_response=last_text,
        last_validation_error=last_error,
    )
