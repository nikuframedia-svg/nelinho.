"""
ProdPlan ONE - Guardrails Tier 1 (Sprint S.4)
===============================================

Blueprint v2.0 §5.4 prescribes a two-tier guardrail stack:

  Tier 1 — regex: API keys, credit cards, IBANs, SSNs, PII patterns
  Tier 2 — Guardrails AI: PII + toxicity classifiers (model-based)

This module is Tier 1. It runs BEFORE any LLM call (to strip secrets
from prompts) and AFTER every LLM response (to strip leaked secrets).

Existing `src/copilot/guardrails.py` covers prompt injection + evidence
+ action allow-list; this module complements it with secret/PII regex.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Regex library — conservative by design (false positives acceptable)
# ---------------------------------------------------------------------------

# Anthropic API keys start with `sk-ant-` and are 108 chars long.
ANTHROPIC_API_KEY = re.compile(r"sk-ant-[A-Za-z0-9_-]{95,120}")
# OpenAI API keys start with `sk-` and are 48-60 chars.
OPENAI_API_KEY = re.compile(r"sk-[A-Za-z0-9]{32,80}")
# Generic JWT (3 base64 segments separated by dots).
JWT = re.compile(r"ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")
# Credit cards (loose — Luhn validation left for Tier 2).
CREDIT_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
# Portuguese IBAN (PT + 23 digits).
IBAN_PT = re.compile(r"\bPT\d{23}\b")
# Portuguese NIF (9 digits); we only flag clearly-contextualised matches
# to avoid eating product codes.
NIF_PT = re.compile(r"\b(?:NIF|contribuinte)\s*:?\s*(\d{9})\b", re.IGNORECASE)
# SSN US (XXX-XX-XXXX).
SSN_US = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# Plain emails.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


DEFAULT_PATTERNS: dict[str, re.Pattern] = {
    "anthropic_api_key": ANTHROPIC_API_KEY,
    "openai_api_key": OPENAI_API_KEY,
    "jwt": JWT,
    "credit_card": CREDIT_CARD,
    "iban_pt": IBAN_PT,
    "nif_pt": NIF_PT,
    "ssn_us": SSN_US,
    "email": EMAIL,
}


DEFAULT_MASK = "[REDACTED]"


@dataclass
class ScanResult:
    """Outcome of a single scan — list of matches + redacted text."""

    original_length: int
    matches: List["Match"] = field(default_factory=list)
    redacted: str = ""

    @property
    def has_violations(self) -> bool:
        return len(self.matches) > 0

    def pattern_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for match in self.matches:
            counts[match.pattern_name] = counts.get(match.pattern_name, 0) + 1
        return counts


@dataclass
class Match:
    pattern_name: str
    start: int
    end: int
    # Store only a fingerprint — NEVER the raw match — so logs stay safe.
    fingerprint: str


def scan(
    text: str,
    *,
    patterns: Optional[dict[str, re.Pattern]] = None,
    mask: str = DEFAULT_MASK,
) -> ScanResult:
    """Redact every registered pattern. Returns the redacted text + matches."""
    if not text:
        return ScanResult(original_length=0, matches=[], redacted="")

    effective = patterns or DEFAULT_PATTERNS
    matches: List[Match] = []
    redacted = text

    for name, pattern in effective.items():
        def _replace(match: re.Match) -> str:
            raw = match.group(0)
            matches.append(Match(
                pattern_name=name,
                start=match.start(),
                end=match.end(),
                fingerprint=_fingerprint(raw),
            ))
            return mask

        redacted = pattern.sub(_replace, redacted)

    return ScanResult(
        original_length=len(text),
        matches=matches,
        redacted=redacted,
    )


def _fingerprint(raw: str) -> str:
    """Short, non-reversible fingerprint for logging. Never log the raw value."""
    if not raw:
        return ""
    head = raw[:3]
    tail = raw[-3:] if len(raw) > 6 else ""
    return f"{head}…{tail} (len={len(raw)})"


def any_secret(text: str) -> bool:
    """Quick boolean check — used by callers that only need a tripwire."""
    return scan(text).has_violations
