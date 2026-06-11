"""Q.173.AA — Mediana e moda de consumo histórico por (modelo, material).

Fonte: factory_raw.movimento TPMOV=11 com MOV_OF_ID →
join factory_raw.ordemfabrico (OF_P_ID = modelo).

Por OF calcula a qty consumida de cada material; depois agrega por
(modelo, material): mediana (PERCENTILE_CONT 0.5) e moda
(MODE() WITHIN GROUP) da qty por OF, e nº de OFs.

Exposto como serviço puro (sem FastAPI) para ser chamado tanto pelo router
de consumption-by-model como pelo shortage_forecast_service (campo
`consumo_mediano_por_barco`).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ConsumoMaterialInfo:
    """Consumo histórico de um material num modelo."""

    __slots__ = (
        "mediana_qty",
        "moda_qty",
        "n_ofs",
        "product_code",
        "product_name",
    )

    def __init__(
        self,
        product_code: str,
        product_name: str,
        mediana_qty: Optional[float],
        moda_qty: Optional[float],
        n_ofs: int,
    ) -> None:
        self.product_code = product_code
        self.product_name = product_name
        self.mediana_qty = mediana_qty
        self.moda_qty = moda_qty
        self.n_ofs = n_ofs

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_code": self.product_code,
            "product_name": self.product_name,
            "mediana_qty_por_of": self.mediana_qty,
            "moda_qty_por_of": self.moda_qty,
            "n_ofs": self.n_ofs,
        }


class ConsumptionByModelResult:
    """Resultado completo do consumo por modelo."""

    def __init__(
        self,
        *,
        model_id: int,
        model_name: str,
        materiais: List[ConsumoMaterialInfo],
        gerado_em: datetime,
        fonte: str,
    ) -> None:
        self.model_id = model_id
        self.model_name = model_name
        self.materiais = materiais
        self.gerado_em = gerado_em
        self.fonte = fonte

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_name": self.model_name,
            "materiais": [m.to_dict() for m in self.materiais],
            "total_materiais": len(self.materiais),
            "gerado_em": self.gerado_em.isoformat(),
            "fonte": self.fonte,
        }


class ConsumptionByModelService:
    """Consumo histórico por (modelo, material) — mediana e moda."""

    def __init__(self, session: AsyncSession, tenant_id: UUID) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def by_model(self, model_id: int) -> ConsumptionByModelResult:
        """Devolve mediana + moda de consumo por material para um modelo.

        Usa dados reais de factory_raw.movimento TPMOV=11 (consumo de OF)
        join ordemfabrico (OF_P_ID = modelo).

        Sem dados históricos devolve lista vazia — honesto (invariante #8).
        """
        # Nome do modelo
        r_nome = await self._session.execute(
            text('SELECT "P_NOME" FROM factory_raw.produto WHERE "P_ID" = :mid'),
            {"mid": model_id},
        )
        row_nome = r_nome.fetchone()
        model_name = str(row_nome[0]) if row_nome else str(model_id)

        # Consumo por OF: agrupa mov por (OF, material) → qty total
        # Depois agrega por material: mediana + moda
        q = text("""
            WITH consumo_por_of AS (
                SELECT
                    m."MOV_OF_ID"  AS of_id,
                    m."MOV_P_ID"   AS mat_id,
                    SUM(m."MOV_QUANTIDADE") AS qty
                FROM factory_raw.movimento m
                JOIN factory_raw.ordemfabrico of ON of."OF_ID" = m."MOV_OF_ID"
                WHERE m."MOV_TPMOV_ID" = 11
                  AND m."MOV_OF_ID" IS NOT NULL
                  AND of."OF_P_ID" = :model_id
                GROUP BY m."MOV_OF_ID", m."MOV_P_ID"
            )
            SELECT
                mat_id::text                                                        AS product_code,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY qty)                   AS mediana,
                MODE() WITHIN GROUP (ORDER BY qty)                                  AS moda,
                COUNT(DISTINCT of_id)                                               AS n_ofs
            FROM consumo_por_of
            GROUP BY mat_id
            ORDER BY n_ofs DESC, mediana DESC
        """)
        result = await self._session.execute(q, {"model_id": model_id})
        rows = result.fetchall()

        if not rows:
            return ConsumptionByModelResult(
                model_id=model_id,
                model_name=model_name,
                materiais=[],
                gerado_em=datetime.now(timezone.utc),
                fonte="factory_raw.movimento(TPMOV=11)",
            )

        # Nomes dos materiais
        mat_ids = [int(r[0]) for r in rows]
        r_nomes = await self._session.execute(
            text('SELECT "P_ID"::text, "P_NOME" FROM factory_raw.produto WHERE "P_ID" = ANY(:ids)'),
            {"ids": mat_ids},
        )
        nomes_map: Dict[str, str] = {
            str(row[0]): str(row[1] or "") for row in r_nomes.fetchall()
        }

        materiais = [
            ConsumoMaterialInfo(
                product_code=str(row[0]),
                product_name=nomes_map.get(str(row[0]), str(row[0])),
                mediana_qty=float(row[1]) if row[1] is not None else None,
                moda_qty=float(row[2]) if row[2] is not None else None,
                n_ofs=int(row[3]),
            )
            for row in rows
        ]

        return ConsumptionByModelResult(
            model_id=model_id,
            model_name=model_name,
            materiais=materiais,
            gerado_em=datetime.now(timezone.utc),
            fonte="factory_raw.movimento(TPMOV=11)+factory_raw.ordemfabrico",
        )
