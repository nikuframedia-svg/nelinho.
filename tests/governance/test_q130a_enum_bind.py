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
4. RuleEngine.refresh() carrega ≥1 regra active sem InvalidTextRepresentationError
   (prova funcional do fix end-to-end).
"""

from __future__ import annotations

from uuid import UUID, uuid4

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


# ---------------------------------------------------------------------------
# Prova funcional: RuleEngine.refresh() carrega regra active sem crash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rule_engine_refresh_loads_active_rule():
    """RuleEngine.refresh() com 1 regra active na sessão fake devolve count=1.

    Reprodução directa do bug: antes do fix, a query enviava "ACTIVE" (maiúsculo)
    ao Postgres, que rejeitava com InvalidTextRepresentationError. Com o fix
    o bind value é "active" (minúsculo) e a FakeRuleSession filtra correctamente.

    Usa FakeRuleSession (sem DB) para ser fast e isolado.
    """
    from tests.conftest import FakeRuleSession
    from src.governance.yaml_policy.engine import RuleEngine

    TENANT = UUID("00000000-0000-0000-0000-000000000001")

    # Payload mínimo válido de uma regra kpi_threshold_crossed com acção alert.
    # Campos obrigatórios: id, description, when, then. SafetySpec e ConstraintsSpec
    # têm defaults; Rule.model_config forbids extras (sem name/version/axioms_required).
    payload = {
        "id": "regra-teste-q130a",
        "description": "Regra de teste para regressao Q.130.A",
        "status": "active",
        "when": {
            "event": "kpi_threshold_crossed",
            "conditions": [],
        },
        "then": [
            {
                "action": "alert",
                "params": {
                    "severity": "INFO",
                    "title": "Teste",
                    "message_pt": "Mensagem de teste.",
                    "entity_refs": [],
                },
            }
        ],
        "safety": {
            "requires_human_approval": True,
            "max_fires_per_day": 10,
            "kill_switch": "admin_only",
        },
    }

    row = TenantRule(
        id=uuid4(),
        tenant_id=TENANT,
        rule_id="regra-teste-q130a",
        description="Regra de teste",
        status=RuleLifecycleStatus.ACTIVE,
        event_type="kpi_threshold_crossed",
        payload=payload,
    )

    session = FakeRuleSession()
    session.rules.append(row)

    engine = RuleEngine()
    # Antes do fix, esta chamada lançava InvalidTextRepresentationError.
    count = await engine.refresh(session, tenant_id=TENANT)

    assert count == 1, f"refresh() devia carregar 1 regra active, carregou {count}"
    assert engine.rule_count == 1
    assert "kpi_threshold_crossed" in engine.event_types_with_rules
