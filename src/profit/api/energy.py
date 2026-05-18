"""Energia real — API (Sprint Q.50.B / F8).

Expõe o custo de energia **real** medido pelos sensores IoT da ERP,
agregado por sensor×dia, contra a tarifa €/kWh configurável da
TenantConfig. Compara-se com a linha de energia *standard* do COGS
(``MachineRate.energy_cost_per_hour`` × horas) ao nível factory/dia.

Degrada honestamente: quando o adapter SQL Server está desligado
(``sqlserver_enabled=False``) responde ``erp_available=false`` com uma
razão explícita — nunca um número de kWh inventado.
"""

import logging
from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.profit.services.energy_cost_service import EnergyCostService
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/energy", tags=["Energy"])


def get_tenant_id(x_tenant_id: UUID = Header(...)) -> UUID:
    """Extrai o tenant do header."""
    return x_tenant_id


@router.get("/real")
async def get_real_energy_cost(
    date_from: date | None = Query(
        None, description="Início da janela (inclusivo). Omisso → 7 dias atrás."
    ),
    date_to: date | None = Query(
        None, description="Fim da janela (inclusivo). Omisso → hoje."
    ),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Q.50.B (F8) — custo de energia REAL por sensor/dia.

    Lê os sensores IoT trifásicos da ERP (``IOT_SENSOR_DATA``, via o
    reader Q.45.C), integra a potência em kWh real e multiplica pela
    tarifa €/kWh da TenantConfig (``cost.energy.tariff_eur_per_kwh``).

    Quando a janela não é dada, usa os últimos 7 dias. O grão é
    sensor×dia — ``IOT_SENSOR_DATA`` não tem fase nem barco. O total
    factory/dia é o que se compara com a linha standard do COGS.

    Degrada para ``erp_available=false`` com razão explícita quando o
    adapter SQL Server está desligado — ZERO MOCKS.

    ``tenant_id`` é exigido por consistência mas os dados ERP são
    tenant-agnósticos (uma única BD MAR-KAYAKS); a tarifa, essa, é
    tenant-específica.
    """
    today = date.today()
    if date_to is None:
        date_to = today
    if date_from is None:
        date_from = date_to - timedelta(days=7)

    tariff = await EnergyCostService.load_tariff(session, tenant_id)
    svc = EnergyCostService(tariff_eur_per_kwh=tariff)
    result = await svc.energy_cost(date_from, date_to)
    return result.to_dict()
