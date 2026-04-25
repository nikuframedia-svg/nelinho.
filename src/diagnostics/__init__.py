"""
ProdPlan ONE - Diagnostics module (Sprint Q.7 Fase 1)
=====================================================

Live runtime visibility of the system: per-module health rollup,
infrastructure pings (DB / Redis / Kafka / Ollama), Trust Index gates,
ScheduleCommit cadence, and the same audit metrics the offline
`scripts/audit.py` produces — but live.

Powers the `/admin/health` page in the frontend.
"""

from .api import router

__all__ = ["router"]
