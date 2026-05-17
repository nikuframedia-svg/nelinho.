"""Q.26.B — custo de material a partir do BOM real sincronizado.

Explode a lista de materiais (`core.bom_items`) de um produto acabado e
preca cada componente ao seu custo standard do ERP
(`core.products.standard_cost`, sincronizado pelo Q.26.A).

**Single-level, de proposito.** O `standard_cost` de cada componente ja e
o seu custo rolado (o ERP mantem `P_PRECOCUSTO` para componentes E
sub-conjuntos). Somar os componentes directos da o custo de material do
produto acabado sem dupla contagem — explodir recursivamente sub-conjuntos
que ja tem custo proprio contaria o mesmo material duas vezes.

O resultado expoe `bom_costs` — o dict `{codigo: custo}` que o
`COGSCalculator` consome no componente de material.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.bom import BOMItem
from src.core.models.product import Product

_ZERO = Decimal("0")
_ONE = Decimal("1")


@dataclass(frozen=True)
class MaterialCostLine:
    """Uma linha de BOM precada — um componente do produto acabado."""

    component_code: str
    component_name: str
    quantity_per: Decimal
    scrap_factor: Decimal
    unit_cost: Decimal       # standard_cost do componente (0 se ausente)
    has_cost: bool           # False quando o ERP nao tem custo do componente

    @property
    def line_cost(self) -> Decimal:
        """Custo da linha = quantidade x scrap x custo unitario."""
        return self.quantity_per * self.scrap_factor * self.unit_cost


@dataclass(frozen=True)
class MaterialCostResult:
    """Custo de material de um produto acabado, por unidade."""

    product_id: UUID
    total_material_cost: Decimal
    component_count: int
    missing_cost_count: int          # componentes sem custo no ERP
    lines: tuple[MaterialCostLine, ...]

    @classmethod
    def from_lines(
        cls, product_id: UUID, lines: Sequence[MaterialCostLine]
    ) -> "MaterialCostResult":
        """Agrega linhas num resultado — puro, sem BD (testavel directo)."""
        lines = tuple(lines)
        total = sum((ln.line_cost for ln in lines), _ZERO)
        missing = sum(1 for ln in lines if not ln.has_cost)
        return cls(
            product_id=product_id,
            total_material_cost=total,
            component_count=len(lines),
            missing_cost_count=missing,
            lines=lines,
        )

    @property
    def bom_costs(self) -> dict[str, Decimal]:
        """Dict `{codigo_componente: custo}` para o COGSCalculator.

        Componentes repetidos (varias linhas de BOM com o mesmo codigo)
        sao somados — o dict nunca perde uma linha.
        """
        acc: dict[str, Decimal] = {}
        for ln in self.lines:
            acc[ln.component_code] = acc.get(ln.component_code, _ZERO) + ln.line_cost
        return acc

    @property
    def is_complete(self) -> bool:
        """True quando todos os componentes tinham custo no ERP."""
        return self.component_count > 0 and self.missing_cost_count == 0


class MaterialCostService:
    """Calcula o custo de material de um produto a partir do BOM sincronizado."""

    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def material_cost(
        self, product_id: UUID, as_of: Optional[date] = None
    ) -> MaterialCostResult:
        """Custo de material por unidade do produto acabado `product_id`.

        Considera so as linhas de BOM efectivas em `as_of` (hoje por
        omissao). Componentes sem `standard_cost` entram com custo 0 e sao
        contados em `missing_cost_count` — o custo nunca e inventado.
        """
        as_of = as_of or date.today()
        stmt = (
            select(
                BOMItem.quantity_per,
                BOMItem.scrap_factor,
                Product.product_code,
                Product.product_name,
                Product.standard_cost,
            )
            .join(Product, Product.id == BOMItem.component_product_id)
            .where(
                BOMItem.tenant_id == self.tenant_id,
                BOMItem.parent_product_id == product_id,
                or_(BOMItem.effective_from.is_(None), BOMItem.effective_from <= as_of),
                or_(BOMItem.effective_to.is_(None), BOMItem.effective_to >= as_of),
            )
        )
        rows = (await self.session.execute(stmt)).all()
        return MaterialCostResult.from_lines(
            product_id, [_row_to_line(r) for r in rows]
        )


def _row_to_line(row) -> MaterialCostLine:
    """Linha do SELECT (quantity_per, scrap_factor, code, name, cost) -> linha."""
    quantity_per, scrap_factor, code, name, std_cost = row
    has_cost = std_cost is not None and std_cost > _ZERO
    return MaterialCostLine(
        component_code=str(code),
        component_name=str(name or code),
        quantity_per=quantity_per if quantity_per is not None else _ZERO,
        scrap_factor=scrap_factor if scrap_factor is not None else _ONE,
        unit_cost=std_cost if has_cost else _ZERO,
        has_cost=has_cost,
    )
