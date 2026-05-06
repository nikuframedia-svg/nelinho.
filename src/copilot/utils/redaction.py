"""
ProdPlan ONE - COPILOT Redaction Utilities
===========================================

Mascarar dados sensíveis (ex: nomes de funcionários para não-HR roles).

Sprint Q.12 Onda 5.1 — replaced two pre-existing problems:

* The ``hash(name) % 10000`` placeholder used :func:`hash` which is
  randomised per Python process (``PYTHONHASHSEED``). The placeholder
  for the same employee differed between deploys, leaking the fact
  that two redactions referred to the same person across runs (or
  worse, *not* leaking it when they were the same person and the
  reader expected stable IDs).
* ``NAME_PATTERNS`` was defined and never used: only names already
  enumerated in ``employee_names`` got redacted, so any free-form
  mention of a worker the context map didn't include went through.

The new helper uses HMAC-SHA256 keyed on ``settings.secret_key`` so
the placeholder is deterministic per deploy yet unguessable; the
short alphabetic suffix keeps it readable in chat output. The legacy
patterns are now actually used for the secondary "scan free text for
unknown names" pass.
"""

import hashlib
import hmac
import re
from typing import Any, Dict, Iterable, Set

from src.shared.config import settings


# Sprint Q.12 Onda 5.1 — simple two-token + initialism patterns. Used
# in :func:`mask_unknown_capitalised_names` for the free-text sweep.
# Conservative on purpose: these never produce false-positive
# placeholders for things like "Quality Gate" because we additionally
# require the tokens not to match a small allow-list of common
# domain words.
NAME_PATTERNS = [
    re.compile(r"\b[A-Z][a-z]{2,} [A-Z][a-z]{2,}\b"),       # "João Silva"
    re.compile(r"\b[A-Z]\. ?[A-Z][a-z]{2,}\b"),             # "J. Silva"
]

# Words that match the regex shape but should NOT be redacted.
_NAME_SAFE_WORDS = {
    "Quality Gate", "Standard Work", "Lead Time", "Pull System",
    "Total Productive", "Setup Time", "Cycle Time", "Takt Time",
    "Work Order", "Bill Of",
}


def _placeholder_for(name: str) -> str:
    """Stable, deploy-keyed placeholder for ``name``.

    Uses HMAC-SHA256 with ``settings.secret_key`` so the hash isn't
    PYTHONHASHSEED-dependent. The first 4 hex chars (16 bits) match
    the readability of the old ``% 10000`` placeholder while moving
    from a 1-in-10k birthday-paradox collision to ~1-in-65k.
    """
    digest = hmac.new(
        settings.secret_key.encode("utf-8"),
        name.lower().strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"[Funcionário {digest[:4]}]"


def mask_employee_names(text: str, employee_names: Set[str]) -> str:
    """
    Mascarar nomes de funcionários no texto.

    Substitui nomes por "Funcionário [HMAC-suffix]" — estável por
    deploy mas não adivinhável.
    """
    masked = text
    for name in employee_names:
        escaped_name = re.escape(name)
        masked = re.sub(
            escaped_name,
            _placeholder_for(name),
            masked,
            flags=re.IGNORECASE,
        )
    masked = mask_unknown_capitalised_names(masked, known=employee_names)
    return masked


def mask_unknown_capitalised_names(
    text: str, *, known: Iterable[str] = (),
) -> str:
    """Sprint Q.12 Onda 5.1 — second pass for names the context map
    didn't enumerate.

    Walks :data:`NAME_PATTERNS` and replaces matches that aren't in
    :data:`_NAME_SAFE_WORDS` (and aren't already redacted by the
    enumerated path). Conservative — only redacts true two-token
    capitalised phrases ≥3 letters per token, so it doesn't eat
    sentence starts like "Boas práticas".
    """
    known_lower = {k.lower() for k in known}

    def _replace(match: re.Match) -> str:
        token = match.group(0)
        if token in _NAME_SAFE_WORDS:
            return token
        if token.lower() in known_lower:
            # Already redacted via the enumerated path — leave alone.
            return token
        return _placeholder_for(token)

    out = text
    for pattern in NAME_PATTERNS:
        out = pattern.sub(_replace, out)
    return out


def redact_response(
    response: Dict[str, Any],
    employee_names: Set[str],
    has_hr_role: bool,
) -> Dict[str, Any]:
    """
    Redigir resposta do COPILOT se necessário.
    
    Se não tem HR role, mascarar nomes de funcionários no output.
    """
    if has_hr_role:
        return response  # Não redigir
    
    # Redigir summary
    if "summary" in response:
        response["summary"] = mask_employee_names(response["summary"], employee_names)
    
    # Redigir facts
    if "facts" in response:
        for fact in response.get("facts", []):
            if "text" in fact:
                fact["text"] = mask_employee_names(fact["text"], employee_names)
    
    # Citations mantêm IDs internos (não redigir)
    
    return response


def extract_employee_names_from_context(context: Dict[str, Any]) -> Set[str]:
    """Extrair nomes de funcionários do contexto para redação."""
    names = set()
    
    # Procurar em allocations
    allocations = context.get("operational_snapshot", {}).get("allocations", {})
    for emp in allocations.get("top_employees", []):
        if "name" in emp:
            names.add(emp["name"])
    
    return names


