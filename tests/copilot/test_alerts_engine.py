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
    async def test_second_scan_with_active_alert_does_not_reinsert(
        self, fake_session, tenant_id,
    ):
        """Q.173.AR.1 — a BD garante 1 alerta ATIVO por (tenant, code)
        (constraint Q.138.I); o persist salta quando já existe um ativo,
        independentemente da idade."""
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

        # Second scan: the existing-active lookup finds the alert id → skip.
        recent = inserted_first[0]
        fake_session.queue_scalar(recent.id)
        summary_second = await engine.scan()

        assert summary_second["skipped_duplicate"] >= 1
        bottleneck_alerts = [
            a for a in _added_alerts(fake_session) if a.code == CODE_BOTTLENECK_FORMATION
        ]
        assert len(bottleneck_alerts) == 1


class TestAggregateCandidates:
    """Q.173.AR.1 — N candidatos do mesmo código colapsam num só alerta
    (a constraint da BD só permite 1 ativo por código)."""

    def test_167_barcos_viram_um_alerta(self):
        from src.copilot.alerts.engine import _aggregate_candidates

        candidates = [
            {
                "severity": "CRITICAL" if i % 3 == 0 else "WARN",
                "code": CODE_DELIVERY_RISK,
                "title": f"Risco de atraso — barco #{i}",
                "message_pt": f"O barco #{i} está atrasado.",
                "context": {"hull": i},
                "entity_refs": [f"barco:{i}"],
            }
            for i in range(167)
        ]

        out = _aggregate_candidates(candidates)

        assert len(out) == 1
        agg = out[0]
        assert agg["severity"] == "CRITICAL"  # a pior do grupo
        assert agg["context"]["count"] == 167
        assert agg["context"]["count_critical"] == 56
        assert len(agg["entity_refs"]) == 15  # amostra, não os 167
        assert "+166 casos" in agg["title"]
        assert "167 casos ativos" in agg["message_pt"]

    def test_um_candidato_passa_intacto(self):
        from src.copilot.alerts.engine import _aggregate_candidates

        single = [{
            "severity": "WARN", "code": CODE_DELIVERY_RISK,
            "title": "t", "message_pt": "m", "context": {}, "entity_refs": ["x"],
        }]
        assert _aggregate_candidates(single) == single

    def test_codigos_distintos_nao_se_misturam(self):
        from src.copilot.alerts.engine import _aggregate_candidates

        candidates = [
            {"severity": "WARN", "code": "A", "title": "a", "message_pt": "a",
             "context": {}, "entity_refs": ["a:1"]},
            {"severity": "WARN", "code": "B", "title": "b", "message_pt": "b",
             "context": {}, "entity_refs": ["b:1"]},
        ]
        assert len(_aggregate_candidates(candidates)) == 2


# ---------------------------------------------------------------------------
# Q.138.G — dedup de alertas CPO sem entity_refs (_upsert_cpo_alert)
# ---------------------------------------------------------------------------

