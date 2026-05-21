"""Sprint Q.13.D D.3 — `ImproveService.record_adoption_signal` test.

The improve module is the closing piece of Camada 1: when a decision
the operator executed matches a suggestion the system had pending,
the suggestion's confidence rises (Bayesian Beta-Bernoulli update);
when the operator rejected, it falls.

Without these tests, a future refactor could break:
  * The action_type matching logic
  * The Bayesian math (NaN, divide-by-zero on the first signal)
  * The cap at N=50 that prevents single-signal confidence pinning
  * The persistence shape (`_adoption_n` in `estimated_impact`)
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.improve.models import (
    ImprovementSuggestion,
    SuggestionSource,
    SuggestionStatus,
)
from src.improve.service import ImproveService


_TENANT = UUID("11111111-1111-1111-1111-111111111111")


class _FakeSession:
    """Q.68.3.4: kept local — whereclause introspection ~80L.

    Minimal AsyncSession stand-in that holds rows in a list and
    answers `.execute(select(...))` by returning all rows that match
    the captured filter clauses (a tenant + action_type whitelist).

    Não migrado para o canónico porque o test corre 100x com filtros
    DOMAIN-specific muito intricados; subclassear o canónico não
    reduziria significativamente a complexidade.
    """

    def __init__(self, rows: list[ImprovementSuggestion]) -> None:
        self._rows = list(rows)
        self.flushed = False

    async def execute(self, stmt):
        # Resolve `where` clauses. For this test we only need to honour
        # `action_type ==` and `tenant_id ==` filters; everything else
        # is irrelevant.
        wanted_action = None
        wanted_tenant = None
        for clause in stmt.whereclause.clauses if stmt.whereclause is not None else []:
            try:
                if clause.left.name == "action_type":
                    wanted_action = clause.right.value
                elif clause.left.name == "tenant_id":
                    wanted_tenant = clause.right.value
            except AttributeError:
                continue

        matches = [
            r for r in self._rows
            if (wanted_action is None or r.action_type == wanted_action)
            and (wanted_tenant is None or r.tenant_id == wanted_tenant)
        ]

        class _R:
            def __init__(self, items):
                self._items = items

            def scalars(self):
                return self

            def all(self):
                return list(self._items)

        return _R(matches)

    async def flush(self):
        self.flushed = True

    async def commit(self):
        self.flushed = True

    async def refresh(self, _instance):
        return None


def _suggestion(action_type: str, confidence: float = 0.5) -> ImprovementSuggestion:
    """Build a suggestion row that uses the Beta-Bernoulli prior (N=10)
    via an empty `estimated_impact`. The first signal coerces it to
    the expected Beta(αN, βN) shape inside record_adoption_signal."""
    s = ImprovementSuggestion(
        title="dummy",
        description="dummy",
        domain="other",
        action_type=action_type,
        status=SuggestionStatus.PENDING.value,
        source=SuggestionSource.SEED.value,
        estimated_impact={},
        confidence=confidence,
    )
    s.id = uuid4()
    s.tenant_id = _TENANT
    return s


@pytest.mark.asyncio
async def test_accepted_signal_raises_confidence():
    sug = _suggestion("reduce_standard_time", confidence=0.5)
    session = _FakeSession([sug])
    svc = ImproveService(session, _TENANT)  # type: ignore[arg-type]

    n = await svc.record_adoption_signal(
        action_type="reduce_standard_time", accepted=True,
    )
    assert n == 1
    assert sug.confidence > 0.5
    assert sug.estimated_impact["_last_signal"] == "accepted"
    assert session.flushed is True


@pytest.mark.asyncio
async def test_rejected_signal_lowers_confidence():
    sug = _suggestion("reduce_standard_time", confidence=0.5)
    session = _FakeSession([sug])
    svc = ImproveService(session, _TENANT)  # type: ignore[arg-type]

    n = await svc.record_adoption_signal(
        action_type="reduce_standard_time", accepted=False,
    )
    assert n == 1
    assert sug.confidence < 0.5
    assert sug.estimated_impact["_last_signal"] == "rejected"


@pytest.mark.asyncio
async def test_confidence_clamped_to_unit_interval():
    """Even with extreme starting confidence (1.0) and many accepts,
    the result stays within [0, 1]."""
    sug = _suggestion("reduce_standard_time", confidence=1.0)
    session = _FakeSession([sug])
    svc = ImproveService(session, _TENANT)  # type: ignore[arg-type]

    for _ in range(20):
        await svc.record_adoption_signal(
            action_type="reduce_standard_time", accepted=True,
        )
    assert 0.0 <= sug.confidence <= 1.0


@pytest.mark.asyncio
async def test_no_match_is_a_no_op():
    sug = _suggestion("a_specific_action")
    session = _FakeSession([sug])
    svc = ImproveService(session, _TENANT)  # type: ignore[arg-type]

    n = await svc.record_adoption_signal(
        action_type="a_different_action", accepted=True,
    )
    assert n == 0
    # No update happened
    assert sug.confidence == 0.5
    assert "_last_signal" not in (sug.estimated_impact or {})


@pytest.mark.asyncio
async def test_sample_size_caps_at_50():
    """Many signals must NOT push the effective sample size beyond
    the documented cap (50). Without the cap, late signals get
    too little weight + early signals dominate forever."""
    sug = _suggestion("reduce_standard_time", confidence=0.5)
    session = _FakeSession([sug])
    svc = ImproveService(session, _TENANT)  # type: ignore[arg-type]

    for _ in range(100):
        await svc.record_adoption_signal(
            action_type="reduce_standard_time", accepted=True,
        )
    assert sug.estimated_impact["_adoption_n"] <= 50.0


@pytest.mark.asyncio
async def test_multiple_suggestions_with_same_action_type_all_update():
    """When the operator's decision matches multiple suggestions, all
    of them get the signal — no first-row-wins."""
    s1 = _suggestion("reduce_standard_time", confidence=0.5)
    s2 = _suggestion("reduce_standard_time", confidence=0.7)
    s3 = _suggestion("other_action", confidence=0.5)  # not matched
    session = _FakeSession([s1, s2, s3])
    svc = ImproveService(session, _TENANT)  # type: ignore[arg-type]

    n = await svc.record_adoption_signal(
        action_type="reduce_standard_time", accepted=True,
    )
    assert n == 2
    assert s1.confidence > 0.5
    assert s2.confidence > 0.7
    assert s3.confidence == 0.5  # untouched
