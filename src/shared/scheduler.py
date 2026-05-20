"""Q.66.A.4 — shim de backwards-compat após decomposição.

O conteúdo real vive em `src/scheduling/` (core + jobs por domínio).
Este shim re-exporta tudo para que os call-sites existentes (main.py
lifespan, 3 testes Q.25.D/Q.54.A/Q.61.35-adjacentes, docs) não tenham
de mudar.

Particularidade: os testes Q.25.D e Q.54.A fazem
``scheduler._scheduler = None`` e ``scheduler.start_scheduler(...)``
em sequência para garantir arranque limpo. Como `start_scheduler` vive
em `src.scheduling.core` e usa ``global _scheduler`` no namespace de
`core`, um simples `_scheduler = None` neste módulo não chegaria à
variável real. A classe ``_SchedulerShim`` abaixo intercepta escritas
e leituras dos atributos que partilham estado com `core` e proxy-as
para o módulo certo, mantendo a semântica dos testes intacta.

Próximo sprint pode actualizar call-sites para importar directamente
de `src.scheduling.*` e remover este shim.
"""

from __future__ import annotations

import sys
from types import ModuleType

from src.scheduling import core as _core
from src.scheduling.jobs import alerts as _alerts
from src.scheduling.jobs import audit as _audit
from src.scheduling.jobs import causal as _causal
from src.scheduling.jobs import feedback as _feedback
from src.scheduling.jobs import improve as _improve
from src.scheduling.jobs import ml as _ml
from src.scheduling.jobs import nelo_erp as _nelo_erp
from src.scheduling.jobs import order_reconciliation as _order_rec
from src.scheduling.jobs import preference_learning as _pref
from src.scheduling.jobs import supply as _supply

# ── Re-exports estáticos (funções) ──────────────────────────────────
# Estes são bind-once: não mudam em runtime e podem ser importados
# directamente via `from src.shared.scheduler import start_scheduler`.

# core
get_scheduler = _core.get_scheduler
start_scheduler = _core.start_scheduler
register_tenant = _core.register_tenant
shutdown_scheduler = _core.shutdown_scheduler
APSCHEDULER_AVAILABLE = _core.APSCHEDULER_AVAILABLE

# jobs (prefix `_` preserva o contrato anterior — privados-por-convenção)
_alerts_scan_job = _alerts._alerts_scan_job
_audit_retention_purge_job = _audit._audit_retention_purge_job
_causal_discovery_job = _causal._causal_discovery_job
_daily_feedback_job = _feedback._daily_feedback_job
_abl_feedback_job = _improve._abl_feedback_job
_improve_adoption_signal_job = _improve._improve_adoption_signal_job
_mold_health_scan_job = _ml._mold_health_scan_job
_multivariate_drift_job = _ml._multivariate_drift_job
_quality_risk_scoring_job = _ml._quality_risk_scoring_job
_nelo_erp_incremental_sync_job = _nelo_erp._nelo_erp_incremental_sync_job
_nelo_erp_sync_job = _nelo_erp._nelo_erp_sync_job
_nelo_erp_time_mining_job = _nelo_erp._nelo_erp_time_mining_job
_order_status_reconcile_job = _order_rec._order_status_reconcile_job
_reconcile_order_statuses_all_tenants = (
    _order_rec._reconcile_order_statuses_all_tenants
)
_dpo_finetune_job = _pref._dpo_finetune_job
_preference_rule_detector_job = _pref._preference_rule_detector_job
_preference_weights_retrain_job = _pref._preference_weights_retrain_job
_shortage_scan_job = _supply._shortage_scan_job


# ── Proxy de estado mutável ─────────────────────────────────────────
# Os testes Q.25.D / Q.54.A fazem ``scheduler._scheduler = None`` para
# isolar o arranque entre testes. A real `_scheduler` (singleton)
# vive em `src.scheduling.core`. Subclassificamos `ModuleType` e
# trocamos `sys.modules[__name__].__class__` para interceptar tanto
# leituras (`scheduler._scheduler`) como escritas (`scheduler._scheduler = X`)
# e redireccioná-las para `_core`.
#
# A mesma técnica cobre `_INCREMENTAL_MIRRORS` (lido pelos testes via
# `scheduler._INCREMENTAL_MIRRORS`) e qualquer atributo futuro que
# precise de ficar sincronizado com a fonte real.

_PROXIED_FROM_CORE = {"_scheduler"}
_PROXIED_FROM_NELO_ERP = {"_INCREMENTAL_MIRRORS"}


class _SchedulerShim(ModuleType):
    def __getattr__(self, name: str):
        if name in _PROXIED_FROM_CORE:
            return getattr(_core, name)
        if name in _PROXIED_FROM_NELO_ERP:
            return getattr(_nelo_erp, name)
        raise AttributeError(name)

    def __setattr__(self, name: str, value) -> None:
        if name in _PROXIED_FROM_CORE:
            setattr(_core, name, value)
            return
        if name in _PROXIED_FROM_NELO_ERP:
            setattr(_nelo_erp, name, value)
            return
        super().__setattr__(name, value)


sys.modules[__name__].__class__ = _SchedulerShim


__all__ = [
    "APSCHEDULER_AVAILABLE",
    "get_scheduler",
    "register_tenant",
    "shutdown_scheduler",
    "start_scheduler",
    "_abl_feedback_job",
    "_alerts_scan_job",
    "_audit_retention_purge_job",
    "_causal_discovery_job",
    "_daily_feedback_job",
    "_dpo_finetune_job",
    "_improve_adoption_signal_job",
    "_mold_health_scan_job",
    "_multivariate_drift_job",
    "_nelo_erp_incremental_sync_job",
    "_nelo_erp_sync_job",
    "_nelo_erp_time_mining_job",
    "_order_status_reconcile_job",
    "_preference_rule_detector_job",
    "_preference_weights_retrain_job",
    "_quality_risk_scoring_job",
    "_reconcile_order_statuses_all_tenants",
    "_shortage_scan_job",
    # NOTE: `_scheduler` e `_INCREMENTAL_MIRRORS` são proxied via
    # `_SchedulerShim.__getattr__/__setattr__` (não estão em `__all__`
    # porque ruff F822 reclama de nomes não definidos no namespace
    # estático — mas continuam acessíveis via `scheduler._scheduler`
    # exactamente como antes).
]
