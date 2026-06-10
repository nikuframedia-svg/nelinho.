"""Q.135.F3.4 — testes de PhaseConfig: service, endpoint e property tests Spelke.

Cobre:
  * upsert + audit (FakeSession)
  * whitelist inválida → ValueError (axioma 5)
  * Laminagem team_size=1 → ValueError (axioma 4)
  * num_stations_override fora de [1, _N_MAX] → ValueError (axioma 1)
  * property: workers_for ⊆ skill_matrix mesmo com whitelist
  * property: Laminagem mantém >= 2 quando PAIR_PREFERRED
  * property: num_stations_for >= 1 sempre
  * property: com whitelist {A}, nenhum worker fora de {A} é elegível
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from hypothesis import given, settings, strategies as st

from src.plan.cpo.state import FactoryState
from src.plan.services.phase_config_service import PhaseConfigService, _N_MAX

# ─── helpers ──────────────────────────────────────────────────────────────

TEST_TENANT = UUID("11111111-1111-1111-1111-111111111111")
FASE_LAMINAGEM = "10"  # FP_ID arbitrário que mapeamos ao nome "Laminagem"
FASE_PINTURA = "18"


def _make_state(
    skill_matrix: Optional[Dict[str, Set[str]]] = None,
    phase_config: Optional[Dict[str, Dict[str, Any]]] = None,
    phase_stations: Optional[Dict[str, int]] = None,
) -> FactoryState:
    state = FactoryState(tenant_id=TEST_TENANT)
    if skill_matrix is not None:
        state.skill_matrix = skill_matrix
    if phase_config is not None:
        state.phase_config = phase_config
    if phase_stations is not None:
        state.phase_stations = phase_stations
    return state


class _FakeAuditSession:
    """Minimal fake session para PhaseConfigService (sem Postgres)."""

    def __init__(self, existing_row=None):
        self._existing = existing_row
        self.added: List[Any] = []
        self.flush_calls = 0

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flush_calls += 1

    async def execute(self, stmt: Any, *args, **kwargs):
        # SELECT PhaseConfig: devolve a row existente
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=self._existing)
        return result


# audit_change é real mas escreve num FakeSession — mockamos para não precisar
# de schema governance em testes unitários

async def _noop_audit(*args, **kwargs):
    pass


# ─── testes unitários do service ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_insert_new(monkeypatch):
    """Upsert numa fase sem config existente cria uma nova linha."""
    monkeypatch.setattr(
        "src.plan.services.phase_config_service.audit_change", _noop_audit
    )
    session = _FakeAuditSession(existing_row=None)
    svc = PhaseConfigService(session, TEST_TENANT)
    row = await svc.upsert(
        FASE_PINTURA,
        team_size_override=2,
        num_stations_override=3,
        known_workers={"w1", "w2"},
    )
    assert row.phase_id == FASE_PINTURA
    assert row.team_size_override == 2
    assert row.num_stations_override == 3
    assert len(session.added) == 1
    assert session.flush_calls == 1


@pytest.mark.asyncio
async def test_upsert_update_existing(monkeypatch):
    """Upsert numa fase com config existente actualiza os campos."""
    monkeypatch.setattr(
        "src.plan.services.phase_config_service.audit_change", _noop_audit
    )
    from src.plan.models.phase_config import PhaseConfig
    from datetime import datetime, timezone

    existing = PhaseConfig(
        id=uuid4(),
        tenant_id=TEST_TENANT,
        phase_id=FASE_PINTURA,
        team_size_override=1,
        num_stations_override=2,
        updated_at=datetime.now(timezone.utc),
    )
    session = _FakeAuditSession(existing_row=existing)
    svc = PhaseConfigService(session, TEST_TENANT)
    row = await svc.upsert(
        FASE_PINTURA,
        team_size_override=3,
        num_stations_override=5,
    )
    assert row.team_size_override == 3
    assert row.num_stations_override == 5
    # update não faz session.add()
    assert len(session.added) == 0


@pytest.mark.asyncio
async def test_whitelist_outside_skill_raises(monkeypatch):
    """allowed_worker_ids com worker fora do skill_matrix → ValueError (axioma 5)."""
    monkeypatch.setattr(
        "src.plan.services.phase_config_service.audit_change", _noop_audit
    )
    session = _FakeAuditSession(existing_row=None)
    svc = PhaseConfigService(session, TEST_TENANT)
    with pytest.raises(ValueError, match="axioma 5"):
        await svc.upsert(
            FASE_PINTURA,
            allowed_worker_ids=["w_unknown"],
            known_workers={"w1", "w2"},
        )


@pytest.mark.asyncio
async def test_laminagem_team_size_1_raises(monkeypatch):
    """Laminagem com team_size_override=1 → ValueError (axioma 4)."""
    monkeypatch.setattr(
        "src.plan.services.phase_config_service.audit_change", _noop_audit
    )
    session = _FakeAuditSession(existing_row=None)
    svc = PhaseConfigService(session, TEST_TENANT)
    with pytest.raises(ValueError, match="axioma 4"):
        await svc.upsert(
            FASE_LAMINAGEM,
            team_size_override=1,
            phase_name="Laminagem",
        )


@pytest.mark.asyncio
async def test_num_stations_zero_raises(monkeypatch):
    """num_stations_override=0 → ValueError (axioma 1)."""
    monkeypatch.setattr(
        "src.plan.services.phase_config_service.audit_change", _noop_audit
    )
    session = _FakeAuditSession(existing_row=None)
    svc = PhaseConfigService(session, TEST_TENANT)
    with pytest.raises(ValueError, match="axioma capacity"):
        await svc.upsert(FASE_PINTURA, num_stations_override=0)


@pytest.mark.asyncio
async def test_num_stations_above_max_raises(monkeypatch):
    """num_stations_override > _N_MAX → ValueError (axioma 1)."""
    monkeypatch.setattr(
        "src.plan.services.phase_config_service.audit_change", _noop_audit
    )
    session = _FakeAuditSession(existing_row=None)
    svc = PhaseConfigService(session, TEST_TENANT)
    with pytest.raises(ValueError, match="axioma capacity"):
        await svc.upsert(FASE_PINTURA, num_stations_override=_N_MAX + 1)


# ─── testes unitários de FactoryState ─────────────────────────────────────


def test_workers_for_no_override():
    """Sem override, workers_for devolve o skill_matrix inteiro."""
    state = _make_state(skill_matrix={"f1": {"w1", "w2", "w3"}})
    assert state.workers_for("f1") == {"w1", "w2", "w3"}


def test_workers_for_whitelist_intersection():
    """Com whitelist, devolve intersecção com skill_matrix."""
    state = _make_state(
        skill_matrix={"f1": {"w1", "w2", "w3"}},
        phase_config={"f1": {"allowed_worker_ids": ["w1", "w3"], "team_size_override": None, "num_stations_override": None}},
    )
    assert state.workers_for("f1") == {"w1", "w3"}


def test_workers_for_whitelist_cannot_exceed_skill_matrix():
    """Whitelist com worker fora do skill_matrix → não aparece no resultado."""
    state = _make_state(
        skill_matrix={"f1": {"w1"}},
        phase_config={"f1": {"allowed_worker_ids": ["w1", "w_ghost"], "team_size_override": None, "num_stations_override": None}},
    )
    result = state.workers_for("f1")
    assert "w_ghost" not in result
    assert result == {"w1"}


def test_can_perform_respects_whitelist():
    """can_perform com whitelist exclui workers fora dela."""
    state = _make_state(
        skill_matrix={"f1": {"w1", "w2"}},
        phase_config={"f1": {"allowed_worker_ids": ["w1"], "team_size_override": None, "num_stations_override": None}},
    )
    assert state.can_perform("f1", "w1") is True
    assert state.can_perform("f1", "w2") is False


def test_team_size_override_respected():
    """team_size_override é aplicado."""
    state = _make_state(
        phase_config={"f1": {"team_size_override": 3, "num_stations_override": None, "allowed_worker_ids": None}},
    )
    assert state.team_size_for("f1", "PINTURA") == 3


def test_team_size_laminagem_override_minimum():
    """Laminagem com team_size_override < 2 → forçado a 2 (axioma 4).

    Q.169.C — match EXATO do nome canónico (era substring): "Laminagem
    Standard" não é uma fase real da NELO (fases reais: Laminagem=1,
    peças=36, Double Dutch=54, Infusão=67 — medidas live no offp_eq:
    só a fase 1 tem par maioritário; 36/54/67 são 64-99% solo)."""
    state = _make_state(
        phase_config={"f1": {"team_size_override": 1, "num_stations_override": None, "allowed_worker_ids": None}},
    )
    result = state.team_size_for("f1", "Laminagem")
    assert result >= 2


def test_team_size_variantes_solo_nao_herdam_par_q169c():
    """Variantes de laminagem maioritariamente SOLO no histórico real
    (offp_eq live 2026-06-10: peças 63.9%, Double Dutch 99.4%, Infusão
    98.8% solo) NÃO herdam o mínimo de par por substring."""
    state = _make_state(phase_config={})
    assert state.team_size_for("36", "Laminagem peças") == 1
    assert state.team_size_for("54", "Laminagem Double Dutch") == 1
    assert state.team_size_for("67", "Laminagem Infusão") == 1


def test_num_stations_override_respected():
    """num_stations_override é aplicado."""
    state = _make_state(
        phase_stations={"f1": 5},
        phase_config={"f1": {"num_stations_override": 2, "team_size_override": None, "allowed_worker_ids": None}},
    )
    assert state.num_stations_for("f1") == 2


def test_num_stations_fallback_to_phase_stations():
    """Sem override, num_stations_for usa phase_stations."""
    state = _make_state(phase_stations={"f1": 7})
    assert state.num_stations_for("f1") == 7


def test_num_stations_fallback_1_when_no_data():
    """Sem override e sem phase_stations, num_stations_for devolve 1 (axioma 1)."""
    state = _make_state()
    assert state.num_stations_for("f_unknown") == 1


# ─── property tests Spelke ────────────────────────────────────────────────


@st.composite
def _phase_setup(draw):
    """Gera (skill_set, whitelist_subset, phase_id) para property tests."""
    n_workers = draw(st.integers(min_value=1, max_value=20))
    worker_ids = [f"w{i}" for i in range(n_workers)]
    skill_set = set(draw(st.lists(st.sampled_from(worker_ids), min_size=1, max_size=n_workers, unique=True)))
    # whitelist é sempre um subconjunto do skill_set
    whitelist_size = draw(st.integers(min_value=0, max_value=len(skill_set)))
    whitelist = list(draw(st.lists(
        st.sampled_from(sorted(skill_set)),
        min_size=whitelist_size,
        max_size=whitelist_size,
        unique=True,
    ))) if skill_set else []
    return skill_set, whitelist, "f_test"


@given(_phase_setup())
@settings(max_examples=200)
def test_property_workers_within_skill_matrix(setup):
    """Property: workers_for ⊆ skill_matrix para qualquer whitelist válida."""
    skill_set, whitelist, fase_id = setup
    state = _make_state(
        skill_matrix={fase_id: skill_set},
        phase_config={fase_id: {
            "allowed_worker_ids": whitelist if whitelist else None,
            "team_size_override": None,
            "num_stations_override": None,
        }},
    )
    result = state.workers_for(fase_id)
    assert result <= skill_set, (
        f"workers_for retornou {result} fora de skill_matrix {skill_set}"
    )


@given(_phase_setup())
@settings(max_examples=200)
def test_property_whitelist_single_worker_only_that_worker(setup):
    """Property: com whitelist {A}, apenas A é elegível (se A ∈ skill_matrix)."""
    skill_set, _, fase_id = setup
    if not skill_set:
        return
    chosen = next(iter(skill_set))
    state = _make_state(
        skill_matrix={fase_id: skill_set},
        phase_config={fase_id: {
            "allowed_worker_ids": [chosen],
            "team_size_override": None,
            "num_stations_override": None,
        }},
    )
    result = state.workers_for(fase_id)
    assert result == {chosen} or result == set()
    for w in result:
        assert w == chosen


@given(st.integers(min_value=1, max_value=_N_MAX))
@settings(max_examples=100)
def test_property_num_stations_override_ge_1(n):
    """Property: num_stations_for >= 1 para qualquer override válido [1.._N_MAX]."""
    state = _make_state(
        phase_config={"f1": {"num_stations_override": n, "team_size_override": None, "allowed_worker_ids": None}},
    )
    assert state.num_stations_for("f1") >= 1


@given(st.integers(min_value=2, max_value=10))
@settings(max_examples=100)
def test_property_laminagem_team_size_ge_2(override):
    """Property: Laminagem team_size_for >= 2 mesmo com override >= 2."""
    state = _make_state(
        phase_config={"f_lam": {"team_size_override": override, "num_stations_override": None, "allowed_worker_ids": None}},
    )
    result = state.team_size_for("f_lam", "Laminagem")
    assert result >= 2


@given(st.integers(min_value=1, max_value=1))
@settings(max_examples=5)
def test_property_laminagem_team_size_1_bumped_to_2(override):
    """Property: Laminagem com override=1 → bumped para 2 (PAIR_PREFERRED)."""
    state = _make_state(
        phase_config={"f_lam": {"team_size_override": override, "num_stations_override": None, "allowed_worker_ids": None}},
    )
    result = state.team_size_for("f_lam", "Laminagem")
    assert result == 2
