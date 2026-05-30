"""Q.130.A — Regressão: SQLEnum de status/action usa .value (minúsculo).

Causa-raiz: sem `native_enum=False`, o SQLAlchemy usava `.name` ("ACTIVE")
como bind value em vez de `.value` ("active"), causando
InvalidTextRepresentationError contra o enum Postgres criado em minúsculo
pela migration 028a.

Estes testes verificam que:
1. O tipo da coluna `status` de TenantRule processa `RuleLifecycleStatus.ACTIVE`
   e produz o bind value "active" (minúsculo).
2. O tipo da coluna `action` de TenantRuleRevision processa
   `RuleRevisionAction.APPROVED` e produz o bind value "approved" (minúsculo).
3. Todos os membros de ambos os enums têm .name != .value (confirma que o bug
   seria real sem o fix).
"""

from __future__ import annotations

import pytest

from src.governance.yaml_policy.models import (
    RuleLifecycleStatus,
    RuleRevisionAction,
    TenantRule,
    TenantRuleRevision,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_column_type(mapper_class, col_name: str):
    """Devolve o TypeEngine da coluna pelo nome."""
    return mapper_class.__table__.c[col_name].type


# ---------------------------------------------------------------------------
# Prova que .name != .value (sem fix, o bug seria real)
# ---------------------------------------------------------------------------

def test_status_enum_name_differs_from_value():
    """Cada membro tem .name maiúsculo e .value minúsculo — confirma que
    enviar .name causaria InvalidTextRepresentationError."""
    for member in RuleLifecycleStatus:
        assert member.name != member.value, (
            f"RuleLifecycleStatus.{member.name}: name == value, bug não seria reproduzível"
        )


def test_revision_action_enum_name_differs_from_value():
    for member in RuleRevisionAction:
        assert member.name != member.value, (
            f"RuleRevisionAction.{member.name}: name == value"
        )


# ---------------------------------------------------------------------------
# Verifica que native_enum=False está activo (SQLAlchemy usa VARCHAR/values)
# ---------------------------------------------------------------------------

def test_tenant_rule_status_col_is_not_native_enum():
    """Com native_enum=False o tipo não é PGEnum nativo — usa VARCHAR internamente."""
    col_type = _get_column_type(TenantRule, "status")
    # native_enum=False faz create_constraint=False; o atributo é acessível.
    assert col_type.native_enum is False, (
        "TenantRule.status deve ter native_enum=False para enviar .value ao Postgres"
    )


def test_tenant_rule_revision_action_col_is_not_native_enum():
    col_type = _get_column_type(TenantRuleRevision, "action")
    assert col_type.native_enum is False, (
        "TenantRuleRevision.action deve ter native_enum=False"
    )


# ---------------------------------------------------------------------------
# Verifica que o bind value é .value e não .name
# ---------------------------------------------------------------------------

def test_status_bind_value_is_lowercase():
    """O col_type.enums lista os .value strings (minúsculo) e não os .name."""
    col_type = _get_column_type(TenantRule, "status")
    # Com native_enum=False + values_callable, col_type.enums contém .value
    # strings em minúsculo — é o que o SQLAlchemy usa como bind value.
    for member in RuleLifecycleStatus:
        assert member.value in col_type.enums, (
            f"'{member.value}' não está em col_type.enums — values_callable incorrecto"
        )
        assert member.name not in col_type.enums, (
            f"'{member.name}' (maiúsculo) não deve estar em col_type.enums"
        )


def test_action_bind_value_is_lowercase():
    col_type = _get_column_type(TenantRuleRevision, "action")
    for member in RuleRevisionAction:
        assert member.value in col_type.enums, (
            f"'{member.value}' não está em col_type.enums"
        )
        assert member.name not in col_type.enums, (
            f"'{member.name}' (maiúsculo) não deve estar em col_type.enums"
        )
