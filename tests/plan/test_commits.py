"""
Tests for src.plan.cpo.commits — Schedule-as-Code (Sprint K.1, K.3).

Strategy: shared `fake_session` fixture + build ScheduleCommit rows
manually (not persisted) to exercise the diff + SHA logic.
"""

from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID, uuid4

import pytest

from src.plan.cpo.commits import (
    CommitsService,
    ScheduleCommit,
    compute_commit_hash,
    compute_operations_diff,
)


TENANT = UUID("11111111-1111-1111-1111-111111111111")


def _commit(
    *,
    sha: str,
    operations: List[Dict[str, Any]] = None,
    kpis: Dict[str, Any] = None,
    parent_id=None,
    alternatives: List[Dict[str, Any]] = None,
) -> ScheduleCommit:
    return ScheduleCommit(
        id=uuid4(),
        tenant_id=TENANT,
        parent_id=parent_id,
        commit_sha256=sha,
        author="test",
        message="",
        kpis=kpis or {},
        operations=operations or [],
        delta={},
        alternatives=alternatives or [],
        cpo_meta={},
        trust_index=0.0,
        operations_count=len(operations or []),
    )


# ---------------------------------------------------------------------------
# compute_commit_hash
# ---------------------------------------------------------------------------

class TestComputeCommitHash:
    def test_deterministic(self):
        h1 = compute_commit_hash(None, {"makespan_hours": 10}, [{"operation_id": "o1"}])
        h2 = compute_commit_hash(None, {"makespan_hours": 10}, [{"operation_id": "o1"}])
        assert h1 == h2
        assert len(h1) == 64

    def test_parent_sha_changes_hash(self):
        base = compute_commit_hash(None, {"a": 1}, [])
        chained = compute_commit_hash(base, {"a": 1}, [])
        assert base != chained

    def test_operations_order_changes_hash(self):
        a = compute_commit_hash(None, {}, [{"operation_id": "o1"}, {"operation_id": "o2"}])
        b = compute_commit_hash(None, {}, [{"operation_id": "o2"}, {"operation_id": "o1"}])
        assert a != b  # order matters — operations are a list, not a set

    def test_delta_contributes_to_hash(self):
        no_delta = compute_commit_hash(None, {"a": 1}, [], None)
        with_delta = compute_commit_hash(None, {"a": 1}, [], {"entity_type": "x"})
        assert no_delta != with_delta


# ---------------------------------------------------------------------------
# compute_operations_diff
# ---------------------------------------------------------------------------

class TestComputeOperationsDiff:
    def test_added_and_removed(self):
        a = _commit(sha="a" * 64, operations=[{"operation_id": "op1"}])
        b = _commit(sha="b" * 64, operations=[{"operation_id": "op2"}])
        diff = compute_operations_diff(a, b)
        assert diff["summary"]["removed_count"] == 1
        assert diff["summary"]["added_count"] == 1
        assert diff["summary"]["changed_count"] == 0
        assert diff["removed"][0]["operation_id"] == "op1"
        assert diff["added"][0]["operation_id"] == "op2"

    def test_changed_field_reported(self):
        a = _commit(sha="a" * 64, operations=[
            {"operation_id": "op1", "machine_id": "M1", "start_time": "t0"},
        ])
        b = _commit(sha="b" * 64, operations=[
            {"operation_id": "op1", "machine_id": "M2", "start_time": "t0"},
        ])
        diff = compute_operations_diff(a, b)
        assert diff["summary"]["changed_count"] == 1
        entry = diff["changed"][0]
        assert entry["operation_id"] == "op1"
        assert entry["field"] == "machine_id"
        assert entry["before"] == "M1"
        assert entry["after"] == "M2"

    def test_kpi_deltas(self):
        a = _commit(sha="a" * 64, kpis={"makespan_hours": 10.0, "num_late_orders": 2})
        b = _commit(sha="b" * 64, kpis={"makespan_hours": 7.5, "num_late_orders": 1})
        diff = compute_operations_diff(a, b)
        assert diff["kpi_deltas"]["makespan_hours"]["delta"] == pytest.approx(-2.5)
        assert diff["kpi_deltas"]["num_late_orders"]["delta"] == pytest.approx(-1)

    def test_identical_commits_produce_zero_diff(self):
        ops = [{"operation_id": "o1", "machine_id": "M1"}]
        a = _commit(sha="a" * 64, operations=ops, kpis={"x": 1})
        b = _commit(sha="b" * 64, operations=ops, kpis={"x": 1})
        diff = compute_operations_diff(a, b)
        assert diff["summary"] == {"added_count": 0, "removed_count": 0, "changed_count": 0}
        # Same-KPI entries are kept with delta=0 so the UI knows the KPI exists
        assert diff["kpi_deltas"]["x"]["delta"] == 0


# ---------------------------------------------------------------------------
# CommitsService — uses the shared `fake_session` fixture
# ---------------------------------------------------------------------------

