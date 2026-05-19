"""
Sprint Q.33.A.2 — testes do dispatch de diagnósticos do copiloto.

`CopilotService._handle_diagnostic_dispatch` corre, in-process, um dos 3
detectores de causa raiz (`erro_tree` / `reichenbach` / `mill_diff`) quando
a capability está wired para o tenant. Estratégia: mock do `OllamaClient`
(2 chamadas — selecção + composição) e fake dos detectores.

Cobertura:
- selecção escolhe o ErroTree → resposta ANSWER com citação `calculation`
- selecção escolhe o Reichenbach → o detector certo é despachado
- capability off → devolve None (fallback)
- tool desconhecida → devolve None (fallback)
- detector levanta → devolve None (fallback)
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from src.copilot.schemas import CopilotAskRequest
from src.copilot.service import CopilotService
from src.explain.diagnostics.reichenbach import CommonCauseResult
from src.explain.diagnostics.types import DiagnosticResult, Hypothesis, TriggerType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALL_WIRED = {
    "diagnostics.erro_tree.enabled": True,
    "diagnostics.reichenbach.enabled": True,
    "diagnostics.mill_diff.enabled": True,
}
NONE_WIRED = {k: False for k in ALL_WIRED}


def _make_service(fake_session, tenant_id) -> CopilotService:
    return CopilotService(
        session=fake_session,
        tenant_id=tenant_id,
        actor_id=uuid4(),
        actor_role="OPERATOR",
    )


def _make_request(query: str) -> CopilotAskRequest:
    return CopilotAskRequest(
        user_query=query,
        conversation_id=None,
        context_window_hours=24,
        include_citations=True,
    )


def _patch_flags(monkeypatch, flags: dict) -> None:
    async def _fake_flags(session, tenant_id):
        return dict(flags)

    monkeypatch.setattr(
        "src.copilot.prompts.capabilities.fetch_capability_flags", _fake_flags,
    )


class _FakeErroTree:
    """ErroTreeDetector stub — devolve um DiagnosticResult com causa raiz."""

    captured: dict = {}

    def __init__(self, session, tenant_id):
        pass

    async def investigate(self, *, trigger, period_days=7, phase_id=None):
        _FakeErroTree.captured = {
            "trigger": trigger, "period_days": period_days, "phase_id": phase_id,
        }
        return DiagnosticResult(
            root_cause=Hypothesis(
                type="mold_degradation",
                entity="Molde K1-A",
                alpha=8.0,
                beta=2.0,
                evidence=["Taxa de erro subiu de 4% para 11% em 7 dias"],
            ),
            chain=["Molde K1-A degradou", "→ retrabalho na Laminagem"],
            steps_checked=[{"step": "mold", "result": "FOUND"}],
            recommendation={"action": "inspecionar molde K1-A", "priority": "high"},
        )


class _FakeReichenbach:
    captured: dict = {}

    def __init__(self, session, tenant_id):
        pass

    async def find_common_cause(self, *, deviating_phases, period_days=7):
        _FakeReichenbach.captured = {
            "deviating_phases": deviating_phases, "period_days": period_days,
        }
        return CommonCauseResult(
            common_causes=[
                Hypothesis(
                    type="shared_mold",
                    entity="Molde partilhado X",
                    alpha=7.0,
                    beta=3.0,
                    evidence=["3 barcos passaram pelas 2 fases com o mesmo molde"],
                ),
            ],
            independent_causes=[],
            verdict="common_cause",
            checks_run=[{"step": "shared_mold", "result": "FOUND"}],
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDiagnosticDispatch:
    async def test_erro_tree_dispatch_answers_with_calculation_citation(
        self, fake_session, tenant_id, monkeypatch, mock_ollama,
    ):
        """Pergunta de queda de qualidade → ErroTree corre → ANSWER com
        causa raiz real e citação `calculation`."""
        _patch_flags(monkeypatch, ALL_WIRED)
        monkeypatch.setattr(
            "src.explain.diagnostics.erro_tree.ErroTreeDetector", _FakeErroTree,
        )
        # 1ª chamada — selecção; 2ª chamada — composição.
        mock_ollama.queue_chat({
            "tool": "investigate_quality_drop",
            "params": {"trigger": "quality_drop", "period_days": 7},
        })
        mock_ollama.queue_chat({
            "summary": "O molde K1-A degradou.",
            "answer": (
                "O OEE caiu porque o molde K1-A está degradado — a taxa de "
                "erro subiu de 4% para 11%. Recomendo inspeccionar o molde."
            ),
        })

        svc = _make_service(fake_session, tenant_id)
        result = await svc._handle_diagnostic_dispatch(
            _make_request("Porque é que a qualidade caiu na Laminagem?"),
            uuid4(),
            time.time(),
        )

        assert result is not None
        response, audit = result
        assert response.type == "ANSWER"
        assert "K1-A" in response.facts[0].text
        assert response.facts[0].citations[0].source_type == "calculation"
        assert response.meta.get("diagnostic_tool") == "investigate_quality_drop"
        assert response.meta.get("diagnostic_detector") == "erro_tree"
        # O detector recebeu o trigger tipado, não a string crua.
        assert _FakeErroTree.captured["trigger"] == TriggerType.QUALITY_DROP

    async def test_reichenbach_dispatch_routes_to_common_cause(
        self, fake_session, tenant_id, monkeypatch, mock_ollama,
    ):
        """Selecção `find_common_cause` → o ReichenbachDetector é despachado
        com as fases que drift."""
        _patch_flags(monkeypatch, ALL_WIRED)
        monkeypatch.setattr(
            "src.explain.diagnostics.reichenbach.ReichenbachDetector",
            _FakeReichenbach,
        )
        mock_ollama.queue_chat({
            "tool": "find_common_cause",
            "params": {"deviating_phases": ["LAMINAGEM", "CURA"], "period_days": 7},
        })
        mock_ollama.queue_chat({
            "summary": "Molde partilhado.",
            "answer": "As duas fases drift juntas por causa de um molde partilhado.",
        })

        svc = _make_service(fake_session, tenant_id)
        result = await svc._handle_diagnostic_dispatch(
            _make_request("As fases Laminagem e Cura pioraram — qual a causa comum?"),
            uuid4(),
            time.time(),
        )

        assert result is not None
        response, _ = result
        assert response.meta.get("diagnostic_detector") == "reichenbach"
        assert _FakeReichenbach.captured["deviating_phases"] == ["LAMINAGEM", "CURA"]

    async def test_capability_off_returns_none(
        self, fake_session, tenant_id, monkeypatch,
    ):
        """Nenhuma capability wired → devolve None sem chamar o LLM."""
        _patch_flags(monkeypatch, NONE_WIRED)

        svc = _make_service(fake_session, tenant_id)
        result = await svc._handle_diagnostic_dispatch(
            _make_request("Porque caiu o OEE?"),
            uuid4(),
            time.time(),
        )
        assert result is None

    async def test_unknown_tool_returns_none(
        self, fake_session, tenant_id, monkeypatch, mock_ollama,
    ):
        """O LLM escolhe uma tool inexistente → fallback (None)."""
        _patch_flags(monkeypatch, ALL_WIRED)
        mock_ollama.queue_chat({"tool": "frobnicate", "params": {}})

        svc = _make_service(fake_session, tenant_id)
        result = await svc._handle_diagnostic_dispatch(
            _make_request("Porque caiu o OEE?"),
            uuid4(),
            time.time(),
        )
        assert result is None

    async def test_detector_raises_returns_none(
        self, fake_session, tenant_id, monkeypatch, mock_ollama,
    ):
        """O detector levanta → `_dispatch_diagnostic_detector` apanha e o
        handler devolve None (cai no fallback)."""
        _patch_flags(monkeypatch, ALL_WIRED)

        class _BoomErroTree:
            def __init__(self, session, tenant_id):
                pass

            async def investigate(self, *, trigger, period_days=7, phase_id=None):
                raise RuntimeError("repositório indisponível")

        monkeypatch.setattr(
            "src.explain.diagnostics.erro_tree.ErroTreeDetector", _BoomErroTree,
        )
        mock_ollama.queue_chat({
            "tool": "investigate_quality_drop",
            "params": {"trigger": "quality_drop"},
        })

        svc = _make_service(fake_session, tenant_id)
        result = await svc._handle_diagnostic_dispatch(
            _make_request("Porque caiu o OEE?"),
            uuid4(),
            time.time(),
        )
        assert result is None
