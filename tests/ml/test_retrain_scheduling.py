"""
Tests for src.ml.jobs.scheduling.register_ml_retrain_jobs.

Strategy: fake scheduler records add_job calls; assert correct cron specs
and per-tenant registration. No APScheduler instance needed.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import List
from uuid import UUID

from src.ml.jobs.scheduling import register_ml_retrain_jobs


TENANT_A = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = UUID("22222222-2222-2222-2222-222222222222")


class _FakeScheduler:
    def __init__(self):
        self.jobs: List[dict] = []

    def add_job(self, fn, trigger=None, args=None, **kwargs):
        self.jobs.append({
            "fn": fn.__name__ if hasattr(fn, "__name__") else str(fn),
            "trigger": trigger,
            "args": args,
            **kwargs,
        })


class TestRegisterMLRetrainJobs:
    def test_noop_when_scheduler_none(self):
        assert register_ml_retrain_jobs(None, tenants=[TENANT_A]) == 0

    def test_noop_when_no_tenants(self):
        sched = _FakeScheduler()
        assert register_ml_retrain_jobs(sched, tenants=None) == 0
        assert register_ml_retrain_jobs(sched, tenants=[]) == 0
        assert sched.jobs == []

    def test_registers_three_jobs_per_tenant(self):
        sched = _FakeScheduler()
        count = register_ml_retrain_jobs(sched, tenants=[TENANT_A])
        # Sprint Q.54.F — duration + quality_risk + otd_risk = 3
        # (surrogate has empty cron → skipped).
        assert count == 3
        ids = {j["id"] for j in sched.jobs}
        assert f"ml_retrain:duration:{TENANT_A}" in ids
        assert f"ml_retrain:quality_risk:{TENANT_A}" in ids
        assert f"ml_retrain:otd_risk:{TENANT_A}" in ids

    def test_registers_across_multiple_tenants(self):
        sched = _FakeScheduler()
        count = register_ml_retrain_jobs(sched, tenants=[TENANT_A, TENANT_B])
        # 3 jobs × 2 tenants = 6
        assert count == 6
        names = {j["name"] for j in sched.jobs}
        assert f"ml_retrain_duration[{TENANT_A}]" in names
        assert f"ml_retrain_duration[{TENANT_B}]" in names
        assert f"ml_retrain_otd_risk[{TENANT_A}]" in names

    def test_replace_existing_set(self):
        sched = _FakeScheduler()
        register_ml_retrain_jobs(sched, tenants=[TENANT_A])
        for job in sched.jobs:
            assert job["replace_existing"] is True
            assert job["coalesce"] is True
            assert job["max_instances"] == 1
