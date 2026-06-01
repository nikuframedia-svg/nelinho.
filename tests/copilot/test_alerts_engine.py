"""
Tests for src.copilot.alerts.engine.AlertsEngine.

Strategy: inject a fake `SemanticQueriesInMemory` via the constructor so we
control what each detector sees. Use the shared `FakeSession` fixture to
capture inserted alerts and stub dedup lookups.

Coverage:
- Bottleneck detector: threshold gate, severity escalation, ignored rows
- Skills detector: SPOF (1 capable) vs WARN (2 capable)
- Quality detector: under/over threshold
- Delivery risk detector: returns nothing (blocked metric)
- Deduplication: second scan within window does not re-insert same alert
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import pytest

from src.copilot.alerts.engine import (
    AlertsEngine,
    BOTTLENECK_DAYS_THRESHOLD,
    QUALITY_EVENTS_THRESHOLD,
)
from src.copilot.alerts.models import (
    CODE_BOTTLENECK_FORMATION,
    CODE_DELIVERY_RISK,
    CODE_DURATION_FALLBACK_HIGH,
    CODE_ORDERS_WITHOUT_ROUTING,
    CODE_QUALITY_DEGRADATION,
    CODE_SKILLS_CONCENTRATION,
    CopilotAlert,
    STATUS_ACTIVE,
)
from src.plan.cpo.scheduler_run import _upsert_cpo_alert
from src.plan.models.order import OrderStatus, ProductionOrder


# ---------------------------------------------------------------------------
# Fake SemanticQueriesInMemory — returns scripted results
# ---------------------------------------------------------------------------

class FakeSemanticQueries:
    def __init__(self) -> None:
        self._results: Dict[str, Dict[str, Any]] = {}

    def set(self, method: str, result: Dict[str, Any]) -> None:
        self._results[method] = result

    def get_wip(self, **_):
        return self._results.get("get_wip", {"status": "BLOCKED"})

    def get_bottlenecks(self, **_):
        return self._results.get("get_bottlenecks", {"status": "BLOCKED"})

    def get_skills_risk(self, **_):
        return self._results.get("get_skills_risk", {"status": "BLOCKED"})

    def get_quality(self, **_):
        return self._results.get("get_quality", {"status": "BLOCKED"})


def _added_alerts(session) -> List[CopilotAlert]:
    return [o for o in session.added if isinstance(o, CopilotAlert)]


# ---------------------------------------------------------------------------
# Bottleneck
# ---------------------------------------------------------------------------

class TestBottleneckDetector:
    async def test_emits_alert_above_threshold(self, fake_session, tenant_id):
        sq = FakeSemanticQueries()
        sq.set("get_bottlenecks", {
            "status": "OK",
            "rows": [
                {"fase_id": "F-1", "fase_nome": "Laminagem",
                 "backlog_dias": BOTTLENECK_DAYS_THRESHOLD + 5,
                 "backlog_horas": 240},
            ],
        })
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)

        summary = await engine.scan()

        alerts = _added_alerts(fake_session)
        bottleneck_alerts = [a for a in alerts if a.code == CODE_BOTTLENECK_FORMATION]
        assert len(bottleneck_alerts) == 1
        assert bottleneck_alerts[0].severity == "WARN"
        assert bottleneck_alerts[0].entity_refs == ["fase:F-1"]
        assert summary["created"] >= 1

    async def test_escalates_to_critical_at_2x_threshold(self, fake_session, tenant_id):
        sq = FakeSemanticQueries()
        sq.set("get_bottlenecks", {
            "status": "OK",
            "rows": [
                {"fase_id": "F-2", "fase_nome": "Pintura",
                 "backlog_dias": BOTTLENECK_DAYS_THRESHOLD * 2.5,
                 "backlog_horas": 400},
            ],
        })
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)

        await engine.scan()

        alerts = [a for a in _added_alerts(fake_session) if a.code == CODE_BOTTLENECK_FORMATION]
        assert len(alerts) == 1
        assert alerts[0].severity == "CRITICAL"

    async def test_ignores_rows_below_threshold(self, fake_session, tenant_id):
        sq = FakeSemanticQueries()
        sq.set("get_bottlenecks", {
            "status": "OK",
            "rows": [
                {"fase_id": "F-3", "fase_nome": "Cola",
                 "backlog_dias": BOTTLENECK_DAYS_THRESHOLD - 1,
                 "backlog_horas": 8},
            ],
        })
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)

        await engine.scan()

        assert not [a for a in _added_alerts(fake_session) if a.code == CODE_BOTTLENECK_FORMATION]

    async def test_blocked_result_emits_nothing(self, fake_session, tenant_id):
        sq = FakeSemanticQueries()  # all methods return BLOCKED by default
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)

        summary = await engine.scan()

        assert summary["created"] == 0
        assert _added_alerts(fake_session) == []


# ---------------------------------------------------------------------------
# Skills concentration
# ---------------------------------------------------------------------------

class TestSkillsDetector:
    async def test_spof_is_critical(self, fake_session, tenant_id):
        sq = FakeSemanticQueries()
        sq.set("get_skills_risk", {
            "status": "OK",
            "rows": [
                {"fase_id": "F-10", "fase_nome": "Rotomoldagem",
                 "num_funcionarios_aptos": 1},
            ],
        })
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)

        await engine.scan()

        alerts = [a for a in _added_alerts(fake_session) if a.code == CODE_SKILLS_CONCENTRATION]
        assert len(alerts) == 1
        assert alerts[0].severity == "CRITICAL"

    async def test_two_capable_is_warn(self, fake_session, tenant_id):
        sq = FakeSemanticQueries()
        sq.set("get_skills_risk", {
            "status": "OK",
            "rows": [
                {"fase_id": "F-11", "fase_nome": "Infusão",
                 "num_funcionarios_aptos": 2},
            ],
        })
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)

        await engine.scan()

        alerts = [a for a in _added_alerts(fake_session) if a.code == CODE_SKILLS_CONCENTRATION]
        assert len(alerts) == 1
        assert alerts[0].severity == "WARN"


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

class TestQualityDetector:
    async def test_fires_above_threshold(self, fake_session, tenant_id):
        sq = FakeSemanticQueries()
        rows = [
            {"erro_tipo": "rebarba", "total_erros": QUALITY_EVENTS_THRESHOLD + 100},
            {"erro_tipo": "risco", "total_erros": 50},
        ]
        sq.set("get_quality", {"status": "OK", "rows": rows})
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)

        await engine.scan()

        alerts = [a for a in _added_alerts(fake_session) if a.code == CODE_QUALITY_DEGRADATION]
        assert len(alerts) == 1
        assert alerts[0].severity == "WARN"
        assert "rebarba" in alerts[0].context["top_error_types"]

    async def test_under_threshold_stays_silent(self, fake_session, tenant_id):
        sq = FakeSemanticQueries()
        sq.set("get_quality", {
            "status": "OK",
            "rows": [{"erro_tipo": "rebarba", "total_erros": QUALITY_EVENTS_THRESHOLD - 10}],
        })
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)

        await engine.scan()

        assert not [a for a in _added_alerts(fake_session) if a.code == CODE_QUALITY_DEGRADATION]


# ---------------------------------------------------------------------------
# Delivery risk — Q.31.H: barco com transporte próximo e ainda em produção
# ---------------------------------------------------------------------------

class TestDeliveryRiskDetector:
    @staticmethod
    def _order(tenant_id, transport_date, hull=4271):
        return ProductionOrder(
            id=uuid4(),
            tenant_id=tenant_id,
            legacy_id=hull,
            product_name="K1 Vanquish",
            product_type="K1",
            current_phase_name="Laminagem",
            status=OrderStatus.IN_PROGRESS,
            transport_date=transport_date,
        )

    async def test_boat_due_soon_in_production_fires_warn(self, fake_session, tenant_id):
        fake_session.queue_scalars([
            self._order(tenant_id, date.today() + timedelta(days=1)),
        ])
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=FakeSemanticQueries())
        await engine.scan()

        alerts = [a for a in _added_alerts(fake_session) if a.code == CODE_DELIVERY_RISK]
        assert len(alerts) == 1
        assert alerts[0].severity == "WARN"
        assert alerts[0].entity_refs == ["barco:4271"]

    async def test_overdue_boat_is_critical(self, fake_session, tenant_id):
        fake_session.queue_scalars([
            self._order(tenant_id, date.today() - timedelta(days=2)),
        ])
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=FakeSemanticQueries())
        await engine.scan()

        alerts = [a for a in _added_alerts(fake_session) if a.code == CODE_DELIVERY_RISK]
        assert len(alerts) == 1
        assert alerts[0].severity == "CRITICAL"

    async def test_no_orders_no_delivery_alert(self, fake_session, tenant_id):
        fake_session.queue_scalars([])
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=FakeSemanticQueries())
        await engine.scan()

        alerts = [a for a in _added_alerts(fake_session) if a.code == CODE_DELIVERY_RISK]
        assert alerts == []


# ---------------------------------------------------------------------------
# Dedup (within window, same code+entity)
# ---------------------------------------------------------------------------

class TestDedup:
    async def test_second_scan_within_window_does_not_reinsert(
        self, fake_session, tenant_id,
    ):
        sq = FakeSemanticQueries()
        sq.set("get_bottlenecks", {
            "status": "OK",
            "rows": [
                {"fase_id": "F-1", "fase_nome": "Laminagem",
                 "backlog_dias": BOTTLENECK_DAYS_THRESHOLD + 5,
                 "backlog_horas": 240},
            ],
        })
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)

        # First scan — inserts
        await engine.scan()
        inserted_first = _added_alerts(fake_session)
        assert len(inserted_first) == 1

        # Simulate second scan hitting dedup: pre-queue the id of the recent
        # alert, then the full alert row for the entity_ref check.
        recent = inserted_first[0]
        # queue scalar list (id subquery) then scalar list (full row check)
        fake_session.queue_scalars([recent.id])  # id query result
        fake_session.queue_scalars([recent])      # full row check
        # bottleneck is the first detector, then each other detector will
        # run its own query — empty results keep them silent.
        summary_second = await engine.scan()

        assert summary_second["skipped_duplicate"] >= 1
        # No additional CopilotAlert added after dedup
        bottleneck_alerts = [
            a for a in _added_alerts(fake_session) if a.code == CODE_BOTTLENECK_FORMATION
        ]
        assert len(bottleneck_alerts) == 1


# ---------------------------------------------------------------------------
# Q.138.G — dedup de alertas CPO sem entity_refs (_upsert_cpo_alert)
# ---------------------------------------------------------------------------

class TestCpoAlertUpsertDedup:
    """Prova que _upsert_cpo_alert nunca cria 2 linhas activas para o mesmo code.

    Cenário: scheduler corre 2 vezes seguidas com as mesmas ordens sem rota.
    Após o segundo upsert deve existir exactamente 1 alerta activo com o
    code ORDERS_WITHOUT_ROUTING — não 2.
    """

    async def test_second_call_updates_existing_alert_not_inserts(
        self, fake_session, tenant_id,
    ):
        # --- primeira chamada: nenhum alerta activo → insere ---
        fake_session.queue_scalars([])  # SELECT → 0 rows → vai inserir
        await _upsert_cpo_alert(
            fake_session,
            tenant_id,
            code=CODE_ORDERS_WITHOUT_ROUTING,
            title="4 ordens sem rota — não planeadas",
            message_pt="4 ordens ficaram fora do plano.",
            context={"unplanned_count": 4, "unplanned_orders": ["A", "B", "C", "D"]},
        )
        inserted_after_first = _added_alerts(fake_session)
        assert len(inserted_after_first) == 1
        assert inserted_after_first[0].code == CODE_ORDERS_WITHOUT_ROUTING

        # --- segunda chamada: alerta activo já existe → actualiza, não insere ---
        existing_alert = inserted_after_first[0]
        # O SELECT devolve o alerta existente
        fake_session.queue_scalars([existing_alert])
        await _upsert_cpo_alert(
            fake_session,
            tenant_id,
            code=CODE_ORDERS_WITHOUT_ROUTING,
            title="5 ordens sem rota — não planeadas",
            message_pt="5 ordens ficaram fora do plano.",
            context={"unplanned_count": 5, "unplanned_orders": ["A", "B", "C", "D", "E"]},
        )

        # Continua a haver só 1 alert em session.added (nenhum novo insert)
        all_alerts = _added_alerts(fake_session)
        assert len(all_alerts) == 1, (
            f"Esperado 1 alerta (upsert), mas há {len(all_alerts)} — bug de dedup"
        )
        # O alerta existente foi actualizado com o novo contexto
        assert existing_alert.context["unplanned_count"] == 5
        assert existing_alert.title == "5 ordens sem rota — não planeadas"

    async def test_different_codes_both_inserted(self, fake_session, tenant_id):
        """Alertas de codes diferentes não se interferem."""
        # Primeiro code
        fake_session.queue_scalars([])  # SELECT → 0 rows
        await _upsert_cpo_alert(
            fake_session, tenant_id,
            code=CODE_ORDERS_WITHOUT_ROUTING,
            title="4 sem rota",
            message_pt="...",
            context={},
        )
        # Segundo code diferente
        fake_session.queue_scalars([])  # SELECT → 0 rows
        await _upsert_cpo_alert(
            fake_session, tenant_id,
            code=CODE_DURATION_FALLBACK_HIGH,
            title="Plano degradado",
            message_pt="...",
            context={},
        )

        all_alerts = _added_alerts(fake_session)
        assert len(all_alerts) == 2
        codes = {a.code for a in all_alerts}
        assert CODE_ORDERS_WITHOUT_ROUTING in codes
        assert CODE_DURATION_FALLBACK_HIGH in codes
