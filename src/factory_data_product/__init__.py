"""
Factory Data Product — Contrato 010
===================================

Industrial data product with:
- Separate database `prodplan_factory`
- RAW/CURATED/META/SEMANTIC layers
- Quality gates with blocking checks
- Logical activation/rollback via `active_ingestion_id`
- Read-only API for consumption

CRITICAL PRINCIPLES:
1. RAW is append-only: never update, never delete
2. Rollback is logical: swap `active_ingestion_id`, don't delete data
3. Idempotency by file hash: re-upload of same file = SKIP
4. No free SQL: only allow-listed views
5. Audit first: every record has lineage (ingestion, sheet, row, hashes)
6. PII/cost protected: explicit access policy; deny by default
"""

from src.factory_data_product.api import router as factory_router

__all__ = ["factory_router"]


