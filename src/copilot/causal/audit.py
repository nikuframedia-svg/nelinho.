"""
ProdPlan ONE — Causal Chain Audit (Sprint S.2, Camada 4 wiring)
=================================================================

The copilot's chain capture surface. Two functions:

* :func:`persist_chain_audit` — call this at the end of any causal
  response. It writes a ``CopilotMessage`` row with
  ``content_structured = {"causal_audit": {...}}`` so the daily ABL
  feedback job (Sprint R.3) has structured input.
* :func:`load_chain_pairs_for_date` — replaces the placeholder in
  ``src/copilot/jobs/abl_feedback.py`` and pulls the trio
  ``(chain, verification, kernel_delta)`` back as live Pydantic
  objects.

Why a dedicated module
----------------------
The copilot service today does not run ``verify_chain`` automatically;
when it eventually does (out of scope for S.2), the integration point
is a single ``persist_chain_audit(...)`` call at the end of every
causal response. Until then, the function exists so:

* Tests can simulate captures end-to-end.
* The ABL feedback job is no longer a no-op against real data.
* When the integration ships, it slots in without renaming or
  refactoring the consumer side.

Schema
------
The ``content_structured`` payload looks like::

    {
        "causal_audit": {
            "chain": <CausalChain.model_dump()>,
            "verification": <CausalVerificationResult.model_dump()>,
            "kernel_delta": float | None,
            "captured_at": "<isoformat>"
        }
    }

Stored under the ``copilot`` actor_role with ``content_text =
chain.question`` for grep-ability. Idempotent through ``correlation_id``
so the same response is never persisted twice.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.copilot.causal.chain import CausalChain, CausalVerificationResult
from src.copilot.models import CopilotMessage

logger = logging.getLogger(__name__)


CAUSAL_AUDIT_KEY = "causal_audit"


async def persist_chain_audit(
    *,
    session: AsyncSession,
    tenant_id: UUID,
    conversation_id: UUID,
    chain: CausalChain,
    verification: CausalVerificationResult,
    kernel_delta: Optional[float] = None,
    correlation_id: Optional[UUID] = None,
) -> CopilotMessage:
    """Write a chain + verification audit row.

    Designed to be called at the very end of a causal response, after
    ``verify_chain`` has finished. The caller commits the session as
    part of its normal lifecycle — this function only stages the row.
    """
    payload = {
        "type": "causal_audit",
        CAUSAL_AUDIT_KEY: {
            "chain": chain.model_dump(),
            "verification": verification.model_dump(),
            "kernel_delta": kernel_delta,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        },
    }
    msg = CopilotMessage(
        id=uuid4(),
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        actor_role="copilot",
        content_text=chain.question,
        content_structured=payload,
        correlation_id=correlation_id,
        latency_ms=None,
        model=None,
        validation_passed=verification.passed,
    )
    # Q.66.B.3: CopilotMessage e o registo da conversa LLM (auditoria
    # interna do copiloto, chain + verification), nao state de governance.
    session.add(msg)  # noqa: audit_coverage  # copilot conversation message, not gov state
    return msg


async def load_chain_pairs_for_date(
    session: AsyncSession,
    tenant_id: UUID,
    target_date: date,
) -> List[Tuple[CausalChain, CausalVerificationResult, Optional[float]]]:
    """Replay ``persist_chain_audit`` rows for a given UTC day.

    Returns the trio the ABL feedback job consumes. Rows whose
    payload is malformed (missing keys, schema drift) are skipped
    with a warning so one bad row never breaks the whole window.
    """
    start = datetime.combine(target_date, time.min, tzinfo=timezone.utc)
    end = datetime.combine(target_date, time.max, tzinfo=timezone.utc)
    stmt = (
        select(CopilotMessage)
        .where(
            and_(
                CopilotMessage.tenant_id == tenant_id,
                CopilotMessage.created_at >= start,
                CopilotMessage.created_at <= end,
                CopilotMessage.actor_role == "copilot",
            )
        )
        .order_by(CopilotMessage.created_at.asc())
    )
    rows = list((await session.execute(stmt)).scalars().all())

    pairs: List[Tuple[CausalChain, CausalVerificationResult, Optional[float]]] = []
    for row in rows:
        payload = row.content_structured if isinstance(row.content_structured, dict) else None
        if not payload:
            continue
        audit = payload.get(CAUSAL_AUDIT_KEY)
        if not isinstance(audit, dict):
            continue
        chain_dict = audit.get("chain")
        verification_dict = audit.get("verification")
        if not isinstance(chain_dict, dict) or not isinstance(verification_dict, dict):
            continue
        try:
            chain = CausalChain.model_validate(chain_dict)
            verification = CausalVerificationResult.model_validate(verification_dict)
        except Exception as exc:
            logger.warning(
                "causal_audit: skipping malformed audit on message %s (%s)",
                row.id, exc,
            )
            continue
        kernel_delta = audit.get("kernel_delta")
        if kernel_delta is not None and not isinstance(kernel_delta, (int, float)):
            kernel_delta = None
        pairs.append((chain, verification, kernel_delta))
    return pairs


__all__ = [
    "CAUSAL_AUDIT_KEY",
    "load_chain_pairs_for_date",
    "persist_chain_audit",
]
