"""NELO ERP (MAR-KAYAKS DB) adapter — read-only.

The `MAR-KAYAKS` DB on `fabrica.nelo.eu` is the factory's primary ERP
(Laravel front + SQL Server back). This adapter mirrors the core tables
needed by ProdPlan ONE planning:

- WorkOrder (ORDEMFABRICO) + WorkOrderPhase (OF_FP)
- Product (PRODUTO) + ProductPhase routings (PRODUTO_FASE)
- ProductComponent BOM (PRODUTO_COMPONENTE)
- ProductionPhase work centres (FASES_PRODUCAO)
- Entity people/customers/operators (ENTIDADE) + skill matrix (ENTIDADE_FASE)
- Mold catalogue (MOLDES)
- Movement stock ledger (MOVIMENTO)

Connection: `mssql+aioodbc://...` via `src.shared.config:sqlserver_url`.
Never use these models to issue UPDATE/INSERT/DELETE.

The async query layer is :mod:`src.adapters.nelo.services`; the
ERP→Postgres ETL mirrors are in :mod:`src.adapters.nelo.etl`.
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
from .schemas import (
    BomRow,
    EntityPhaseRow,
    EntityRow,
    HealthCheckResult,
    MoldRow,
    MovementRow,
    OperationRow,
    OrderRow,
    PhaseRow,
    ProductOrderCount,
    ProductRow,
    ProductStockRow,
    RoutingRow,
    ScheduleRow,
    WarehouseStockRow,
)

__all__ = [
    "Base",
    "BomRow",
    "Entity",
    "EntityPhaseRow",
    "EntityRow",
    "HealthCheckResult",
    "MoldRow",
    "Movement",
    "MovementRow",
    "OperationRow",
    "OrderRow",
    "PhaseRow",
    "Product",
    "ProductComponent",
    "ProductOrderCount",
    "ProductRow",
    "ProductStockRow",
    "ProductionPhase",
    "ProductPhase",
    "RoutingRow",
    "ScheduleRow",
    "WarehouseStockRow",
    "WorkOrder",
    "WorkOrderPhase",
]