class TestCpoAlertUpsertDedup:
    """Caracteriza o contrato Q.138.I do _upsert_cpo_alert: o dedup vive na
    BD (INSERT ... ON CONFLICT no unique partial index (tenant_id, code)
    WHERE status='active', migração 069), não em SELECT-then-INSERT na
    sessão. Estes testes provam o SHAPE do statement emitido — a garantia
    de unicidade em si é do Postgres (provada live no Q.138.I).
    """

    @staticmethod
    def _compiled(stmt) -> str:
        from sqlalchemy.dialects import postgresql

        return str(stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        ))

    async def test_upsert_emite_on_conflict_do_update_e_comita(self, tenant_id):
        from tests.conftest import FakeSession

        class _Recorder(FakeSession):
            def __init__(self) -> None:
                super().__init__()
                self.statements: list = []

            async def execute(self, stmt, *a, **kw):
                self.statements.append(stmt)
                return await super().execute(stmt, *a, **kw)

        session = _Recorder()
        session.queue_scalars([])
        await _upsert_cpo_alert(
            session,
            tenant_id,
            code=CODE_ORDERS_WITHOUT_ROUTING,
            title="4 ordens sem rota — não planeadas",
            message_pt="4 ordens ficaram fora do plano.",
            context={"unplanned_count": 4},
        )

        assert len(session.statements) == 1
        sql = self._compiled(session.statements[0])
        assert "INSERT INTO" in sql
        assert "ON CONFLICT (tenant_id, code)" in sql, (
            "dedup tem de ser no unique partial index — não SELECT-then-INSERT"
        )
        assert "status = 'active'" in sql
        assert "DO UPDATE SET" in sql
        # commit interno explícito (statement raw não marca a sessão dirty)
        assert session.commit_calls == 1

    async def test_codes_diferentes_emitem_upserts_independentes(self, tenant_id):
        """Cada code é um upsert próprio — o índice (tenant_id, code) só
        funde linhas do MESMO code; codes distintos coexistem."""
        from tests.conftest import FakeSession

        class _Recorder(FakeSession):
            def __init__(self) -> None:
                super().__init__()
                self.params: list = []

            async def execute(self, stmt, *a, **kw):
                comp = stmt.compile()
                self.params.append(dict(comp.params))
                return await super().execute(stmt, *a, **kw)

        session = _Recorder()
        session.queue_scalars([])
        await _upsert_cpo_alert(
            session, tenant_id,
            code=CODE_ORDERS_WITHOUT_ROUTING,
            title="4 sem rota", message_pt="...", context={},
        )
        session.queue_scalars([])
        await _upsert_cpo_alert(
            session, tenant_id,
            code=CODE_DURATION_FALLBACK_HIGH,
            title="Plano degradado", message_pt="...", context={},
        )

        codes = {p.get("code") for p in session.params}
        assert codes == {CODE_ORDERS_WITHOUT_ROUTING, CODE_DURATION_FALLBACK_HIGH}
        assert session.commit_calls == 2


# ---------------------------------------------------------------------------
# Q.173.M — thresholds vêm da config de tenant (categoria 'alertas')
# ---------------------------------------------------------------------------

class TestQ173MThresholdsConfiguraveis:
    _CFG = (
        "src.core.services.tenant_config_service."
        "TenantConfigService.get_category"
    )

    async def test_scan_carrega_thresholds_da_config(
        self, fake_session, tenant_id, monkeypatch,
    ):
        """Mudar o knob em Configurações muda MESMO o detector — antes as
        keys 'alertas.*' eram seeded e ignoradas (auditoria 2026-06-11)."""
        async def fake_cfg(self, category):
            assert category == "alertas"
            return {
                "bottleneck.days_threshold": 2.0,
                "quality.events_threshold": 1,
                "delivery_risk.window_days": 30,
            }

        monkeypatch.setattr(self._CFG, fake_cfg)

        sq = FakeSemanticQueries()
        # backlog 3 dias: abaixo do default 10, ACIMA do configurado 2.
        sq.set("get_bottlenecks", {
            "status": "OK",
            "rows": [{"fase_id": "40", "fase_nome": "Pintura",
                      "backlog_dias": 3.0}],
        })
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)
        await engine.scan()

        assert engine.bottleneck_days_threshold == 2.0
        assert engine.quality_events_threshold == 1
        assert engine.delivery_risk_window_days == 30
        codes = [a.code for a in _added_alerts(fake_session)]
        assert CODE_BOTTLENECK_FORMATION in codes, (
            "com threshold configurado 2.0, backlog 3.0 tem de disparar"
        )

    async def test_sem_config_fica_nos_defaults(
        self, fake_session, tenant_id, monkeypatch,
    ):
        async def boom(self, category):
            raise ValueError("config indisponível")

        monkeypatch.setattr(self._CFG, boom)

        sq = FakeSemanticQueries()
        sq.set("get_bottlenecks", {
            "status": "OK",
            "rows": [{"fase_id": "40", "fase_nome": "Pintura",
                      "backlog_dias": 3.0}],
        })
        engine = AlertsEngine(fake_session, tenant_id, semantic_queries=sq)
        await engine.scan()

        assert engine.bottleneck_days_threshold == BOTTLENECK_DAYS_THRESHOLD
        assert engine.quality_events_threshold == QUALITY_EVENTS_THRESHOLD
        # backlog 3.0 < default 10 → nada dispara
        assert CODE_BOTTLENECK_FORMATION not in [
            a.code for a in _added_alerts(fake_session)
        ]

    def test_seeds_q173m_presentes(self):
        from src.core.services.default_configs import iter_seeds

        seeds = {(c, k): (v, t) for c, k, v, t, _n in iter_seeds()}
        assert seeds[("alertas", "bottleneck.days_threshold")] == (10.0, "float")
        assert seeds[("alertas", "quality.events_threshold")] == (500, "int")
        # as keys já-existentes continuam seeded (agora finalmente lidas)
        assert seeds[("alertas", "delivery_risk.window_days")] == (3, "int")


