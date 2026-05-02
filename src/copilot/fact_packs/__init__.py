"""Fact-pack helpers for the Copilot.

A "fact pack" is a deterministic, machine-readable summary of a slice
of the business state — built from real DB queries (not LLM calls) so
the prompt has a *source of truth* it can quote without hallucinating.

The legacy ``CopilotService._render_prompt`` already inlines a KPI
fact pack; this package extracts the per-domain fact packs into their
own modules so each can evolve independently and be unit-tested.

Currently exports:

* :mod:`schedule_fact_pack` (FASE 3.7 / HIGH-52) — fact pack for
  ``"qual é o plano para amanhã?"`` style queries. Pulls from
  ``plan.production_schedules``.
"""

from src.copilot.fact_packs.schedule_fact_pack import (
    ScheduleFactPack,
    build_schedule_fact_pack,
)

__all__ = ["ScheduleFactPack", "build_schedule_fact_pack"]
