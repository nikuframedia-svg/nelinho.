"""
ProdPlan ONE — Endpoint de validação ambiental da cura (F12, Sprint Q.49.B)
============================================================================

Cruza as operações de cura/desmolde executadas num período com as leituras
reais de temperatura/humidade da tabela ERP `TH`, e devolve quais decorreram
fora do intervalo ambiental aceitável.

NÃO é uma constraint do scheduler — é diagnóstico a posteriori. Os 7 axiomas
Spelke e o decoder/fitness ficam intactos: este endpoint só lê.

Endpoint
--------
    GET /v1/plan/curing-validation?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD

Intervalo aceitável (logic-as-data)
-----------------------------------
O range temperatura/humidade e a lista de fases de cura vêm da
`TenantConfigService` (categoria `quality`, chaves `curing.*`). Quando o
tenant não definiu política própria usam-se os defaults documentados em
`curing_validation_service` — nunca um número enterrado no cálculo.

Honestidade de degradação
-------------------------
Em dev `sqlserver_enabled=False`, logo os readers `list_operations` e
`list_temperature_humidity` lançam `RuntimeError`. Este endpoint apanha-o e
devolve, com HTTP 200, `status="sem_dados_sensor"` — uma resposta explícita
de que não há leituras de sensor para validar, NUNCA uma % de conformidade
inventada.
"""

from __future__ import annotations

import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.nelo import services as nelo_services
from src.core.services.tenant_config_service import TenantConfigService
from src.plan.services.curing_validation_service import (
    DEFAULT_CURING_PHASE_CODES,
    DEFAULT_HUMIDITY_MAX_PCT,
    DEFAULT_HUMIDITY_MIN_PCT,
    DEFAULT_TEMP_MAX_C,
    DEFAULT_TEMP_MIN_C,
    EnvironmentRange,
    curing_operations_from_rows,
    sensor_readings_from_rows,
    validate_curing_window,
)
from src.shared.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Plan"])

# Tecto da janela: cruzar `TH` (~586 k linhas) com `OF_FP` (2.6 M) é caro;
# uma janela demasiado larga arrisca varreduras enormes. 92 dias ≈ um
# trimestre, que cobre qualquer análise retrospectiva razoável.
MAX_WINDOW_DAYS: int = 92


def get_tenant_id(x_tenant_id: UUID = Header(..., alias="X-Tenant-Id")) -> UUID:
    return x_tenant_id


async def _load_environment_range(
    session: AsyncSession, tenant_id: UUID
) -> tuple[EnvironmentRange, tuple[str, ...]]:
    """Lê o intervalo aceitável + fases de cura da config do tenant.

    Cai para os defaults documentados do serviço quando o tenant não tem
    política própria (ou a config não está disponível) — logic-as-data com
    fallback honesto, não um número enterrado.
    """
    try:
        cfg = TenantConfigService(session, tenant_id)
        env = EnvironmentRange(
            temp_min_c=float(await cfg.get(
                "quality", "curing.temp_min_c", default=DEFAULT_TEMP_MIN_C)),
            temp_max_c=float(await cfg.get(
                "quality", "curing.temp_max_c", default=DEFAULT_TEMP_MAX_C)),
            humidity_min_pct=float(await cfg.get(
                "quality", "curing.humidity_min_pct",
                default=DEFAULT_HUMIDITY_MIN_PCT)),
            humidity_max_pct=float(await cfg.get(
                "quality", "curing.humidity_max_pct",
                default=DEFAULT_HUMIDITY_MAX_PCT)),
        )
        raw_codes = await cfg.get(
            "quality", "curing.phase_codes",
            default=",".join(DEFAULT_CURING_PHASE_CODES),
        )
    except Exception:  # noqa: BLE001 — config indisponível → defaults documentados
        return EnvironmentRange(), DEFAULT_CURING_PHASE_CODES

    codes = tuple(c.strip() for c in str(raw_codes).split(",") if c.strip())
    return env, (codes or DEFAULT_CURING_PHASE_CODES)


@router.get("/curing-validation")
async def curing_validation(
    date_from: date = Query(..., description="Início do período (inclusivo)"),
    date_to: date = Query(..., description="Fim do período (inclusivo)"),
    tenant_id: UUID = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
):
    """Validação ambiental retrospectiva das operações de cura num período."""
    if date_to < date_from:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="date_to não pode ser anterior a date_from",
        )
    if (date_to - date_from).days > MAX_WINDOW_DAYS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Janela máxima de {MAX_WINDOW_DAYS} dias (cura cruza TH × OF_FP)",
        )

    env, curing_phase_codes = await _load_environment_range(session, tenant_id)

    # `window` é comum a todas as respostas; `environment_range` vem do
    # `result.to_dict()` no caminho real e acrescenta-se à parte na
    # degradação (onde não há `result`).
    base = {"window": {"from": date_from.isoformat(), "to": date_to.isoformat()}}

    # Caminho real: ler operações + leituras de TH. Em dev
    # (sqlserver_enabled=False) os readers lançam RuntimeError — degradação
    # honesta, sem % de conformidade inventada.
    try:
        operation_rows = await nelo_services.list_operations(
            date_from=date_from, date_to=date_to,
        )
        reading_rows = await nelo_services.list_temperature_humidity(
            date_from=date_from, date_to=date_to,
        )
    except RuntimeError as exc:
        logger.info("Validação da cura: ERP/sensor indisponível — %s", exc)
        return {
            **base,
            "status": "sem_dados_sensor",
            "environment_range": env.to_dict(),
            "detail": (
                "O ERP MAR-KAYAKS não está ligado (sqlserver_enabled=False); "
                "não há leituras de temperatura/humidade (TH) para validar a "
                "cura. Liga o sync do ERP para obter a validação ambiental."
            ),
        }

    operations = curing_operations_from_rows(operation_rows, curing_phase_codes)
    readings = sensor_readings_from_rows(reading_rows)
    result = validate_curing_window(
        operations, readings, environment_range=env,
    )

    return {**base, **result.to_dict()}
