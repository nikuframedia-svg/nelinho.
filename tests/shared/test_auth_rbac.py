"""Tests for src/shared/auth/rbac.py — SoD + permission checks (S1)."""
from __future__ import annotations

from uuid import UUID

import pytest

from src.shared.auth.rbac import (
    Permission,
    Role,
    check_sod,
    has_all_permissions,
    has_any_permission,
    has_permission,
)


PROPOSER = UUID("00000000-0000-0000-0000-000000000001")
APPROVER = UUID("00000000-0000-0000-0000-000000000002")


# --- has_permission -----------------------------------------------------------

def test_admin_has_every_permission():
    for perm in Permission:
        assert has_permission(Role.ADMIN_PLATFORM.value, perm)


def test_operator_lacks_master_data_write():
    assert has_permission(Role.OPERATOR.value, Permission.SCHEDULE_READ)
    assert not has_permission(Role.OPERATOR.value, Permission.MASTER_DATA_WRITE)


def test_unknown_role_has_no_permission():
    assert not has_permission("unknown_role", Permission.SCHEDULE_READ)


def test_routing_edit_open_to_all_roles_q133():
    """Q.133.B.1 — editar fases de routing (reordenar + flexível) está aberto a
    QUALQUER role (decisão do owner), incluindo CEO e Operador. MAS é uma
    permissão DEDICADA: CEO/Operador continuam SEM SCHEDULE_WRITE, logo NÃO
    acedem a /v1/plan/cpo, /v1/governance nem /v1/decisions — o SoD do
    write-gate fica intacto."""
    for role in (
        Role.MANAGER_OPERATIONS,
        Role.PLANNER_SUPPLY,
        Role.FINANCE_CONTROLLER,
        Role.HR_MANAGER,
        Role.OPERATOR,
        Role.CEO,
        Role.VIEWER,
        Role.ADMIN_PLATFORM,
    ):
        assert has_permission(role.value, Permission.ROUTING_EDIT), role
    # Invariante preservado: routing aberto NÃO destranca o plano/CPO.
    assert not has_permission(Role.CEO.value, Permission.SCHEDULE_WRITE)
    assert not has_permission(Role.OPERATOR.value, Permission.SCHEDULE_WRITE)


def test_has_any_permission():
    assert has_any_permission(
        Role.OPERATOR.value,
        [Permission.MASTER_DATA_WRITE, Permission.SCHEDULE_READ],
    )
    assert not has_any_permission(
        Role.OPERATOR.value,
        [Permission.MASTER_DATA_WRITE, Permission.PRICING_WRITE],
    )


def test_has_all_permissions():
    assert has_all_permissions(
        Role.MANAGER_OPERATIONS.value,
        [Permission.MASTER_DATA_READ, Permission.SCHEDULE_WRITE],
    )
    assert not has_all_permissions(
        Role.MANAGER_OPERATIONS.value,
        [Permission.MASTER_DATA_READ, Permission.PAYROLL_WRITE],
    )


# --- check_sod ----------------------------------------------------------------

def test_self_approval_blocked():
    ok, err = check_sod(
        action_type="ADJUST_PRICE",
        proposer_id=PROPOSER,
        proposer_role=Role.FINANCE_CONTROLLER,
        approver_id=PROPOSER,
        approver_role=Role.FINANCE_CONTROLLER,
    )
    assert ok is False
    assert err is not None and "Cannot approve own decision" in err


def test_approver_with_required_role_passes():
    ok, err = check_sod(
        action_type="ADJUST_PRICE",
        proposer_id=PROPOSER,
        proposer_role=Role.OPERATOR,
        approver_id=APPROVER,
        approver_role=Role.FINANCE_CONTROLLER,
    )
    assert ok is True
    assert err is None


def test_approver_with_wrong_role_blocked():
    ok, err = check_sod(
        action_type="INCREASE_PRICE",  # only FINANCE_CONTROLLER may approve
        proposer_id=PROPOSER,
        proposer_role=Role.OPERATOR,
        approver_id=APPROVER,
        approver_role=Role.OPERATOR,
    )
    assert ok is False
    assert err is not None and "not authorized" in err


def test_unknown_action_uses_generic_policy():
    # GENERIC_ACTION accepts MANAGER_OPERATIONS or FINANCE_CONTROLLER.
    ok, _ = check_sod(
        action_type="SOMETHING_NEW",
        proposer_id=PROPOSER,
        proposer_role=Role.OPERATOR,
        approver_id=APPROVER,
        approver_role=Role.MANAGER_OPERATIONS,
    )
    assert ok is True

    ok, err = check_sod(
        action_type="SOMETHING_NEW",
        proposer_id=PROPOSER,
        proposer_role=Role.OPERATOR,
        approver_id=APPROVER,
        approver_role=Role.OPERATOR,
    )
    assert ok is False
    assert err is not None
