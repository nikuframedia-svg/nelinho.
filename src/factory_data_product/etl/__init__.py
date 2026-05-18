"""Q.36.C — ETL relacional → `factory_curated.*`.

O ``IngestEngine`` do `factory_data_product` é in-memory e só popula a
camada curada via upload de Excel. Como resultado, os 3 detectores
causais (`erro_tree`, `reichenbach`, `mill_diff`) — que lêem
`factory_curated.*` pelo `DiagnosticsRepository` — correm sempre contra
tabelas vazias.

Este pacote materializa `factory_curated.{order_phase,quality_event,
allocation}` a partir das fontes relacionais reais do ERP MAR-KAYAKS
(`OF_FP`, `OF_CHECKLIST`, `OFFP_EQ`) — funções de transformação puras +
`load_curated`, que faz full-refresh das 3 tabelas numa transacção e
regista um `IngestionRun` (audit, axioma 7).
"""

from .curated_loader import (
    checklist_to_quality_events,
    crew_to_allocations,
    load_curated,
    operations_to_order_phases,
)

__all__ = [
    "checklist_to_quality_events",
    "crew_to_allocations",
    "load_curated",
    "operations_to_order_phases",
]
