"""
Q.37.D — handler de inventário: `adjust_inventory`.

Escreve `Product.safety_stock`. Recusa descer abaixo do baseline
(axioma 7 — safety_net ≥ baseline): se o payload trouxer
`baseline_safety_stock`, o novo valor não pode ficar abaixo dele;
em qualquer caso o stock de segurança não pode ser negativo.

O handler corre dentro do `ActionExecutor`:
  * SANDBOX — a mutação é feita e o savepoint é revertido pelo executor;
  * EXECUTE — a mutação fica no `flush()`/`commit()` do executor + audit log.

Devolve o estado no mesmo formato que `ActionExecutor._capture_state`
produz para `adjust_inventory` (`{"products": [...]}`), para que
`_calculate_actual_impact` calcule os deltas correctamente.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select

from src.core.models.product import Product

logger = logging.getLogger(__name__)


class InventoryAdjustmentRejected(ValueError):
    """Ajuste de inventário recusado (ex.: violaria o axioma 7)."""


def _to_decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InventoryAdjustmentRejected(
            f"{field} não é um número válido: {value!r}"
        ) from exc


async def adjust_inventory(
    executor: "Any",  # ActionExecutor — evita import circular
    action: "Any",  # Action
    plan_id: Optional[UUID],
) -> Dict[str, Any]:
    """Ajusta `safety_stock` de um produto.

    Payload esperado em ``action.payload``::

        {
            "target": "<product_id UUID>",
            "new_safety_stock": 120,
            "baseline_safety_stock": 100   # opcional — piso do axioma 7
        }
    """
    payload = action.payload or {}
    target = payload.get("target")
    if not target:
        raise InventoryAdjustmentRejected(
            "adjust_inventory precisa de payload.target (product_id)."
        )
    try:
        product_id = UUID(str(target))
    except (ValueError, TypeError) as exc:
        raise InventoryAdjustmentRejected(
            f"payload.target não é um UUID válido: {target!r}"
        ) from exc

    if "new_safety_stock" not in payload:
        raise InventoryAdjustmentRejected(
            "adjust_inventory precisa de payload.new_safety_stock."
        )
    new_value = _to_decimal(payload["new_safety_stock"], "new_safety_stock")

    # Axioma 7 — safety_net nunca abaixo do baseline. Sem baseline
    # explícito, o piso é zero (stock de segurança negativo é absurdo).
    if "baseline_safety_stock" in payload:
        baseline = _to_decimal(
            payload["baseline_safety_stock"], "baseline_safety_stock"
        )
    else:
        baseline = Decimal("0")

    if new_value < baseline:
        raise InventoryAdjustmentRejected(
            f"Ajuste recusado: novo safety_stock {new_value} fica abaixo "
            f"do baseline {baseline} (axioma 7 — safety_net ≥ baseline)."
        )

    result = await executor.session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == executor.tenant_id,
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise InventoryAdjustmentRejected(
            f"Produto {product_id} não encontrado neste tenant."
        )

    old_value = product.safety_stock
    product.safety_stock = new_value
    await executor.session.flush()

    logger.info(
        "adjust_inventory: produto=%s safety_stock %s → %s (tenant=%s)",
        product.product_code, old_value, new_value, executor.tenant_id,
    )

    # Mesmo formato que `_capture_state` produz para adjust_inventory.
    return {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "action_type": action.type,
        "plan_id": str(plan_id) if plan_id else None,
        "products": [
            {
                "id": str(product.id),
                "product_code": product.product_code,
                "safety_stock": float(new_value),
                "lead_time_days": product.lead_time_days,
            }
        ],
        "adjustment": {
            "product_id": str(product.id),
            "old_safety_stock": float(old_value) if old_value is not None else 0.0,
            "new_safety_stock": float(new_value),
            "baseline_safety_stock": float(baseline),
        },
    }
