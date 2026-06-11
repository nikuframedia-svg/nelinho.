"""Q.173.AS — CoeficienteX mirror (factory_raw.produto_fase → profit.phase_bonus_payout).

O ERP guarda em ``PRODF_COEFICIENTE_X`` o prémio (€) pago por (produto ×
fase) — confirmado pelo CEO em 2026-04-22 («this field is the bonus (€)
copied into each OF»). A tabela canónica ``profit.phase_bonus_payout``
(CX5) e o ``BonusPayoutService`` existem desde a migração 025a mas NUNCA
foram alimentados: 22.002 linhas prontas no espelho e a tabela a 0
(auditoria 2026-06-11).

Invariante #8 — espelho CRU, sem interpretação: ``bonus_eur`` é a cópia
literal de ``PRODF_COEFICIENTE_X``. A pergunta semântica aberta (#64 — o
valor é por OF? por unidade? por hora?) pertence aos CONSUMIDORES
(cost_service/payroll), nunca a este ETL.

Invariante #5 — CoeficienteX é DINHEIRO: vive em ``src/profit``; o CPO
(``src/plan/cpo``) nunca importa daqui.

Mapeamento de ids:
  * ``product_id`` — UUID real de ``core.products`` via ``product_code ==
    PRODF_P_ID::text`` (match 100%: 22.002/22.002 medido 2026-06-12).
  * ``phase_id`` — o schema CX5 pede UUID mas as fases do ERP são códigos
    int (``FP_ID``); não existe ``core.phases``. Usamos uuid5 determinístico
    (padrão da casa, ver checklist.py) — :func:`phase_uuid` é o helper
    PÚBLICO que qualquer consumidor deve usar para consultar por fase.
  * ``valid_from`` — ``PRODF_DATA`` (data de definição no ERP); sem data →
    sentinela 2000-01-01 = "validade aberta, ERP não versiona" (não é um
    número de negócio, é um marcador de janela).

Idempotente: conflito por ``(tenant_id, product_id, phase_id, valid_from)``
→ atualiza ``bonus_eur``. Linhas eliminadas (``PRODF_DATA_ELIMINADO``)
ficam fora; duplicados por (produto, fase) resolvem para o ``PRODF_ID``
mais recente.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional
from uuid import NAMESPACE_DNS, UUID, uuid5

from sqlalchemy import text

from .runner import EtlRunner, EtlRunResult
from .sync import register_mirror

logger = logging.getLogger(__name__)

# Sem data de definição no ERP — janela de validade aberta (ver docstring).
_VALID_FROM_FALLBACK = date(2000, 1, 1)

# 11 colunas/linha; asyncpg limita a 32.767 parâmetros por statement →
# 2.000 × 11 = 22.000 fica com folga.
_CHUNK = 2_000


def phase_uuid(fp_id: int | str) -> UUID:
    """UUID determinístico de uma fase do ERP (FP_ID) para o schema CX5.

    Qualquer consumidor de ``profit.phase_bonus_payout`` que parta de um
    código de fase do ERP deve usar ESTE helper — é o único contrato entre
    o código int do ERP e o ``phase_id`` UUID da tabela.
    """
    return uuid5(NAMESPACE_DNS, f"nelo-erp-fase-{int(fp_id)}")


_READ_SQL = text("""
    SELECT DISTINCT ON (pf."PRODF_P_ID", pf."PRODF_FP_ID")
           pf."PRODF_P_ID"          AS p_id,
           pf."PRODF_FP_ID"         AS fp_id,
           pf."PRODF_COEFICIENTE_X" AS coefx,
           NULLIF(pf."PRODF_DATA", '') AS prodf_data,
           cp.id                    AS product_uuid
    FROM factory_raw.produto_fase pf
    JOIN core.products cp
      ON cp.tenant_id = :tenant_id
     AND cp.product_code = pf."PRODF_P_ID"::text
    WHERE pf."PRODF_COEFICIENTE_X" IS NOT NULL
      AND pf."PRODF_COEFICIENTE_X" > 0
      AND pf."PRODF_FP_ID" IS NOT NULL
      AND NULLIF(pf."PRODF_DATA_ELIMINADO", '') IS NULL
    ORDER BY pf."PRODF_P_ID", pf."PRODF_FP_ID", pf."PRODF_ID" DESC
""")


def _parse_valid_from(raw: Optional[str]) -> date:
    if not raw:
        return _VALID_FROM_FALLBACK
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return _VALID_FROM_FALLBACK


async def mirror_bonus_payout(
    *,
    session,
    tenant_id: UUID,
    since: Optional[date] = None,
) -> EtlRunResult:
    """Mirror ``PRODF_COEFICIENTE_X`` → ``profit.phase_bonus_payout``.

    Lê o espelho LOCAL (``factory_raw.produto_fase``) — sem ida ao ERP —
    por isso é barato e corre no ciclo normal dos mirrors. ``since`` é
    ignorado (a fonte não tem watermark fiável; o upsert é idempotente).
    """
    from src.profit.services.bonus_payout_service import BonusPayoutService

    async with EtlRunner(session, tenant_id, source="bonus_payout") as run:
        rows = (
            await session.execute(_READ_SQL, {"tenant_id": str(tenant_id)})
        ).all()
        run.count_read(len(rows))

        payload = [
            {
                "product_id": r.product_uuid,
                "phase_id": phase_uuid(r.fp_id),
                "bonus_eur": r.coefx,
                "valid_from": _parse_valid_from(r.prodf_data),
                "source": "ERP_STANDARD",
            }
            for r in rows
        ]

        svc = BonusPayoutService(session, tenant_id)
        upserted = 0
        for i in range(0, len(payload), _CHUNK):
            upserted += await svc.bulk_upsert(payload[i : i + _CHUNK])
        # o ON CONFLICT do bulk_upsert não separa insert de update —
        # registamos o total processado como inserted (auditável no etl_run).
        run.result.rows_inserted += upserted

        logger.info(
            "bonus_payout mirror — %d (produto×fase) com CoeficienteX>0 "
            "espelhados (lidos %d)",
            upserted, len(rows),
        )

    return run.result


register_mirror("bonus_payout", mirror_bonus_payout)
