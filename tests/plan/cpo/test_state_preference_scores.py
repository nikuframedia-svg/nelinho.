"""Q.140.F — preferência por sector → fase no FactoryState (p/ o CPO).

`SectorPreferenceService.phase_preference_map` produz {(employee_code,
fase_id): [0,1]} a partir do nível por sector (override > derivado > semente),
resolvendo o gap UUID↔employee_code. `FactoryState.preference_score_for` é o
lookup puro que o decoder usa. O loader é best-effort (session None → {}).
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.plan.cpo.state import FactoryState, _load_sector_preferences_db
from src.workforce.sector_preference_service import (
    SectorPreferenceService,
    _PhaseStat,
)

_TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _stat(fase_id, fase_nome, ops, defects):
    return _PhaseStat(
        fase_id=fase_id, fase_nome=fase_nome, ops=ops, defects=defects,
        last_fim=datetime(2026, 5, 1),
    )


def _service(history, dim, *, overrides=None, erp=None):
    svc = SectorPreferenceService(session=None, tenant_id=_TENANT)  # type: ignore[arg-type]

    async def _hist(employee_code=None):
        return history

    async def _erp():
        return erp or {}

    async def _ov():
        return overrides or {}

    async def _dim(codes=None):
        return dim

    svc._fetch_phase_history = _hist     # type: ignore[assignment]
    svc._fetch_erp_levels = _erp         # type: ignore[assignment]
    svc._fetch_overrides = _ov           # type: ignore[assignment]
    svc._fetch_employee_dim = _dim       # type: ignore[assignment]
    return svc


_UID = uuid4()


# ─────────────────────────────────────────────────────────────────────────
# phase_preference_map — chave employee_code, valor [0,1]
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_map_keyed_by_employee_code_not_uuid():
    history = {"27641": [_stat("5", "Pintura Acabamento", ops=300, defects=0)]}
    dim = {"27641": (_UID, "Hugo")}
    svc = _service(history, dim)

    m = await svc.phase_preference_map()

    # Chave é (employee_code, fase_id) — NÃO o UUID.
    assert ("27641", "5") in m
    assert all(isinstance(k[0], str) and k[0] == "27641" for k in m)
    # 300 ops limpas → derived 3.0 → score 3.0/3.0 = 1.0.
    assert m[("27641", "5")] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_override_changes_the_score():
    history = {"27641": [_stat("5", "Pintura Acabamento", ops=300, defects=0)]}
    dim = {"27641": (_UID, "Hugo")}
    overrides = {(str(_UID), "Pintura"): 1.5}  # manual: 1.5 → 0.5
    svc = _service(history, dim, overrides=overrides)

    m = await svc.phase_preference_map()
    assert m[("27641", "5")] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_worker_without_employee_row_still_gets_derived_score():
    # Sem linha em core.employees (dim vazio) → sem override, mas o nível
    # derivado entra na mesma (o pool do CPO inclui-o).
    history = {"99999": [_stat("1", "Laminagem", ops=200, defects=0)]}
    svc = _service(history, dim={})

    m = await svc.phase_preference_map()
    assert ("99999", "1") in m
    assert m[("99999", "1")] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_empty_history_is_empty_map():
    svc = _service(history={}, dim={})
    assert await svc.phase_preference_map() == {}


# ─────────────────────────────────────────────────────────────────────────
# FactoryState.preference_score_for — lookup puro
# ─────────────────────────────────────────────────────────────────────────

def test_preference_score_for_none_when_empty():
    st = FactoryState(tenant_id=uuid4())
    assert st.preference_score_for("A", "5") is None


def test_preference_score_for_hit_and_miss():
    st = FactoryState(tenant_id=uuid4())
    st.sector_preferences = {("A", "5"): 0.5}
    assert st.preference_score_for("A", "5") == 0.5
    assert st.preference_score_for("A", "9") is None   # fase não mapeada
    assert st.preference_score_for("B", "5") is None   # worker não mapeado


# ─────────────────────────────────────────────────────────────────────────
# loader best-effort
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_loader_none_session_is_empty():
    assert await _load_sector_preferences_db(None, _TENANT) == {}
