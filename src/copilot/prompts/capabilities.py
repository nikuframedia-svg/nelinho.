"""
ProdPlan ONE — Capabilities marker for the Copilot system prompt
=================================================================

Sprint Q.15.0 — the v2.2 system prompt (`system_prompt.md`) describes
behaviors that may or may not be wired in code at any given time:

  * `investigate_quality_drop` — ERRO-TREE handler (Q.15.D.1)
  * `find_common_cause` — Reichenbach handler (Q.15.D.2/D.3)
  * `what_changed` — Mill's method handler (Q.15.D.4)

Without an explicit "wired vs aspirational" marker, the LLM **fingirá**
that it followed the framework when in fact it improvised — that's the
classic hallucination-with-false-authority risk.

This module emits a small dynamic block that gets substituted into the
prompt at the ``<!-- CAPABILITIES_PLACEHOLDER -->`` marker. It reads
per-tenant ConfigStore flags so an operator can flip a handler from
``aspiracional`` → ``Wired`` once the corresponding sprint lands and
the handler passes integration tests on that tenant.

The block tells the LLM:

  ✓ Which tools exist and CAN be called
  ⚠ Which tools are NOT wired — must NOT pretend to invoke them
  - The graceful fallback wording when no tool is wired
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


# Each capability bundles a tool name + a config flag + a one-line
# description shown in the prompt. The tool name MUST match the
# `name` in `src/copilot/tools/diagnostic_tools.py` so the dispatch
# table works without indirection.
@dataclass(frozen=True)
class Capability:
    tool_name: str
    config_key: str  # under "copilot" category
    summary_pt: str

    def is_wired(self, flags: Dict[str, bool]) -> bool:
        return bool(flags.get(self.config_key, False))


# Order matters: rendered top-to-bottom in the prompt, so the most
# user-visible capabilities go first.
KNOWN_CAPABILITIES: List[Capability] = [
    Capability(
        tool_name="investigate_quality_drop",
        config_key="diagnostics.erro_tree.enabled",
        summary_pt=(
            "ERRO-TREE — investigar queda de qualidade ou throughput "
            "(cascata moldes → operadores → material → sobrecarga)"
        ),
    ),
    Capability(
        tool_name="find_common_cause",
        config_key="diagnostics.reichenbach.enabled",
        summary_pt=(
            "Reichenbach — quando 2+ fases drift juntas, encontrar "
            "recurso partilhado (molde, operadores, material, turno, cascata)"
        ),
    ),
    Capability(
        tool_name="what_changed",
        config_key="diagnostics.mill_diff.enabled",
        summary_pt=(
            "Mill's method — comparar 2 períodos e listar tudo o que "
            "mudou, ranqueado por correlação (Cohen's d)"
        ),
    ),
]


# Wired capabilities every tenant has from day 1 — facto + cenário
# correspond to existing infrastructure (DB queries + POETIQ/CPO).
# No config flag because they're foundational; if they break, the
# whole copilot is broken anyway.
_ALWAYS_WIRED: List[str] = [
    "facto: query directa à DB de KPIs, fases, ordens, operadores, moldes",
    "cenário: simulação CPO via POETIQ (one-shot ou iterative opt-in)",
]


async def fetch_capability_flags(
    session: Any, tenant_id: UUID,
) -> Dict[str, bool]:
    """Read per-tenant capability flags from ConfigStore.

    Best-effort: a missing key OR a TenantConfigService failure means
    the capability stays ``False`` (aspiracional). This is the safe
    default — the LLM never assumes a tool is wired without explicit
    operator opt-in.
    """
    flags: Dict[str, bool] = {}
    try:
        from src.core.services.tenant_config_service import TenantConfigService
    except ImportError:
        logger.debug(
            "fetch_capability_flags: TenantConfigService unavailable; "
            "treating all capabilities as aspirational",
        )
        return flags

    try:
        cfg = TenantConfigService(session, tenant_id)
        for cap in KNOWN_CAPABILITIES:
            value = await cfg.get("copilot", cap.config_key, default=False)
            flags[cap.config_key] = bool(value)
    except Exception as exc:
        logger.warning(
            "fetch_capability_flags: read failed for tenant %s (%s) — "
            "all capabilities treated as aspirational",
            tenant_id, exc,
        )
    return flags


def render_capabilities_block(flags: Dict[str, bool]) -> str:
    """Compose the block of text that replaces the placeholder.

    The output is plain markdown intended to be human-readable. It is
    INTENTIONALLY short — the LLM has to parse it on every prompt and
    long capability lists waste tokens on something that should be
    decision-tree-flat.
    """
    wired_lines: List[str] = list(_ALWAYS_WIRED)
    aspirational_lines: List[str] = []

    for cap in KNOWN_CAPABILITIES:
        line = f"`{cap.tool_name}` — {cap.summary_pt}"
        if cap.is_wired(flags):
            wired_lines.append(line)
        else:
            aspirational_lines.append(line)

    block_lines: List[str] = [
        "## CAPABILITIES — o que este sistema PODE fazer (lê antes de prometer)",
        "",
        "✓ **Wired** (chama via tool, cita resultado):",
    ]
    for line in wired_lines:
        block_lines.append(f"  - {line}")

    block_lines.append("")
    if aspirational_lines:
        block_lines.append("⚠ **Não wired ainda** (não prometer; admite que não tens handler):")
        for line in aspirational_lines:
            block_lines.append(f"  - {line}")
        block_lines.append("")
        block_lines.append(
            "Quando uma capability acima é ⚠, responde:"
        )
        block_lines.append(
            "> *\"Posso descrever-te a árvore de raciocínio, mas o handler que "
            "faz a investigação real não está activo neste tenant. Pede ao "
            "admin para activar.\"*"
        )
        block_lines.append("")
        block_lines.append(
            "**NUNCA** pretender que diagnosticaste algo se a tool não está activa."
        )
    else:
        block_lines.append(
            "✓ **Todos os handlers de diagnóstico estão activos** — usa-os "
            "via tool-call sempre que o gestor faz uma pergunta de causa raiz."
        )

    return "\n".join(block_lines)


def is_diagnostic_capability_wired(flags: Dict[str, bool]) -> bool:
    """True iff at least one diagnostic capability is wired.

    The service uses this to decide whether to bother offering
    diagnostic tools to the LLM in `chat_with_tools` — when nothing
    is wired, the LLM should fall straight through to generic free-form
    answer with the "improvising" warning.
    """
    return any(cap.is_wired(flags) for cap in KNOWN_CAPABILITIES)


__all__ = [
    "Capability",
    "KNOWN_CAPABILITIES",
    "fetch_capability_flags",
    "is_diagnostic_capability_wired",
    "render_capabilities_block",
]
