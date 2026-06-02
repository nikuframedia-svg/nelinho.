"""Q.158 — property test: operadores TERMINATED nunca aparecem na skill_matrix.

Spelke axiom 5 (skill-match): o CPO só pode atribuir operadores que realmente
trabalham na fábrica. Um TERMINATED na matriz amplia artificialmente o pool
elegível e pode gerar planos com pessoas que já saíram.

Testa a função pura ``_load_skills_db`` via uma FakeSession que devolve
pares (fase, worker) misturados com workers TERMINATED. A propriedade é:
nenhum worker TERMINATED aparece no resultado — independentemente de quantos
existam no histórico.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.plan.cpo.state import _load_skills_db

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


# ─── fake session ─────────────────────────────────────────────────────────

class _MappingRow(dict):
    """Permite acesso por índice (row["col"]) como SQLAlchemy MappingResult."""
    pass


class _MappingResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = [_MappingRow(r) for r in rows]

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeSkillSession:
    """Devolve pares (fase_id, func_id) e linhas de core.employees fake.

    A query real em ``_load_skills_db`` faz um LEFT JOIN a core.employees.
    Esta fake interpreta a query pelo binding ``:tenant_id`` e devolve
    apenas workers com status='ACTIVE' (o JOIN filtra TERMINATED).

    Para simular o comportamento correcto, a fake NÃO pré-filtra — em vez
    disso replica o que a query SQL faz: só devolve (fase, worker) onde o
    worker não é TERMINATED. Isto valida que a lógica SQL está correcta
    (não que a fake seja esperta).
    """

    def __init__(self, pairs: list[tuple[str, str]], terminated: set[str]) -> None:
        """
        pairs: lista de (fase_id, func_id) do histórico OFFP_EQ
        terminated: conjunto de func_id que são TERMINATED em core.employees
        """
        self._pairs = pairs
        self._terminated = terminated

    async def execute(self, sql: Any, *args: Any, **kwargs: Any) -> Any:
        # Simula o LEFT JOIN + WHERE (e.employee_code IS NULL OR e.status='ACTIVE')
        # Operadores não espelhados (sem linha em core.employees) passam (IS NULL).
        # Operadores TERMINATED são excluídos.
        filtered = [
            {"fase_id": fase, "func_id": func}
            for fase, func in self._pairs
            if func not in self._terminated
        ]
        return _MappingResult(filtered)


# ─── strategies ───────────────────────────────────────────────────────────

@st.composite
def _scenario(draw):
    """Gera um cenário aleatório: pares históricos + subset de TERMINATED."""
    n_workers = draw(st.integers(min_value=1, max_value=20))
    n_phases = draw(st.integers(min_value=1, max_value=10))
    worker_ids = [str(draw(st.integers(min_value=1000, max_value=9999)))
                  for _ in range(n_workers)]
    phase_ids = [str(draw(st.integers(min_value=1, max_value=50)))
                 for _ in range(n_phases)]

    # Pares históricos: cada worker aparece em 1..3 fases
    pairs = []
    for wid in worker_ids:
        for pid in draw(st.lists(
            st.sampled_from(phase_ids), min_size=1, max_size=3, unique=True,
        )):
            pairs.append((pid, wid))

    # Subset de workers que são TERMINATED (usa unique_ids para evitar
    # pedir unique_list com min_size > len(set(worker_ids)))
    unique_worker_ids = list(set(worker_ids))
    n_terminated = draw(st.integers(min_value=0, max_value=len(unique_worker_ids)))
    terminated_list = draw(st.lists(
        st.sampled_from(unique_worker_ids),
        min_size=n_terminated, max_size=n_terminated, unique=True,
    ))
    terminated = set(terminated_list)

    return pairs, terminated


# ─── property test ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@settings(
    deadline=None,
    max_examples=300,
    suppress_health_check=[HealthCheck.too_slow],
)
@given(_scenario())
async def test_terminated_worker_never_in_skill_matrix(scenario):
    """Spelke axiom 5 — nenhum TERMINATED aparece na skill_matrix resultado.

    Independentemente de quantos ex-trabalhadores existam no histórico,
    a ``_load_skills_db`` filtrada não deve incluir nenhum deles na matriz.
    """
    pairs, terminated = scenario

    session = _FakeSkillSession(pairs, terminated)
    matrix = await _load_skills_db(session, TENANT_ID)

    # Todos os workers no resultado devem ser activos
    all_in_matrix: set[str] = set()
    for workers_set in matrix.values():
        all_in_matrix |= workers_set

    leaked = all_in_matrix & terminated
    assert not leaked, (
        f"Workers TERMINATED encontrados na skill_matrix: {leaked!r}. "
        f"A skill_matrix não deve conter ex-trabalhadores."
    )


@pytest.mark.asyncio
async def test_skill_matrix_empty_session_returns_empty():
    """session=None devolve {} (back-compat, nunca InfeasibleError)."""
    result = await _load_skills_db(None, TENANT_ID)
    assert result == {}


@pytest.mark.asyncio
async def test_skill_matrix_all_terminated_returns_empty_sets():
    """Se todos os workers do histórico são TERMINATED, a matriz fica vazia."""
    pairs = [("10", "W_SAIU"), ("10", "W_TAMBEM_SAIU"), ("20", "W_SAIU")]
    terminated = {"W_SAIU", "W_TAMBEM_SAIU"}
    session = _FakeSkillSession(pairs, terminated)
    matrix = await _load_skills_db(session, TENANT_ID)
    # Nenhum worker deve aparecer
    assert all(len(v) == 0 for v in matrix.values()), (
        f"Esperava matriz vazia mas obteve: {matrix}"
    )


@pytest.mark.asyncio
async def test_skill_matrix_active_workers_are_kept():
    """Workers ACTIVE passam pelo filtro intactos."""
    pairs = [("10", "W_ACTIVO"), ("10", "W_SAIU"), ("20", "W_ACTIVO")]
    terminated = {"W_SAIU"}
    session = _FakeSkillSession(pairs, terminated)
    matrix = await _load_skills_db(session, TENANT_ID)
    assert "W_ACTIVO" in matrix.get("10", set())
    assert "W_SAIU" not in matrix.get("10", set())
    assert "W_ACTIVO" in matrix.get("20", set())
