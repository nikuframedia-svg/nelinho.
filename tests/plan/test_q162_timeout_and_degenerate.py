"""Q.162 — invariantes do fix "pôr o nelinho a PLANEAR (não espelhar o ERP)".

O grid ficava preso num plano degenerado de 2 ops porque o job do robô estourava
o timeout do Arq e NUNCA gravava: o budget do solver (`time_limit_sec=600`) era
IGUAL ao `job_timeout=600` do worker → o solve comia tudo, sobrava zero para
load+serialização+persist, o Arq matava o job antes do commit (j_failed=22).

Estes testes blindam os dois invariantes do fix:
  1. `job_timeout` >> budget do solver do robô (com folga real para o persist).
  2. guarda anti-plano-degenerado (scope grande + cobertura colapsada).
"""
from __future__ import annotations

import pytest

from src.plan.api.cpo_routers.schedule import _MAX_TIME_LIMIT_S
from src.plan.cpo.scheduler_run import (
    _DEGENERATE_COVERAGE_FLOOR,
    _DEGENERATE_MIN_SCOPE,
    _is_degenerate_plan,
)
from src.plan.cpo.worker import WorkerSettings
from src.scheduling.jobs.auto_cpo_replan_job import _DEFAULT_ROBOT_TIME_LIMIT_S


# ── Invariante 1: job_timeout >> budget do solver ───────────────────────────

def test_job_timeout_exceeds_robot_solver_budget_with_margin():
    """O wall-clock do Arq tem de exceder o budget do solver do robô com folga
    para load (~4s) + serialização de ~8k ops + trust_index + boost + reapply.
    Exigimos pelo menos +50% de margem (o bug era job_timeout == time_limit)."""
    assert WorkerSettings.job_timeout > _DEFAULT_ROBOT_TIME_LIMIT_S, (
        f"REGRESSÃO Q.161.B: job_timeout ({WorkerSettings.job_timeout}) <= "
        f"budget do solver do robô ({_DEFAULT_ROBOT_TIME_LIMIT_S}) → o job é "
        "morto antes de gravar o commit."
    )
    assert WorkerSettings.job_timeout >= _DEFAULT_ROBOT_TIME_LIMIT_S * 1.5, (
        "job_timeout precisa de >=50% de folga sobre o solver para o persist."
    )


def test_robot_solver_budget_within_request_cap():
    """O budget do robô não pode passar o tecto do CPOScheduleRequest, senão é
    silenciosamente clampado (e voltava a colar-se ao antigo 600=600)."""
    assert _DEFAULT_ROBOT_TIME_LIMIT_S <= _MAX_TIME_LIMIT_S
    # E tem de deixar folga sob o job_timeout mesmo no tecto.
    assert _MAX_TIME_LIMIT_S < WorkerSettings.job_timeout


# ── Invariante 2: guarda anti-plano-degenerado ──────────────────────────────

def test_degenerate_when_big_scope_and_low_coverage():
    """Scope grande (1222) + cobertura colapsada (2/1222) → degenerado."""
    assert _is_degenerate_plan(1222, 0.0016) is True


def test_not_degenerate_for_healthy_plan():
    """O plano saudável medido live (cobertura 0.87, scope 1222) NÃO é flagged."""
    assert _is_degenerate_plan(1222, 0.8707) is False


def test_not_degenerate_for_small_intentional_scope():
    """Scope pequeno (request com `orders` explícito) nunca é degenerado, mesmo
    com cobertura baixa — não há baseline de scope para comparar."""
    assert _is_degenerate_plan(_DEGENERATE_MIN_SCOPE - 1, 0.0) is False


def test_degenerate_boundary_uses_constants():
    """A fronteira é exatamente (scope >= MIN) E (coverage < FLOOR)."""
    # No mínimo de scope, cobertura logo abaixo do floor → degenerado.
    assert _is_degenerate_plan(_DEGENERATE_MIN_SCOPE, _DEGENERATE_COVERAGE_FLOOR - 0.01) is True
    # Mesma scope, cobertura no floor → saudável (não estritamente abaixo).
    assert _is_degenerate_plan(_DEGENERATE_MIN_SCOPE, _DEGENERATE_COVERAGE_FLOOR) is False