# ---------------------------------------------------------------------------
# Plan LIVE staleness (Q.173.AR)
# ---------------------------------------------------------------------------

class TestPlanLiveStalenessDetector:
    """O loop plan-vs-actual só aprende de commits LIVE; o detector avisa
    quando ninguém aprova um plano há N dias (default 7; 2x = CRITICAL)."""

    @staticmethod
    def _engine(fake_session, tenant_id) -> AlertsEngine:
        return AlertsEngine(
            fake_session, tenant_id, semantic_queries=FakeSemanticQueries(),
        )

    async def test_nunca_houve_live_com_drafts_e_critical(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)  # sem alerta ativo deste código
        fake_session.queue_scalar(None)  # max(created_at) LIVE → nunca
        fake_session.queue_scalar(154)   # drafts acumulados
        engine = self._engine(fake_session, tenant_id)

        candidates = await engine._detect_plan_live_staleness()

        assert len(candidates) == 1
        assert candidates[0]["severity"] == "CRITICAL"
        assert candidates[0]["context"]["drafts_since_live"] == 154
        assert candidates[0]["entity_refs"] == ["plan:live-staleness"]
        assert "nunca" in candidates[0]["message_pt"]

    async def test_instalacao_nova_sem_drafts_nao_alerta(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)  # sem alerta ativo
        fake_session.queue_scalar(None)  # sem LIVE
        fake_session.queue_scalar(0)     # sem DRAFTs
        engine = self._engine(fake_session, tenant_id)

        assert await engine._detect_plan_live_staleness() == []

    async def test_live_recente_nao_alerta(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)
        fake_session.queue_scalar(datetime.now() - timedelta(days=2))
        engine = self._engine(fake_session, tenant_id)

        assert await engine._detect_plan_live_staleness() == []

    async def test_live_velho_e_warn(self, fake_session, tenant_id):
        from datetime import timezone

        # created_at é naive-UTC no modelo — construir o fixture igual
        # (datetime.now() local daria 8d−1h = 7 dias em Lisboa).
        utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        fake_session.queue_scalar(None)
        fake_session.queue_scalar(utc_naive - timedelta(days=8, hours=2))
        fake_session.queue_scalar(12)
        engine = self._engine(fake_session, tenant_id)

        candidates = await engine._detect_plan_live_staleness()

        assert len(candidates) == 1
        assert candidates[0]["severity"] == "WARN"
        assert candidates[0]["context"]["days_without_live"] == 8
        assert candidates[0]["context"]["drafts_since_live"] == 12

    async def test_live_2x_threshold_e_critical(self, fake_session, tenant_id):
        fake_session.queue_scalar(None)
        fake_session.queue_scalar(datetime.now() - timedelta(days=20))
        fake_session.queue_scalar(40)
        engine = self._engine(fake_session, tenant_id)

        candidates = await engine._detect_plan_live_staleness()

        assert len(candidates) == 1
        assert candidates[0]["severity"] == "CRITICAL"

    async def test_alerta_ativo_suprime_reemissao(self, fake_session, tenant_id):
        fake_session.queue_scalar(uuid4())  # já existe um PLAN_LIVE_STALENESS ativo
        engine = self._engine(fake_session, tenant_id)

        assert await engine._detect_plan_live_staleness() == []

    def test_seed_q173ar_presente(self):
        from src.core.services.default_configs import iter_seeds

        seeds = {(c, k): (v, t) for c, k, v, t, _n in iter_seeds()}
        assert seeds[("alertas", "plan_live.staleness_days")] == (7, "int")
