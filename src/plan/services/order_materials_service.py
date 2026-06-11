"""Materiais restantes por Ordem de Fabrico (Q.173.U).

Lê ``factory_raw.movimento`` (espelho local do ERP) e ``supply.warehouse_stock``
para devolver, por OF, os materiais reservados ainda não consumidos e os já
consumidos — com stock disponível actual para cada componente.

Mapeamento de chaves (confirmado na BD 2026-06-11):
- ``MOV_P_ID`` (int)  ==  ``CAST(supply.warehouse_stock.product_code AS int)``
  (product_code é string numérica, ex. "22394").
- ``MOV_P_ID`` (int)  ==  ``CAST(core.products.product_code AS int)``
  (mesmo valor; core.products é a camada curada).
- Coluna de quantidade: ``MOV_QUANTIDADE`` (double precision).
- Coluna de tipo: ``MOV_TPMOV_ID`` (int).
- Coluna satisfeito: ``MOV_SATISFEITO`` (bool).

Estado honesto: OF sem movimentos do tipo relevante → ``items=[]``,
``fonte="movimento(tpmov=4,11)"``. Nunca inventa dados.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.supply.movement_types import TPMOV_CONSUMO_OF, TPMOV_RESERVA


@dataclass
class MaterialRestante:
    """Situação de um material para uma OF."""

    produto_id: int
    produto_nome: Optional[str]
    qty_reservada_aberta: float
    """Quantidade reservada (TPMOV=4, MOV_SATISFEITO=False) ainda por satisfazer."""
    qty_consumida: float
    """Quantidade já consumida (TPMOV=11)."""
    stock_disponivel: Optional[float]
    """Stock actual em ``supply.warehouse_stock`` (soma por armazém). None = sem snapshot."""
    stock_suficiente: Optional[bool]
    """True se stock >= qty_reservada_aberta. None quando stock_disponivel é None."""


@dataclass
class OrdemMaterialsResult:
    """Resultado de ``OrderMaterialsService.materiais_restantes``."""

    of_legacy_id: int
    items: List[MaterialRestante] = field(default_factory=list)
    fonte: str = "movimento(tpmov=4,11)"
    """Indica a fonte dos dados — nunca fica vazia; honesta sobre ausência de dados."""
    stock_snapshot_disponivel: bool = False
    """True quando ``supply.warehouse_stock`` tem linhas (ETL correu)."""


class OrderMaterialsService:
    """Serviço de materiais restantes por OF — só leitura."""

    def __init__(self, session: AsyncSession, tenant_id: Any) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def materiais_restantes(self, of_legacy_id: int) -> OrdemMaterialsResult:
        """Devolve materiais reservados (TPMOV=4 não satisfeitos) e consumidos
        (TPMOV=11) para a OF, cruzados com stock actual.

        Devolve lista vazia quando a OF não tem movimentos do tipo relevante —
        nunca inventa dados nem sinaliza "materiais OK" sem evidência.
        """
        reservas = await self._reservas_abertas(of_legacy_id)
        consumos = await self._consumos(of_legacy_id)
        stock_map = await self._stock_por_produto()
        nomes_map = await self._nomes_produto(
            set(reservas.keys()) | set(consumos.keys())
        )

        produto_ids = sorted(set(reservas.keys()) | set(consumos.keys()))
        items: List[MaterialRestante] = []
        for pid in produto_ids:
            qty_res = reservas.get(pid, 0.0)
            qty_con = consumos.get(pid, 0.0)
            stock = stock_map.get(pid)  # None quando sem snapshot
            suf: Optional[bool] = None
            if stock is not None:
                suf = stock >= qty_res
            items.append(MaterialRestante(
                produto_id=pid,
                produto_nome=nomes_map.get(pid),
                qty_reservada_aberta=qty_res,
                qty_consumida=qty_con,
                stock_disponivel=stock,
                stock_suficiente=suf,
            ))

        return OrdemMaterialsResult(
            of_legacy_id=of_legacy_id,
            items=items,
            fonte="movimento(tpmov=4,11)",
            stock_snapshot_disponivel=bool(stock_map),
        )

    # ------------------------------------------------------------------
    # helpers privados

    async def _reservas_abertas(self, of_id: int) -> Dict[int, float]:
        """Soma MOV_QUANTIDADE por produto para TPMOV=4, MOV_SATISFEITO=False."""
        sql = text(
            'SELECT "MOV_P_ID", COALESCE(SUM("MOV_QUANTIDADE"), 0) '
            "FROM factory_raw.movimento "
            'WHERE "MOV_OF_ID" = :of_id '
            '  AND "MOV_TPMOV_ID" = :tpmov '
            '  AND ("MOV_SATISFEITO" = false OR "MOV_SATISFEITO" IS NULL) '
            'GROUP BY "MOV_P_ID"'
        )
        rows = (
            await self._session.execute(
                sql, {"of_id": of_id, "tpmov": TPMOV_RESERVA}
            )
        ).all()
        return {int(r[0]): float(r[1]) for r in rows if r[0] is not None}

    async def _consumos(self, of_id: int) -> Dict[int, float]:
        """Soma MOV_QUANTIDADE por produto para TPMOV=11."""
        sql = text(
            'SELECT "MOV_P_ID", COALESCE(SUM("MOV_QUANTIDADE"), 0) '
            "FROM factory_raw.movimento "
            'WHERE "MOV_OF_ID" = :of_id '
            '  AND "MOV_TPMOV_ID" = :tpmov '
            'GROUP BY "MOV_P_ID"'
        )
        rows = (
            await self._session.execute(
                sql, {"of_id": of_id, "tpmov": TPMOV_CONSUMO_OF}
            )
        ).all()
        return {int(r[0]): float(r[1]) for r in rows if r[0] is not None}

    async def _stock_por_produto(self) -> Dict[int, float]:
        """Soma stock por produto_id inteiro a partir de supply.warehouse_stock.

        ``product_code`` em warehouse_stock é string numérica que corresponde
        ao ``MOV_P_ID`` inteiro do ERP.
        """
        sql = text(
            "SELECT CAST(product_code AS integer), SUM(stock) "
            "FROM supply.warehouse_stock "
            "WHERE tenant_id = :tid "
            "  AND product_code ~ '^[0-9]+$' "
            "GROUP BY product_code"
        )
        try:
            rows = (
                await self._session.execute(sql, {"tid": str(self._tenant_id)})
            ).all()
        except Exception:  # noqa: BLE001  # defesa: ETL stock não correu → campo fica vazio honesto
            return {}
        return {int(r[0]): float(r[1]) for r in rows if r[0] is not None}

    async def _nomes_produto(self, produto_ids: set[int]) -> Dict[int, str]:
        """Lookup nome do produto em factory_raw.produto."""
        if not produto_ids:
            return {}
        sql = text(
            'SELECT "P_ID", "P_NOME" '
            "FROM factory_raw.produto "
            'WHERE "P_ID" = ANY(:ids)'
        )
        try:
            rows = (
                await self._session.execute(
                    sql, {"ids": list(produto_ids)}
                )
            ).all()
        except Exception:  # noqa: BLE001  # defesa: espelho produto sem dados → nomes ficam vazios
            return {}
        return {int(r[0]): str(r[1]) for r in rows if r[0] is not None and r[1]}
