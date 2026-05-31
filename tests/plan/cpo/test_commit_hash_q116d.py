"""Q.116.D — compute_commit_hash respeita boost_inputs_snapshot.

Garante que:
  1. boost_inputs_snapshot != None nem vazio -> hash MUDA face ao mesmo
     commit sem boost (reprodutibilidade preservada para replay).
  2. boost_inputs_snapshot=None ou {} -> hash IGUAL ao pre-Q.116.D
     (backwards-compat para commits historicos).
  3. Dois snapshots distintos com mesmas operations/KPIs -> hashes distintos.
  4. Determinismo: chamadas repetidas com os mesmos inputs -> mesmo hash.
"""
from __future__ import annotations

from src.plan.cpo.commits import compute_commit_hash


# ─── Inputs base partilhados ─────────────────────────────────────────────────


_PARENT_SHA = "deadbeef" * 8  # 64 hex chars
_KPIS = {
    "makespan_hours": 168.0,
    "total_tardiness_hours": 12.5,
    "num_late_orders": 2,
    "status": "OK",
}
_OPERATIONS = [
    {"operation_id": "op-1", "start_time": "2026-06-01T08:00:00", "end_time": "2026-06-01T10:00:00"},
    {"operation_id": "op-2", "start_time": "2026-06-01T10:00:00", "end_time": "2026-06-01T12:00:00"},
]
_DELTA = {"entity_type": "work_order", "id": "WO-42"}


# ─── 1. snapshot non-empty altera o hash ─────────────────────────────────────


def test_hash_changes_when_boost_snapshot_present():
    """Mesmas operations/KPIs + boost_inputs diferente -> SHAs distintos."""
    snapshot = {
        "WO-42": {"client": 80, "order": 50, "boat": 20, "effective": 150},
    }
    sha_without = compute_commit_hash(
        parent_sha256=_PARENT_SHA,
        kpis=_KPIS,
        operations=_OPERATIONS,
        delta=_DELTA,
    )
    sha_with = compute_commit_hash(
        parent_sha256=_PARENT_SHA,
        kpis=_KPIS,
        operations=_OPERATIONS,
        delta=_DELTA,
        boost_inputs_snapshot=snapshot,
    )
    assert sha_without != sha_with, (
        "boost_inputs_snapshot tem de afectar o hash — sem isto, "
        "replay perde reprodutibilidade quando boost manual muda."
    )


# ─── 2. backwards-compat: None ou {} = hash pre-Q.116.D ──────────────────────


def test_hash_unchanged_when_boost_snapshot_none():
    """Sem boost (None) -> hash igual ao implicito pre-Q.116.D."""
    sha_no_arg = compute_commit_hash(
        parent_sha256=_PARENT_SHA,
        kpis=_KPIS,
        operations=_OPERATIONS,
        delta=_DELTA,
    )
    sha_explicit_none = compute_commit_hash(
        parent_sha256=_PARENT_SHA,
        kpis=_KPIS,
        operations=_OPERATIONS,
        delta=_DELTA,
        boost_inputs_snapshot=None,
    )
    assert sha_no_arg == sha_explicit_none


def test_hash_unchanged_when_boost_snapshot_empty_dict():
    """Snapshot dict vazio == None — hash igual ao baseline."""
    sha_no_arg = compute_commit_hash(
        parent_sha256=_PARENT_SHA,
        kpis=_KPIS,
        operations=_OPERATIONS,
        delta=_DELTA,
    )
    sha_empty = compute_commit_hash(
        parent_sha256=_PARENT_SHA,
        kpis=_KPIS,
        operations=_OPERATIONS,
        delta=_DELTA,
        boost_inputs_snapshot={},
    )
    assert sha_no_arg == sha_empty, (
        "Backwards-compat: commits historicos sem boost (snapshot {}) "
        "tem de manter o mesmo hash que tinham antes do Q.116.D."
    )


# ─── 3. Dois snapshots distintos -> hashes distintos ─────────────────────────


def test_two_distinct_snapshots_yield_distinct_hashes():
    """Snapshots diferentes -> SHAs diferentes (mesmo plano, boost mudou)."""
    snap_a = {"WO-1": {"client": 100, "order": 0, "boat": 0, "effective": 100}}
    snap_b = {"WO-1": {"client": 100, "order": 50, "boat": 0, "effective": 150}}

    sha_a = compute_commit_hash(
        parent_sha256=_PARENT_SHA,
        kpis=_KPIS,
        operations=_OPERATIONS,
        delta=_DELTA,
        boost_inputs_snapshot=snap_a,
    )
    sha_b = compute_commit_hash(
        parent_sha256=_PARENT_SHA,
        kpis=_KPIS,
        operations=_OPERATIONS,
        delta=_DELTA,
        boost_inputs_snapshot=snap_b,
    )
    assert sha_a != sha_b


# ─── 4. Determinismo — mesma entrada, mesmo hash ─────────────────────────────


def test_hash_is_deterministic_with_boost():
    """Chamadas repetidas com os mesmos snapshots -> mesmo hash (canonical JSON)."""
    snapshot = {
        "WO-7": {"client": 60, "order": 30, "boat": 10, "effective": 100},
        "WO-9": {"client": 0, "order": 0, "boat": 0, "effective": 0},
    }
    sha1 = compute_commit_hash(
        parent_sha256=_PARENT_SHA,
        kpis=_KPIS,
        operations=_OPERATIONS,
        delta=_DELTA,
        boost_inputs_snapshot=snapshot,
    )
    sha2 = compute_commit_hash(
        parent_sha256=_PARENT_SHA,
        kpis=_KPIS,
        operations=_OPERATIONS,
        delta=_DELTA,
        boost_inputs_snapshot=dict(snapshot),  # mesma forma, dict novo
    )
    assert sha1 == sha2
