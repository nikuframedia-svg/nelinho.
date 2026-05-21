"""Q.61.14 — single source of truth para imports de modelos.

`src/shared/model_registry.py` substitui as listas divergentes que
viviam em `alembic/env.py` + `scripts/bootstrap_dev_full.py`. Estes
testes pinam:

  * O registry importa sem erros (todos os modulos existem).
  * Apos importar o registry, `Base.metadata.tables` tem pelo menos
    `MIN_TABLES` entries (floor anti-regressao — se alguem apagar um
    import por engano, este teste falha).
  * Tabelas que viviam SO no bootstrap (env.py orfas) estao no
    registry — sao precisamente as que producao via `alembic upgrade
    head` deixava por criar.
"""

from __future__ import annotations


# Floor anti-regressao. 105 era o numero apos Q.61.14 (env.py original
# tinha 84 -> registry tem 105 = 21 tabelas que producao deixava orfas).
# Se este floor cair, alguem apagou um modelo ou um import e nao deveria.
MIN_TABLES = 100


def test_model_registry_imports_cleanly():
    """Smoke: registry corre todos os imports sem ImportError."""
    from src.shared import model_registry


def test_registry_registers_at_least_min_tables():
    """Floor de tabelas registadas. Se cair, alguem partiu o registry."""
    from src.shared import model_registry
    from src.shared.database import Base

    tables = Base.metadata.tables
    assert len(tables) >= MIN_TABLES, (
        f"so {len(tables)} tabelas registadas (floor: {MIN_TABLES}). "
        f"Alguem apagou imports do model_registry.py? Verifica o diff."
    )


def test_registry_includes_tables_that_were_orphans_pre_q61_14():
    """As tabelas que eram orfas no alembic/env.py antes do Q.61.14
    DEVEM estar no registry. Apanha regressao se alguem reverte.
    """
    from src.shared import model_registry
    from src.shared.database import Base

    table_names = set(Base.metadata.tables.keys())

    # Exemplos representativos dos 21 modulos que env.py original nao
    # importava mas bootstrap importava. Lista deliberadamente curta
    # para que o teste leia rapido — se um destes desaparece, e bandeira
    # vermelha mesmo sem ler todos os 21.
    expected_present = {
        # Q.61.10 deu o primeiro consumidor real ao AuditLog.
        "core.audit_log": "core/models/audit.py",
        # Q.61.11 ligou o outbox ao governance.propose.
        "event_outbox": "shared/outbox_models.py",
        # hr: 3 ficheiros (allocation/legacy_allocation/productivity)
        # que viviam so no bootstrap (env.py original esquecia-os).
        "hr.hr_allocations": "hr/models/allocation.py",
        "hr.legacy_allocations": "hr/models/legacy_allocation.py",
        # profit: phase_bonus + cost (env.py so tinha pricing).
        "profit.phase_bonus_payout": "profit/models/phase_bonus.py",
        # governance.yaml_policy (Q.17.C) — orfa.
        "governance.yaml_policy_rule": "governance/yaml_policy/models.py",
        # legacy errors table (Q.22.C).
        "plan.production_errors": "legacy/models.py",
    }

    missing = {
        name: source for name, source in expected_present.items()
        if name not in table_names
    }
    assert not missing, (
        "Tabelas pre-Q.61.14-orfas em falta no registry: "
        f"{missing!r}. Repor o(s) import(s) em model_registry.py."
    )
