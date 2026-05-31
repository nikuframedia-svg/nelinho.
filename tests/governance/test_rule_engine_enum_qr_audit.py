"""Q.R-audit — regressão do bug de enum no motor de regras (Q.17).

§5 da auditoria 2026-05-30: `SQLEnum(RuleLifecycleStatus, ...)` sem
`values_callable` fazia o SQLAlchemy ligar o NOME do membro ("ACTIVE"),
que o enum Postgres minúsculo (`yaml_policy_rule_status`) rejeita →
`RuleEngine.refresh()` rebentava no arranque e carregava 0 regras. Os unit
tests existentes não apanhavam porque usam `FakeRuleSession` (nunca tocam
Postgres). Aqui ficam:

  1. um pin sem DB que afirma que a coluna liga pelo `.value` (minúsculo);
  2. um teste de integração que insere 1 regra `active` e corre
     `RuleEngine.refresh()` contra Postgres real (rebentaria antes do fix).
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from src.governance.yaml_policy.models import (
    RuleLifecycleStatus,
    RuleRevisionAction,
    TenantRule,
    TenantRuleRevision,
)


# ─── 1. Pins sem DB — o tipo da coluna liga pelo .value (minúsculo) ───


def test_status_column_binds_lowercase_value():
    coltype = TenantRule.__table__.c.status.type
    assert coltype.values_callable is not None, (
        "values_callable em falta → SQLAlchemy liga o NOME (ACTIVE) e o enum "
        "Postgres yaml_policy_rule_status rejeita-o"
    )
    assert list(coltype.enums) == [m.value for m in RuleLifecycleStatus]
    assert "active" in coltype.enums and "ACTIVE" not in coltype.enums


def test_revision_action_column_binds_lowercase_value():
    coltype = TenantRuleRevision.__table__.c.action.type
    assert coltype.values_callable is not None
    assert list(coltype.enums) == [m.value for m in RuleRevisionAction]


# ─── 2. Integração — insere 1 regra active e refresh() não rebenta ────


def _build_active_rule(rule_id: str):
    """Constrói um Rule válido (mesmo shape de _build_rule em test_yaml_engine_q17d)."""
    from src.governance.yaml_policy.rule_schema import Rule

    return Rule.model_validate(
        {
            "id": rule_id,
            "description": "Q.R-audit smoke rule",
            "when": {
                "event": "mold_usage_threshold",
                "conditions": [{"field": "uses_count", "op": "gte", "value": 800}],
            },
            "then": [
                {
                    "action": "alert",
                    "params": {
                        "severity": "high",
                        "title": "x",
                        "message_pt": "y",
                        "entity_refs": [],
                    },
                }
            ],
        }
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rule_engine_refresh_loads_active_rule_against_real_db():
    from src.governance.yaml_policy.engine import RuleEngine
    from src.shared.auth.tenant_context import tenant_scope
    from src.shared.database import async_session_factory

    tenant_id = UUID("0a0a0a0a-0000-4000-8000-00000000a17d")
    rule = _build_active_rule(f"qr-audit-{uuid4().hex[:8]}")
    row_id = uuid4()

    with tenant_scope(tenant_id):
        async with async_session_factory() as session:
            try:
                session.add(
                    TenantRule(
                        id=row_id,
                        tenant_id=tenant_id,
                        rule_id=rule.id,
                        description=rule.description,
                        status=RuleLifecycleStatus.ACTIVE,
                        event_type=rule.when.event.value,
                        payload=rule.model_dump(mode="json", exclude_none=True),
                    )
                )
                await session.commit()

                # Prova directa do fix: o valor persistido é minúsculo.
                persisted = (
                    await session.execute(
                        text(
                            "SELECT status::text FROM governance.yaml_policy_rule "
                            "WHERE id = :id"
                        ),
                        {"id": row_id},
                    )
                ).scalar_one()
                assert persisted == "active"

                # O bug original rebentava AQUI (bind 'ACTIVE' no SELECT do enum).
                engine = RuleEngine()
                count = await engine.refresh(session, tenant_id=tenant_id)
                assert count >= 1
                assert engine.rule_count >= 1
            finally:
                await session.rollback()
                await session.execute(
                    text("DELETE FROM governance.yaml_policy_rule WHERE id = :id"),
                    {"id": row_id},
                )
                await session.commit()
