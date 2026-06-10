"""
Factory quality + quarantine endpoints — `/v1/factory/quality/*`, `/v1/factory/quarantine/*` (Q.66.D.4b).
===========================================================================================================

- GET  /quality/trust-heatmap
- GET  /quarantine
- POST /quarantine/{row_id}/resolve

Q.168.D — a quarentena passou de MOCK (2 rows hardcoded + resolve fake 200
sem persistência — violação dos invariantes #1/#8 apanhada pela auditoria
2026-06-10) para a fonte REAL: as tabelas curadas com `QuarantineMixin`
(`factory_curated.*`, colunas is_quarantined/quarantine_code/reason/at).
Camada curada vazia → lista vazia HONESTA. O resolve persiste e escreve
`audit_log` na MESMA transacção (invariante #7).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.factory_data_product.api.routers._deps import get_engine
from src.factory_data_product.ingest import IngestEngine
from src.shared.auth.headers import (
    get_current_user_or_dev_header,
    require_tenant_header,
)
from src.shared.auth.jwt_handler import UserContext
from src.shared.database import get_session
from src.shared.time import utc_now


router = APIRouter(tags=["factory"])

# Tabelas curadas com QuarantineMixin — a fonte REAL da quarentena.
# (nome público da API → modelo ORM; o nome segue o __tablename__)
def _quarantine_tables() -> Dict[str, Any]:
    from src.factory_data_product.models.curated import (
        CuratedAllocation,
        CuratedCostReference,
        CuratedMold,
        CuratedModelo,
        CuratedMoldUsage,
        CuratedOrder,
        CuratedOrderPhase,
        CuratedPhaseCapacity,
        CuratedQualityEvent,
        CuratedSkillMatrix,
    )

    return {
        "order": CuratedOrder,
        "order_phase": CuratedOrderPhase,
        "phase_capacity": CuratedPhaseCapacity,
        "mold": CuratedMold,
        "mold_usage": CuratedMoldUsage,
        "quality_event": CuratedQualityEvent,
        "skill_matrix": CuratedSkillMatrix,
        "cost_reference": CuratedCostReference,
        "allocation": CuratedAllocation,
        "modelo": CuratedModelo,
    }


# Cap por tabela (com aviso explícito em `capped_tables` — nunca truncar em
# silêncio): a quarentena é para triagem humana; >500 rows numa tabela é um
# problema de ingestão, não de paginação.
_PER_TABLE_CAP = 500


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TrustHeatmapResponse(BaseModel):
    """Permissive contract for `/quality/trust-heatmap` (Onda 3.7).

    The heatmap payload is rich and evolves sprint-by-sprint; we lock the
    top-level keys clients depend on and let the rest pass through with
    `extra="allow"` so future additions don't require a coordinated
    front-end + back-end ship.
    """

    model_config = {"extra": "allow"}

    overall_trust: float
    overall_status: str
    domains: List[str]
    segments: Dict[str, Any]
    summary: Dict[str, Any]
    generated_at: str
    ingestion_id: Optional[str] = None


class QuarantineRowResponse(BaseModel):
    """Response for a single quarantined row."""

    id: str
    table_name: str
    row_data: Dict[str, Any]
    quarantine_code: str
    quarantine_reason: str
    quarantined_at: str
    ingestion_id: str


class QuarantineListResponse(BaseModel):
    """Response for quarantine list."""

    rows: List[QuarantineRowResponse]
    total: int
    page: int
    page_size: int
    by_code: Dict[str, int]
    by_table: Dict[str, int]
    # Q.168.D — tabelas que bateram no cap de leitura (nunca truncar em
    # silêncio). Vazio no caso normal.
    capped_tables: List[str] = []


# ---------------------------------------------------------------------------
# Trust heatmap
# ---------------------------------------------------------------------------


@router.get(
    "/quality/trust-heatmap",
    summary="Get Trust Heatmap",
    description="""
    Get a trust heatmap showing data quality by segment and domain.

    Returns:
    - Trust values by segment (rows) and domain (columns)
    - Overall trust score
    - Segments categorized by status (excellent/good/warning/critical)
    - Improvement priorities
    - Alerts for low-trust segments
    """,
    tags=["factory", "quality"],
)
async def get_trust_heatmap(
    include_priorities: bool = Query(True, description="Include improvement priorities"),
    include_alerts: bool = Query(True, description="Include alerts"),
    engine: IngestEngine = Depends(get_engine),
) -> TrustHeatmapResponse:
    """
    Get trust heatmap for data quality visualization.

    This endpoint provides a comprehensive view of data quality across
    all segments and domains, with actionable insights for improvement.
    """
    from src.factory_data_product.quality.trust_heatmap import get_trust_heatmap_generator

    generator = get_trust_heatmap_generator()

    # Get current active run ID
    active_run = engine.get_active_run()
    ingestion_id = str(active_run.get("active_ingestion_id")) if active_run else None

    # Generate heatmap
    heatmap = generator.generate(ingestion_id=ingestion_id)

    result = heatmap.to_dict()

    # Add priorities if requested
    if include_priorities:
        result["improvement_priorities"] = generator.get_improvement_priorities(heatmap)

    # Add alerts if requested
    if include_alerts:
        result["alerts"] = generator.generate_alerts(heatmap)

    return TrustHeatmapResponse(**result)


# ---------------------------------------------------------------------------
# Quarantine — fonte REAL (tabelas curadas com QuarantineMixin)
# ---------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    """Valor de coluna → JSON-seguro (datetime/UUID/Decimal → str)."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _row_response(table_name: str, model: Any, row: Any) -> QuarantineRowResponse:
    skip = {"is_quarantined", "quarantine_reason", "quarantine_code", "quarantined_at"}
    data = {
        col.key: _jsonable(getattr(row, col.key, None))
        for col in model.__table__.columns
        if col.key not in skip
    }
    qa = getattr(row, "quarantined_at", None)
    return QuarantineRowResponse(
        id=str(row.id),
        table_name=table_name,
        row_data=data,
        quarantine_code=str(getattr(row, "quarantine_code", None) or ""),
        quarantine_reason=str(getattr(row, "quarantine_reason", None) or ""),
        quarantined_at=qa.isoformat() if isinstance(qa, datetime) else "",
        ingestion_id=str(getattr(row, "ingestion_id", None) or ""),
    )


