"""Q.54.D — junta o plano optimizado do CPO com as ordens do chão de fábrica.

A página Fábrica mostra o estado CRU do ERP (``/v1/plan/orders/active``).
O CPO produz um :class:`~src.plan.cpo.commits.ScheduleCommit` com o plano
optimizado — barco → fase → operador → molde + datas — mas nenhum endpoint
o devolvia numa forma que o frontend consiga consumir lado-a-lado com as
ordens activas.

Este módulo tem a lógica PURA de merge (sem sessão, sem I/O) para ser
testável directamente: pega no ``operations[]`` de um commit, nas
``ProductionOrder`` activas e nos mapas de nomes (operador/máquina) e
devolve uma lista com a MESMA forma de ``/orders/active`` mais os campos
optimizados.

Forma de cada item devolvido::

    {
      # --- iguais a /orders/active ---
      "id", "hull", "product_name", "product_type", "customer_name",
      "phase", "phase_sequence", "status", "created_date", "transport_date",
      # --- campos optimizados (Q.54.D) ---
      "optimized_phase",        # nome/ID da fase planeada para o próximo passo
      "optimized_phase_sequence",
      "assigned_employee_id",   # primeiro operador atribuído a essa operação
      "assigned_employee_name",
      "assigned_machine_id",
      "scheduled_start",        # ISO-8601 ou null
      "scheduled_end",
      "in_optimized_plan",      # bool — a ordem aparece no commit?
    }

Campo que não resolve → ``null`` honesto (zero mocks). Uma ordem activa que
o commit não planeou continua na lista com ``in_optimized_plan=False`` e os
campos optimizados a ``null`` — assim o frontend mostra o gap.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from src.plan.models.order import ProductionOrder
from src.plan.services.phase_classification import phase_sequence

__all__ = ["merge_commit_with_orders", "pick_operation_for_order"]


def _op_order_key(op: Mapping[str, Any]) -> str:
    """Chave de junção: o ``order_id`` da operação (= OF nº = ``legacy_id``)."""
    return str(op.get("order_id") or "").strip()


def _op_start(op: Mapping[str, Any]) -> str:
    """``start_time`` da operação como string ordenável ('' ordena primeiro)."""
    return str(op.get("start_time") or "")


def pick_operation_for_order(
    order: ProductionOrder,
    ops: List[Mapping[str, Any]],
) -> Optional[Mapping[str, Any]]:
    """Escolhe a operação relevante de uma ordem dentro do plano do commit.

    Uma ordem tem várias operações no commit (uma por fase). O frontend
    Fábrica mostra UM cartão por barco, por isso escolhemos a operação que
    melhor representa o "próximo passo optimizado":

    1. A operação cujo ``phase_id``/``setup_family`` casa com a fase actual
       da ordem (``current_phase_name``) — é o passo onde o barco está.
    2. Caso contrário, a operação com ``start_time`` mais cedo das que ainda
       não acabaram — o próximo passo planeado.
    3. Caso contrário (todas sem datas), a primeira da lista.

    Devolve ``None`` quando a ordem não tem operações no commit.
    """
    if not ops:
        return None

    current = (order.current_phase_name or "").strip().lower()
    if current:
        for op in ops:
            phase = str(op.get("setup_family") or op.get("phase_id") or "").strip().lower()
            if phase and phase == current:
                return op

    # Sem match de fase → a operação que arranca mais cedo.
    dated = sorted(
        (op for op in ops if _op_start(op)),
        key=_op_start,
    )
    if dated:
        return dated[0]
    return ops[0]


def _optimized_phase(op: Mapping[str, Any]) -> Optional[str]:
    """Nome (ou ID) da fase optimizada de uma operação.

    ``setup_family`` carrega o nome canónico da fase (o ``RoutingResolver``
    põe lá ``fase_nome``); ``phase_id`` é o fallback honesto. ``None`` quando
    nenhum dos dois resolve.
    """
    return (
        str(op.get("setup_family")).strip() or None
        if op.get("setup_family")
        else (str(op.get("phase_id")).strip() or None if op.get("phase_id") else None)
    )


def _first_worker(op: Mapping[str, Any]) -> Optional[str]:
    """Primeiro operador atribuído à operação (``None`` se nenhum)."""
    workers = op.get("workers") or []
    if isinstance(workers, (list, tuple)) and workers:
        first = workers[0]
        return str(first) if first is not None else None
    return None


def merge_commit_with_orders(
    *,
    operations: List[Mapping[str, Any]],
    orders: List[ProductionOrder],
    employee_names: Mapping[str, str],
) -> List[Dict[str, Any]]:
    """Junta o plano optimizado (``operations``) com as ordens activas.

    Args:
        operations: ``ScheduleCommit.operations`` — lista de dicts já
            serializados pelo decoder.
        orders: ``ProductionOrder`` activas (mesma lista de
            ``/orders/active``).
        employee_names: mapa ``{employee_code: employee_name}`` para
            resolver o nome do operador atribuído.

    Returns:
        Lista de dicts com a forma de ``/orders/active`` + campos
        optimizados. Ordens fora do plano vêm com ``in_optimized_plan=False``
        e campos optimizados a ``null``.
    """
    # Indexa operações por order_id (= legacy_id da ordem).
    ops_by_order: Dict[str, List[Mapping[str, Any]]] = {}
    for op in operations:
        key = _op_order_key(op)
        if not key:
            continue
        ops_by_order.setdefault(key, []).append(op)

    out: List[Dict[str, Any]] = []
    for order in orders:
        legacy = str(order.legacy_id) if order.legacy_id is not None else ""
        order_ops = ops_by_order.get(legacy, [])
        chosen = pick_operation_for_order(order, order_ops)

        item: Dict[str, Any] = {
            # --- forma idêntica a /orders/active ---
            "id": str(order.id),
            "hull": legacy or None,
            "product_name": order.product_name,
            "product_type": order.product_type,
            "customer_name": getattr(order, "customer_name", None),
            "phase": order.current_phase_name,
            "phase_sequence": phase_sequence(order.current_phase_name),
            "status": (
                order.status.value
                if hasattr(order.status, "value")
                else str(order.status)
            ),
            "created_date": (
                order.created_date.isoformat() if order.created_date else None
            ),
            "transport_date": (
                order.transport_date.isoformat() if order.transport_date else None
            ),
            # --- campos optimizados (Q.54.D) ---
            "in_optimized_plan": chosen is not None,
            "optimized_phase": None,
            "optimized_phase_sequence": None,
            "assigned_employee_id": None,
            "assigned_employee_name": None,
            "assigned_machine_id": None,
            "scheduled_start": None,
            "scheduled_end": None,
        }

        if chosen is not None:
            opt_phase = _optimized_phase(chosen)
            emp_id = _first_worker(chosen)
            machine = chosen.get("machine_id")
            item.update(
                {
                    "optimized_phase": opt_phase,
                    "optimized_phase_sequence": phase_sequence(opt_phase),
                    "assigned_employee_id": emp_id,
                    "assigned_employee_name": (
                        employee_names.get(emp_id) if emp_id else None
                    ),
                    "assigned_machine_id": (
                        str(machine).strip() or None if machine else None
                    ),
                    "scheduled_start": (
                        str(chosen.get("start_time")) if chosen.get("start_time") else None
                    ),
                    "scheduled_end": (
                        str(chosen.get("end_time")) if chosen.get("end_time") else None
                    ),
                }
            )

        out.append(item)

    return out
