"""
ProdPlan ONE — Causal audit runtime helper (Sprint Q.13.D / D.1)
=================================================================

Single function any copilot codepath that produces a `CausalChain`
calls at the end to feed the Camada-4 ABL pipeline. Combines the
two existing primitives (``verify_chain_dict`` + ``persist_chain_audit``)
into a one-liner so adoption is friction-free.

Why this module exists
----------------------

Plan v4 §13 Layer 4 + §22-§26 require Camada 4 (ABL) to receive
``(chain, verification_result)`` pairs nightly so divergences between
the LLM's causal reasoning and the kernel's ground truth are turned
into DPO triplets. Until now:

* `verify_chain` existed but had ZERO callers (only tests + the loader
  for the ABL job).
* `persist_chain_audit` existed but had ZERO callers (only the loader
  reads its output).

Result: the daily ABL job ran, found 0 chains in the database, wrote
0 triplets, the moat never accumulated. This module is the missing
glue.

Adoption
--------

Any copilot path that produces causal reasoning calls
``record_causal_audit(...)`` at the end. The single contract:

    msg = await record_causal_audit(
        session=session,
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        chain_dict=chain_dict,           # raw dict from LLM/reasoner
        kernel_delta=delta,              # optional
        correlation_id=request_id,       # optional
    )

The function:

* Validates the chain via ``verify_chain_dict`` (5-layer checks).
* Persists a `CopilotMessage` row with the audit payload in
  ``content_structured.causal_audit`` (the shape the ABL job
  reads).
* Returns the persisted `CopilotMessage` (with `validation_passed`
  reflecting the verification outcome) so the caller can attach
  follow-up logic (e.g. surface the validation failure to the user).

Failure mode: best-effort. If the chain is malformed and verification
crashes, the function logs + returns ``None`` rather than blowing up
the whole copilot response — the moat is a side effect of the user
flow, not a blocker.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.causal.audit import persist_chain_audit
from src.copilot.causal.chain import (
    CausalChain,
    CausalVerificationResult,
    verify_chain_dict,
)
from src.copilot.models import CopilotMessage

logger = logging.getLogger(__name__)


async def record_causal_audit(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    conversation_id: UUID,
    chain_dict: Dict[str, Any],
    kernel_delta: Optional[float] = None,
    correlation_id: Optional[UUID] = None,
) -> Optional[CopilotMessage]:
    """Verify + persist a causal chain. Returns the audit message row.

    Sprint Q.13.D D.1 — the single line every copilot caller invokes
    at the end of a causal response. See module docstring for adoption
    contract.

    Returns ``None`` (instead of raising) when:
    * ``chain_dict`` doesn't validate as a `CausalChain` schema.
    * ``verify_chain_dict`` raises (defensive — should not happen but
      the contract is "never break the user response").
    * ``persist_chain_audit`` raises (DB outage / FK constraint).

    The caller can ignore the return value safely; the audit is a
    side-effect for the nightly ABL job.
    """
    try:
        verification: CausalVerificationResult = verify_chain_dict(chain_dict)
    except Exception as exc:
        logger.warning(
            "record_causal_audit: verify_chain_dict failed (%s) — skipping persist. "
            "tenant=%s conversation=%s",
            exc, tenant_id, conversation_id,
        )
        return None

    # `verify_chain_dict` does not return the parsed CausalChain to the
    # caller; we re-validate here so `persist_chain_audit` gets a
    # typed object (the schema cost is cheap — Pydantic v2 ModelValidator
    # is C-fast, and this path runs once per copilot response).
    try:
        chain = CausalChain.model_validate(chain_dict)
    except Exception as exc:
        logger.warning(
            "record_causal_audit: CausalChain validation failed AFTER verify "
            "succeeded (%s) — schema drift? tenant=%s",
            exc, tenant_id,
        )
        return None

    try:
        msg = await persist_chain_audit(
            session=session,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            chain=chain,
            verification=verification,
            kernel_delta=kernel_delta,
            correlation_id=correlation_id,
        )
        # `persist_chain_audit` only stages the row; we DON'T flush
        # here so the caller's outer transaction stays in control of
        # the commit boundary.
        return msg
    except Exception as exc:
        logger.warning(
            "record_causal_audit: persist failed (%s) — chain audit lost "
            "for tenant=%s conversation=%s",
            exc, tenant_id, conversation_id,
        )
        return None


__all__ = ["record_causal_audit"]