class TestCommitsServiceCreate:
    async def test_first_commit_has_no_parent(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)  # get_latest → None
        service = CommitsService(fake_session, tenant_id)

        schedule = {
            "makespan_hours": 10.0,
            "total_tardiness_hours": 0.0,
            "num_late_orders": 0,
            "setups": 2,
            "avg_utilization": 65.0,
            "operations": [{"operation_id": "op1"}],
            "cpo_meta": {"generations_run": 5},
        }
        commit = await service.create_from_schedule(
            schedule_result=schedule,
            delta=None,
            author="tester",
        )
        assert commit.parent_id is None
        assert len(commit.commit_sha256) == 64
        assert commit.kpis["makespan_hours"] == 10.0
        assert commit.operations_count == 1
        assert commit in fake_session.added
        assert fake_session.flush_calls >= 1
        # Q.133.A.1 — create_from_schedule TEM de fazer commit() (não só flush).
        # Sem isto o get_session salta o commit (flush esvazia session.new) e o
        # INSERT do ScheduleCommit perde-se silenciosamente (grid vazio).
        assert fake_session.commit_calls >= 1

    async def test_chained_commits_link_parent(self, fake_session, tenant_id):
        parent = _commit(sha="p" * 64, kpis={"makespan_hours": 20})
        parent.id = uuid4()
        fake_session.queue_scalar(parent)  # get_latest → parent

        service = CommitsService(fake_session, tenant_id)
        commit = await service.create_from_schedule(
            schedule_result={"makespan_hours": 10, "operations": []},
        )
        assert commit.parent_id == parent.id
        assert commit.commit_sha256 != parent.commit_sha256

    async def test_alternatives_persisted(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)
        service = CommitsService(fake_session, tenant_id)
        alts = [
            {"rank": 0, "fitness": 10.0, "chromosome": {"permutation": [0, 1]}},
            {"rank": 1, "fitness": 11.0, "chromosome": {"permutation": [1, 0]}},
        ]
        commit = await service.create_from_schedule(
            schedule_result={"makespan_hours": 5, "operations": []},
            mapelites_representatives=alts,
        )
        assert commit.alternatives == alts


class TestCommitsServiceRetrieve:
    async def test_list_commits_queries_session(self, fake_session, tenant_id):
        sample = [_commit(sha=str(i).zfill(64), kpis={}) for i in range(3)]
        fake_session.queue_scalars(sample)
        service = CommitsService(fake_session, tenant_id)
        out = await service.list_commits(limit=10)
        assert len(out) == 3

    async def test_get_by_sha_prefix_rejects_short(self, fake_session, tenant_id):
        service = CommitsService(fake_session, tenant_id)
        assert await service.get_by_sha_prefix("abc") is None

    async def test_to_dict_includes_operations_when_requested(self):
        commit = _commit(
            sha="a" * 64,
            operations=[{"operation_id": "o1"}],
            kpis={"makespan_hours": 8},
        )
        assert "operations" not in CommitsService.to_dict(commit)
        with_ops = CommitsService.to_dict(commit, include_operations=True)
        assert with_ops["operations"] == [{"operation_id": "o1"}]
        assert with_ops["short_sha"] == "a" * 12

    async def test_to_dict_exposes_status_and_safety_net_q133(self):
        """Q.133.A.2 — to_dict expõe `status` (default DRAFT) e
        `safety_net_triggered` (do cpo_meta) para o grid rotular."""
        c = _commit(sha="c" * 64)
        d = CommitsService.to_dict(c)
        assert d["status"] == "DRAFT"  # status não-setado → DRAFT
        assert d["safety_net_triggered"] is False
        c2 = _commit(sha="d" * 64)
        c2.cpo_meta = {"safety_net_triggered": True}
        assert CommitsService.to_dict(c2)["safety_net_triggered"] is True


class TestCommitsServiceDiff:
    async def test_diff_not_found_raises(self, fake_session, tenant_id):
        # Both resolvers miss → ValueError
        fake_session.queue_scalar(None)  # from_sha direct lookup
        fake_session.queue_scalar(None)  # to_sha direct lookup
        service = CommitsService(fake_session, tenant_id)
        with pytest.raises(ValueError, match="commit_not_found"):
            await service.diff("short", "also_short")

    async def test_diff_round_trip(self, fake_session, tenant_id):
        a = _commit(sha="a" * 64, operations=[{"operation_id": "o1", "machine_id": "M1"}])
        b = _commit(sha="b" * 64, operations=[{"operation_id": "o1", "machine_id": "M2"}])
        # diff() makes TWO `get_by_sha` calls → queue two scalars
        fake_session.queue_scalar(a)
        fake_session.queue_scalar(b)
        service = CommitsService(fake_session, tenant_id)
        diff = await service.diff(a.commit_sha256, b.commit_sha256)
        assert diff["summary"]["changed_count"] == 1