@router.get(
    "/quarantine",
    response_model=QuarantineListResponse,
    summary="List Quarantined Rows",
    description="Get rows that have been quarantined due to data quality issues.",
    tags=["factory", "data-quality"],
)
async def list_quarantined_rows(
    table: Optional[str] = Query(None, description="Filter by table name"),
    code: Optional[str] = Query(None, description="Filter by quarantine code"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Results per page"),
    session: AsyncSession = Depends(get_session),
):
    """Lista as rows em quarentena nas tabelas curadas (fonte REAL).

    Camada curada vazia (o estado normal quando o pipeline corre só sobre
    `factory_raw`) → lista vazia honesta, nunca dados de exemplo.
    """
    tables = _quarantine_tables()
    if table is not None and table not in tables:
        raise HTTPException(
            status_code=400,
            detail=(
                f"tabela desconhecida '{table}' — válidas: "
                f"{', '.join(sorted(tables))}"
            ),
        )
    scope = {table: tables[table]} if table else tables

    collected: List[QuarantineRowResponse] = []
    capped: List[str] = []
    for name, model in scope.items():
        stmt = select(model).where(model.is_quarantined.is_(True))
        if code:
            stmt = stmt.where(model.quarantine_code == code)
        stmt = stmt.limit(_PER_TABLE_CAP + 1)
        rows = list((await session.execute(stmt)).scalars().all())
        if len(rows) > _PER_TABLE_CAP:
            capped.append(name)
            rows = rows[:_PER_TABLE_CAP]
        collected.extend(_row_response(name, model, r) for r in rows)

    # Mais recentes primeiro; sem data → fim (determinístico por id).
    collected.sort(key=lambda r: (r.quarantined_at or "", r.id), reverse=True)

    by_code: Dict[str, int] = {}
    by_table: Dict[str, int] = {}
    for row in collected:
        by_code[row.quarantine_code] = by_code.get(row.quarantine_code, 0) + 1
        by_table[row.table_name] = by_table.get(row.table_name, 0) + 1

    start_idx = (page - 1) * page_size
    paginated = collected[start_idx:start_idx + page_size]

    return QuarantineListResponse(
        rows=paginated,
        total=len(collected),
        page=page,
        page_size=page_size,
        by_code=by_code,
        by_table=by_table,
        capped_tables=capped,
    )


@router.post(
    "/quarantine/{row_id}/resolve",
    summary="Resolve Quarantine",
    description="Mark a quarantined row as resolved (repaired or accepted).",
    tags=["factory", "data-quality"],
)
async def resolve_quarantine(
    row_id: str,
    action: str = Query(..., pattern="^(repair|accept_risk|delete)$",
                        description="Action: 'repair', 'accept_risk', 'delete'"),
    reason: str = Query(..., min_length=10, description="Reason for resolution"),
    table: Optional[str] = Query(
        None, description="Tabela curada (acelera a procura; opcional)",
    ),
    tenant_id: UUID = Depends(require_tenant_header),
    user: UserContext = Depends(get_current_user_or_dev_header),
    session: AsyncSession = Depends(get_session),
):
    """Resolve uma row em quarentena — PERSISTE e AUDITA (mesma transacção).

    - repair / accept_risk → `is_quarantined=False` (code/reason ficam como
      histórico);
    - delete → remove a row.

    404 se a row não existe em nenhuma tabela curada — nunca um 200 fake.
    """
    from src.governance.audit_service import audit_change

    try:
        rid = UUID(row_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"row_id inválido: {row_id}")

    tables = _quarantine_tables()
    if table is not None and table not in tables:
        raise HTTPException(
            status_code=400,
            detail=(
                f"tabela desconhecida '{table}' — válidas: "
                f"{', '.join(sorted(tables))}"
            ),
        )
    scope = {table: tables[table]} if table else tables

    for name, model in scope.items():
        row = (
            await session.execute(select(model).where(model.id == rid))
        ).scalar_one_or_none()
        if row is None:
            continue

        old_values = {
            "is_quarantined": bool(getattr(row, "is_quarantined", False)),
            "quarantine_code": getattr(row, "quarantine_code", None),
        }
        if action == "delete":
            await session.delete(row)
            audit_action = "DELETE"
            new_values = None
        else:
            row.is_quarantined = False
            audit_action = "UPDATE"
            new_values = {"is_quarantined": False, "resolution": action}

        # Invariante #7 — audit_log na MESMA transacção da mudança de estado.
        await audit_change(
            session,
            tenant_id=tenant_id,
            entity_type=f"curated_quarantine:{name}",
            entity_id=rid,
            action=audit_action,
            old_values=old_values,
            new_values=new_values,
            actor_id=user.user_id,
            actor_role=user.role,
            reason=reason,
        )
        await session.commit()

        return {
            "success": True,
            "row_id": row_id,
            "table_name": name,
            "action": action,
            "reason": reason,
            "resolved_by": str(user.user_id),
            "resolved_at": utc_now().isoformat(),
        }

    raise HTTPException(
        status_code=404,
        detail=(
            f"row {row_id} não está em quarentena em nenhuma tabela curada"
            + (f" (procurado só em '{table}')" if table else "")
        ),
    )
