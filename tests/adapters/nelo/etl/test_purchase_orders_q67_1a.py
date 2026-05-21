"""Q.67.1.A — pin do comportamento placeholder de purchase_orders.

Os 3 TODOs deste mirror ficaram documentados como `Q.67.1.A: bloqueado
pendente <X> (issue Q.68.A)` em vez de serem fechados:

1. `supplier_name` = `f"Fornecedor {entity_id}"` — pendente mirror
   ENTIDADE (lookup ENTIDADE.ENT_NOME).
2. `unit_cost`/`total_cost` — pendente migration alembic (drift chain
   congelada em Q.62.A).
3. `eta` = `ordered_at + 30 dias` — pendente helper
   MOVIMENTO_FORNECEDOR.MOVFOR_ETA.

Este teste pin garante que o comportamento actual placeholder NÃO
regride enquanto a issue Q.68.A não for executada. Se algum destes
asserts falhar, ou o placeholder foi alterado por engano OU a issue
Q.68.A está em execução — neste caso, apagar este ficheiro e o teste
canónico em `test_purchase_orders_q64_d.py` passa a refletir o
comportamento real.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from src.adapters.nelo.etl.purchase_orders import (
    _ETA_PLACEHOLDER_DAYS,
    _PO_MOVEMENT_TYPE_ID,
    _map_movement_to_po,
)
from src.adapters.nelo.schemas import MovementRow


def _mov(**kw) -> MovementRow:
    """MovementRow com defaults — tipo 9 (PO) por defeito."""
    base = dict(
        movement_id=12345,
        moved_at=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc),
        exit_date=None,
        quantity=10.5,
        unit_price=2.5,
        sale_price=3.0,
        discount=0.0,
        movement_type_id=_PO_MOVEMENT_TYPE_ID,
        work_order_id=None,
        work_order_phase_id=None,
        product_id=42,
        entity_id=777,
        warehouse_id=1,
        phase_id=None,
        routing_id=None,
        parent_movement_id=None,
        batch=None,
        balance_quantity=100.0,
        is_adjustment=False,
        is_defective=False,
        is_satisfied=True,
        approved_at=None,
        observations=None,
        problem=None,
    )
    base.update(kw)
    return MovementRow(**base)


# ── TODO #1 pin: supplier_name placeholder ──────────────────────────


def test_q67_1a_supplier_name_is_placeholder_format():
    """`supplier_name` é placeholder `Fornecedor <entity_id>` até ENTIDADE
    mirror existir (Q.68.A)."""
    row = _mov(entity_id=777)
    mapped = _map_movement_to_po(row)
    assert mapped is not None
    assert mapped["supplier_name"].startswith("Fornecedor "), (
        "Q.67.1.A pin: supplier_name deve ser placeholder `Fornecedor <id>`. "
        "Se este teste falha, ENTIDADE lookup foi implementado — apagar este ficheiro."
    )
    assert mapped["supplier_name"] == "Fornecedor 777"


def test_q67_1a_supplier_name_fallback_when_entity_missing():
    """Sem entity_id, placeholder específico — também é placeholder."""
    row = _mov(entity_id=None)
    mapped = _map_movement_to_po(row)
    assert mapped is not None
    assert mapped["supplier_name"] == "Fornecedor desconhecido", (
        "Q.67.1.A pin: fallback placeholder mantém-se até ENTIDADE mirror."
    )


# ── TODO #2 pin: unit_cost/total_cost não mapeados ──────────────────


def test_q67_1a_unit_cost_not_in_mapped_row():
    """O dict resultado NÃO tem `unit_cost`/`total_cost` — colunas ausentes
    no model `PurchaseOrder` até migration alembic Q.68.A."""
    row = _mov(unit_price=2.5, quantity=10.0)
    mapped = _map_movement_to_po(row)
    assert mapped is not None
    assert "unit_cost" not in mapped, (
        "Q.67.1.A pin: unit_cost não pode estar mapeado enquanto a coluna "
        "não existir no model. Se este teste falha, a migration foi aplicada "
        "— apagar este ficheiro e completar `test_purchase_orders_q64_d.py`."
    )
    assert "total_cost" not in mapped
    assert "currency_code" not in mapped


def test_q67_1a_unit_price_is_read_but_discarded():
    """`unit_price` é lido (para detectar drift do schema MovementRow)
    mas o valor não chega ao mapped row. Este teste pin garante que o
    discard intencional não foi acidentalmente removido."""
    # Se MovementRow perder `unit_price`, este construtor explode — é o
    # canário que justifica o `_ = Decimal(...)` no mapper.
    row = _mov(unit_price=99.99)
    mapped = _map_movement_to_po(row)
    assert mapped is not None
    # nenhum campo do mapped contém o valor `99.99`
    for key, value in mapped.items():
        if isinstance(value, Decimal):
            assert value != Decimal("99.990000"), (
                f"Q.67.1.A pin: unit_price não pode propagar para {key}"
            )


# ── TODO #3 pin: eta = ordered_at + 30 dias ─────────────────────────


def test_q67_1a_eta_is_ordered_at_plus_30_days():
    """ETA é placeholder `ordered_at + 30d`. ETA real do ERP
    (MOVIMENTO_FORNECEDOR.MOVFOR_ETA) só vem depois de Q.68.A."""
    row = _mov(moved_at=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc))
    mapped = _map_movement_to_po(row)
    assert mapped is not None
    ordered_at = mapped["ordered_at"]
    eta = mapped["eta"]
    assert ordered_at == date(2026, 5, 20)
    assert eta - ordered_at == timedelta(days=30), (
        "Q.67.1.A pin: ETA deve ser ordered_at + 30d (placeholder). Se este "
        "teste falha, MOVIMENTO_FORNECEDOR.MOVFOR_ETA foi ligado — "
        "apagar este ficheiro."
    )
    assert eta == date(2026, 6, 19)


def test_q67_1a_eta_placeholder_constant_is_30():
    """A constante `_ETA_PLACEHOLDER_DAYS` está fixada em 30. Mudá-la
    sem ligar MOVFOR_ETA é uma decisão de produto — este pin força a
    discussão explícita."""
    assert _ETA_PLACEHOLDER_DAYS == 30, (
        "Q.67.1.A pin: lead-time placeholder não deve ser alterado sem "
        "fechar a issue Q.68.A (ler ETA real do ERP)."
    )


# ── meta: comentários Q.67.1.A presentes no ficheiro ────────────────


def test_q67_1a_todos_documented_in_source():
    """Os 3 placeholders têm anotação `Q.67.1.A: bloqueado pendente ...
    (issue Q.68.A)` no ficheiro. Se forem removidos sem fechar a issue,
    perdemos o trail — este teste é o canário."""
    from pathlib import Path

    text = Path("src/adapters/nelo/etl/purchase_orders.py").read_text(
        encoding="utf-8"
    )
    occurrences = text.count("Q.67.1.A:")
    assert occurrences >= 3, (
        f"Q.67.1.A pin: esperava >=3 anotações `Q.67.1.A:` (uma por "
        f"TODO), encontrei {occurrences}. Não remover sem fechar Q.68.A."
    )
    assert "Q.68.A" in text, (
        "Q.67.1.A pin: a referência à issue Q.68.A deve permanecer no ficheiro."
    )
