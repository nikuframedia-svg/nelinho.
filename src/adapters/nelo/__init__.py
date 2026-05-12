"""NELO ERP (MAR-KAYAKS DB) adapter — read-only.

The `MAR-KAYAKS` DB on `fabrica.nelo.eu` is the factory's primary ERP
(Laravel front + SQL Server back). This adapter mirrors the 8 core tables
needed by ProdPlan ONE planning:

- WorkOrder (ORDEMFABRICO) + WorkOrderPhase (OF_FP)
- Product (PRODUTO) + ProductPhase routings (PRODUTO_FASE)
- ProductComponent BOM (PRODUTO_COMPONENTE)
- ProductionPhase work centres (FASES_PRODUCAO)
- Entity people/customers/operators (ENTIDADE)
- Movement stock ledger (MOVIMENTO)

Connection: `mssql+aioodbc://...` via `src.shared.config:sqlserver_url`.
Never use these models to issue UPDATE/INSERT/DELETE.
"""

from .models import (
    Base,
    Entity,
    Movement,
    Product,
    ProductComponent,
    ProductionPhase,
    ProductPhase,
    WorkOrder,
    WorkOrderPhase,
)

__all__ = [
    "Base",
    "Entity",
    "Movement",
    "Product",
    "ProductComponent",
    "ProductionPhase",
    "ProductPhase",
    "WorkOrder",
    "WorkOrderPhase",
]
