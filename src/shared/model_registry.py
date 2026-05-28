"""Q.61.14 — Single source of truth para imports de modelos SQLAlchemy.

Antes de Q.61.14, a lista de modelos viva em DOIS sitios divergentes:

  * `alembic/env.py:17-43` — 22 imports
  * `scripts/bootstrap_dev_full.py:30-77` — 28 imports

Resultado pratico: 12 modulos com classes `Base` que o bootstrap
conhecia mas o env.py NAO. Producao via `alembic upgrade head` deixava
tabelas orfas; `bootstrap_dev_full.py` corrigia silenciosamente em
dev (criava as tabelas via `create_all`). Discrepancia que so se
notava quando o schema produccao divergia em produzir.

Q.61.14 consolida tudo aqui. Alembic env.py + bootstrap + tests
(quando precisarem) importam UMA linha:

    from src.shared import model_registry  # noqa: F401

Para adicionar um novo modelo:
  1. Cria o ficheiro `src/<dominio>/models/<algo>.py` com a class.
  2. Adiciona-o aqui, na seccao correcta.
  3. `alembic revision --autogenerate` apanha-o.

Convencao de ordem: alfabetica por modulo top-level (core, copilot,
dqa, ...), depois por sub-ficheiro. Excepcao: `core/models/tenant.py`
vem primeiro (e o ancoragem de FK para muitos outros).
"""
# Os imports abaixo sao side-effect (registam classes em Base.metadata
# via decoradores SQLAlchemy). F401 (unused import) ja esta em ignore
# no ruff config principal.

# ─── core ───────────────────────────────────────────────────────────────
from src.core.models import (
    agent_action,  # Q.66.E.3 — observability do copiloto
    audit,
    bom,
    client_priority,        # Q.115.A.03
    daily_revenue_target,   # Q.115.A.02
    employee,
    etl_run,
    machine,
    operation,
    product,
    rates,
    tenant,
    tenant_configuration,
    user_input,             # Q.115.A.01
)

# ─── copilot ────────────────────────────────────────────────────────────
from src.copilot import models as _copilot_models
from src.copilot.alerts import models as _copilot_alerts_models

# ─── dqa ────────────────────────────────────────────────────────────────
from src.dqa import models as _dqa_models

# ─── explain ────────────────────────────────────────────────────────────
from src.explain.models import explained_value as _explain_explained_value

# ─── factory_data_product ──────────────────────────────────────────────
from src.factory_data_product.models import curated as _fdp_curated
from src.factory_data_product.models import meta as _fdp_meta
from src.factory_data_product.models import raw as _fdp_raw

# ─── governance ────────────────────────────────────────────────────────
# Active Q.13+ models (decision_run, preference_rule, rule_firing, ...)
from src.governance import models as _governance_main
# Q.17.C: tenant_rule + revision tables (YAML rule authoring)
from src.governance.yaml_policy import models as _governance_yaml_policy
# Q.115.A.04 — afinidade operador/fase
from src.governance.models import phase_operator_affinity as _governance_phase_affinity

# ─── hr ─────────────────────────────────────────────────────────────────
from src.hr.models import allocation as _hr_allocation
from src.hr.models import legacy_allocation as _hr_legacy_allocation
from src.hr.models import productivity as _hr_productivity
from src.hr.models import worker_phase_assignment as _hr_worker_phase_assignment  # Q.115.A.09

# ─── improve ───────────────────────────────────────────────────────────
from src.improve import models as _improve_models

# ─── (Q.61.32d) legacy/ removido; ProductionError migrou para quality/.

# ─── ml ────────────────────────────────────────────────────────────────
from src.ml.models import drift_event as _ml_drift_event  # Q.115.A.10
from src.ml.models import orm as _ml_orm

# ─── plan ──────────────────────────────────────────────────────────────
from src.plan.cpo import commits as _plan_commits
from src.plan.models import fases_of_history as _plan_fases_of_history  # Q.115.A.08
from src.plan.models import mold as _plan_mold
from src.plan.models import mrp as _plan_mrp
from src.plan.models import order as _plan_order
from src.plan.models import phase_gap as _plan_phase_gap
from src.plan.models import routing_template as _plan_routing_template
from src.plan.models import schedule as _plan_schedule
from src.plan.models import transport as _plan_transport

# ─── profit ────────────────────────────────────────────────────────────
from src.profit.models import cost as _profit_cost
from src.profit.models import phase_bonus as _profit_phase_bonus
from src.profit.models import pricing as _profit_pricing

# ─── quality ───────────────────────────────────────────────────────────
from src.quality.models import production_error as _quality_production_error  # Q.61.32d
from src.quality.models import rework as _quality_rework
from src.quality.models import runbook as _quality_runbook  # Q.115.A.05+A.06

# ─── reports ───────────────────────────────────────────────────────────
# Q.22.D: report_schedule + report_run
from src.reports import models as _reports_models

# ─── sandbox ───────────────────────────────────────────────────────────
from src.sandbox import models as _sandbox_models

# ─── shared ────────────────────────────────────────────────────────────
# Decision ledger (SharedDecisionRun, DecisionApproval)
from src.shared.models import governance as _shared_governance
# Q.22.A: shared.users (backs GET /v1/auth/me)
from src.shared.models import user as _shared_user
# Outbox + DLQ (Q.61.11 — async event delivery)
from src.shared import outbox_models as _shared_outbox

# ─── supply ────────────────────────────────────────────────────────────
from src.supply import models as _supply_models

# ─── twin ──────────────────────────────────────────────────────────────
from src.twin import models as _twin_models

# ─── workforce ─────────────────────────────────────────────────────────
from src.workforce import models as _workforce_models


__all__: list[str] = []  # importacoes sao side-effect; nada para re-exportar
