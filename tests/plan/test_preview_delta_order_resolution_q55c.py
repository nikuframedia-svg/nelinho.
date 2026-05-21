"""Q.55.C — o drag-drop da Fábrica identifica a operação por `order_id`.

O painel Fábrica só conhece o barco (o seu nº de OF / `hull`), não os ids
de operação internos do commit do CPO. Antes mandava `boat.id` (o UUID da
`ProductionOrder`) como `operation_id` — nunca casava com os ids das
operações do commit (chaveados por `order_id` = `legacy_id`) → 400.

Agora a mutação aceita `order_id` e o `PreviewDeltaService` resolve a
operação certa do commit. O `operation_id` directo continua a funcionar
(SchedulingPage / Timeline não regridem).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.plan.models.order import OrderStatus, ProductionOrder
from src.plan.services.preview_delta_service import (
    PreviewDeltaService,
    PreviewMutation,
)

TENANT = UUID("00000000-0000-0000-0000-000000000001")


def _order(phase: str) -> ProductionOrder:
    return ProductionOrder(
        id=uuid4(),
        tenant_id=TENANT,
        legacy_id=4272,
        product_name="K1 Vanquish",
        product_type="K1",
        current_phase_name=phase,
        status=OrderStatus.IN_PROGRESS,
    )


def _schedule() -> dict:
    """Commit com duas operações da OF 4272 — uma por fase."""
    return {
        "operations": [
            {"id": "op-lam", "order_id": "4272", "phase_id": "Laminagem"},
            {"id": "op-cura", "order_id": "4272", "phase_id": "Cura"},
            {"id": "op-outra", "order_id": "9001", "phase_id": "Montagem"},
        ],
    }


@pytest.mark.asyncio
async def test_resolve_by_order_id_picks_operation_at_current_phase(fake_session):
    """`order_id` → escolhe a operação da fase ACTUAL da ordem."""
    fake_session.queue_scalar(_order("Cura"))  # _load_order

    svc = PreviewDeltaService(fake_session, TENANT)
    op_id = await svc._resolve_operation_id(
        _schedule(), PreviewMutation(order_id="4272")
    )

    assert op_id == "op-cura"


@pytest.mark.asyncio
async def test_resolve_by_order_id_falls_back_to_first_op_without_order(
    fake_session,
):
    """Ordem não carregável → degrada para a 1ª operação da OF, não rebenta."""
    fake_session.queue_scalar(None)  # _load_order não encontra a ordem

    svc = PreviewDeltaService(fake_session, TENANT)
    op_id = await svc._resolve_operation_id(
        _schedule(), PreviewMutation(order_id="4272")
    )

    assert op_id == "op-lam"  # primeira operação da OF 4272


@pytest.mark.asyncio
async def test_resolve_by_order_id_unknown_order_raises(fake_session):
    """OF que não está no commit → erro explícito (o operador vê porquê)."""
    svc = PreviewDeltaService(fake_session, TENANT)
    with pytest.raises(ValueError, match="não está no plano"):
        await svc._resolve_operation_id(
            _schedule(), PreviewMutation(order_id="5555")
        )


@pytest.mark.asyncio
async def test_resolve_by_explicit_operation_id_still_works(fake_session):
    """Retro-compat: `operation_id` directo presente no commit → devolve-o."""
    svc = PreviewDeltaService(fake_session, TENANT)
    op_id = await svc._resolve_operation_id(
        _schedule(), PreviewMutation(operation_id="op-cura")
    )

    assert op_id == "op-cura"


@pytest.mark.asyncio
async def test_resolve_by_explicit_operation_id_absent_raises(fake_session):
    svc = PreviewDeltaService(fake_session, TENANT)
    with pytest.raises(ValueError, match="not in latest commit"):
        await svc._resolve_operation_id(
            _schedule(), PreviewMutation(operation_id="op-fantasma")
        )


@pytest.mark.asyncio
async def test_resolve_requires_a_target(fake_session):
    """Sem operation_id nem order_id → erro (não adivinha)."""
    svc = PreviewDeltaService(fake_session, TENANT)
    with pytest.raises(ValueError, match="operation_id ou order_id"):
        await svc._resolve_operation_id(_schedule(), PreviewMutation())


# ── Schema da API ────────────────────────────────────────────────────────


def test_preview_delta_in_requires_a_target():
    from pydantic import ValidationError
    from src.plan.api.schedule_preview import PreviewDeltaIn

    with pytest.raises(ValidationError):
        PreviewDeltaIn(new_phase_id="Cura")

    # order_id sozinho é suficiente.
    body = PreviewDeltaIn(order_id="4272", new_phase_id="Cura")
    assert body.order_id == "4272"
    assert body.operation_id is None


def test_apply_move_in_requires_a_target_and_reason():
    from pydantic import ValidationError
    from src.plan.api.schedule_preview import ApplyMoveIn

    with pytest.raises(ValidationError):
        ApplyMoveIn(reason="movimento manual do operador")

    body = ApplyMoveIn(order_id="4272", reason="movimento manual do operador")
    assert body.order_id == "4272"
