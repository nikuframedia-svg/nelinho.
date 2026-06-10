"""Q.168.C — boost_inputs_snapshot entra no hash E no ScheduleCommit.

A auditoria 2026-06-10 confirmou o gap Q.116.D: `compute_commit_hash` aceita
`boost_inputs_snapshot` e a coluna existe (jsonb, default {}), mas NENHUM
caller passava o snapshot — o construtor do ScheduleCommit nem sequer o
atribuía. Resultado: a coluna ficava sempre `{}` e dois commits com inputs
de boost diferentes davam o MESMO sha (replay sem reprodutibilidade).

Fio agora travado:
  1. hash distinto com/sem snapshot (e back-compat None ≡ {});
  2. create_from_schedule persiste o snapshot e fá-lo entrar no sha;
  3. _attach_effective_boost reutiliza um snapshot pré-calculado SEM tocar
     na BD (db=None prova que não há queries duplicadas pós-commit).
"""
from __future__ import annotations

import pytest

from src.plan.cpo.commits import CommitsService, compute_commit_hash

_SNAP = {"123456": {"client": 50, "order": 20, "boat": 10, "effective": 80}}


class TestHashIncludesBoostSnapshot:
    def test_hash_distinct_with_snapshot(self):
        base = dict(parent_sha256=None, kpis={"makespan_hours": 1.0},
                    operations=[{"operation_id": "o1"}], delta=None)
        assert compute_commit_hash(**base) != compute_commit_hash(
            **base, boost_inputs_snapshot=_SNAP
        ), "inputs de boost diferentes TÊM de dar shas diferentes (Q.116.D)"

    def test_hash_backcompat_none_equals_empty(self):
        """Commits históricos (sem snapshot) sobrevivem à verificação."""
        base = dict(parent_sha256=None, kpis={}, operations=[], delta=None)
        assert compute_commit_hash(**base) == compute_commit_hash(
            **base, boost_inputs_snapshot={}
        )


class TestCreateFromSchedulePersistsSnapshot:
    async def test_snapshot_persisted_and_hashed(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)  # get_latest → None
        service = CommitsService(fake_session, tenant_id)
        commit = await service.create_from_schedule(
            schedule_result={"makespan_hours": 5.0, "operations": []},
            boost_inputs_snapshot=_SNAP,
        )
        assert commit.boost_inputs_snapshot == _SNAP

        fake_session.queue_scalar(None)
        sem = await service.create_from_schedule(
            schedule_result={"makespan_hours": 5.0, "operations": []},
        )
        assert sem.boost_inputs_snapshot == {}
        assert commit.commit_sha256 != sem.commit_sha256, (
            "o snapshot tem de entrar no sha — senão replay perde os boosts"
        )

    async def test_default_stays_empty_dict(self, fake_session, tenant_id):
        """Sem snapshot → {} honesto (nunca None, nunca inventado)."""
        fake_session.queue_scalar(None)
        service = CommitsService(fake_session, tenant_id)
        commit = await service.create_from_schedule(
            schedule_result={"operations": []},
        )
        assert commit.boost_inputs_snapshot == {}


class TestAttachReusesSnapshot:
    async def test_attach_with_snapshot_skips_db(self):
        """Com snapshot pré-calculado o attach NÃO toca na BD (db=None
        rebentaria à primeira query) — o scheduler calcula uma vez antes do
        commit e reutiliza depois."""
        from src.plan.api._cpo_common import _attach_effective_boost

        ops = [{"order_id": "123456"}, {"order_id": "999"}, {"order_id": None}]
        await _attach_effective_boost(None, None, ops, snapshot=_SNAP)
        assert ops[0]["effective_boost"] == 80
        assert ops[1]["effective_boost"] == 0
        assert ops[2]["effective_boost"] == 0

    async def test_attach_without_ops_is_noop(self):
        from src.plan.api._cpo_common import _attach_effective_boost

        await _attach_effective_boost(None, None, [], snapshot=_SNAP)  # não rebenta


class TestPlannedOnlyWithOps:
    """Q.168.C — `planned_order_ids` era adicionado ANTES do truncate: uma
    ordem com a rota TODA concluída (truncada a zero fases) contava como
    "planeada" com 0 ops — fantasma que inflava a cobertura (Q.131.H)."""

    def test_route_fully_completed_is_unplanned_not_phantom(self):
        from uuid import uuid4

        from src.plan.cpo.state import FactoryState
        from src.plan.services.routing_resolver import RoutingResolver

        state = FactoryState(tenant_id=uuid4())
        state.historical_routes_by_model = {
            "M1": [
                {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 1, "duration_hours": 4.0},
                {"fase_id": "2", "fase_nome": "Acabamento", "sequence": 2, "duration_hours": 2.0},
            ]
        }
        resolver = RoutingResolver(state)
        ops = resolver.resolve(
            {"of_id": "OF-DONE", "modelo_id": "M1",
             "completed_fase_ids": ["1", "2"]}  # tudo já feito no ERP
        )

        assert ops == []
        assert "OF-DONE" not in resolver.planned_order_ids, (
            "0 ops não é 'planeada' — fantasma inflava orders_coverage"
        )
        assert resolver.unplanned_count == 1
        assert resolver.unplanned[0]["reason"] == "rota_concluida"

    def test_partially_completed_still_planned(self):
        from uuid import uuid4

        from src.plan.cpo.state import FactoryState
        from src.plan.services.routing_resolver import RoutingResolver

        state = FactoryState(tenant_id=uuid4())
        state.historical_routes_by_model = {
            "M1": [
                {"fase_id": "1", "fase_nome": "Laminagem", "sequence": 1, "duration_hours": 4.0},
                {"fase_id": "2", "fase_nome": "Acabamento", "sequence": 2, "duration_hours": 2.0},
            ]
        }
        resolver = RoutingResolver(state)
        ops = resolver.resolve(
            {"of_id": "OF-MEIO", "modelo_id": "M1", "completed_fase_ids": ["1"]}
        )
        assert len(ops) == 1 and ops[0].phase_id == "2"
        assert "OF-MEIO" in resolver.planned_order_ids
        assert resolver.unplanned_count == 0
