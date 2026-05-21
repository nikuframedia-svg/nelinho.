"""Sprint Q.53.F — gráficos no copiloto.

Cobre os três blocos novos:

* :class:`ChartSpec` — schema Pydantic (closed whitelist de ``type``,
  ``data`` não-vazia, ``CopilotResponse`` aceita ``charts[]``).
* :func:`normalize_charts` — guardrail que descarta gráficos malformados
  sem rebentar a resposta (mesmo princípio de actions).
* :func:`extract_chart_blocks` + ``process_ask`` — o LLM emite gráficos
  no campo ``charts[]`` ou em blocos ``<chart>...</chart>``; ambos chegam
  validados ao :class:`CopilotResponse`.

ZERO MOCKS de dados: os gráficos usam os números que o LLM já tinha no
contexto; estes testes verificam o pipeline, não inventam séries.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.copilot.guardrails import normalize_charts, ALLOWED_CHART_TYPES
from src.copilot.schemas import ChartSpec, CopilotResponse
from src.copilot.service import CopilotService, extract_chart_blocks


# ---------------------------------------------------------------------------
# ChartSpec schema
# ---------------------------------------------------------------------------

class TestChartSpecSchema:
    def test_valid_line_chart(self):
        spec = ChartSpec(
            type="line",
            title="Throughput por dia",
            data=[{"x": "Seg", "y": 31200}, {"x": "Ter", "y": 28400}],
            config={"x_label": "Dia", "y_label": "€"},
        )
        assert spec.type == "line"
        assert len(spec.data) == 2

    def test_config_defaults_to_empty_dict(self):
        spec = ChartSpec(type="bar", title="X", data=[{"x": "a", "y": 1}])
        assert spec.config == {}

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            ChartSpec(type="pie", title="X", data=[{"x": 1, "y": 2}])

    def test_empty_data_rejected(self):
        """Um gráfico sem dados não é um gráfico — min_items=1."""
        with pytest.raises(ValidationError):
            ChartSpec(type="line", title="X", data=[])

    def test_empty_title_rejected(self):
        with pytest.raises(ValidationError):
            ChartSpec(type="gauge", title="", data=[{"value": 18.7}])

    def test_all_five_chart_types_accepted(self):
        for t in ("line", "bar", "gauge", "scatter", "heatmap"):
            spec = ChartSpec(type=t, title=f"{t} chart", data=[{"v": 1}])
            assert spec.type == t

    def test_whitelist_matches_schema_literal(self):
        """A whitelist do guardrail tem de espelhar o Literal do schema."""
        assert ALLOWED_CHART_TYPES == {"line", "bar", "gauge", "scatter", "heatmap"}


class TestCopilotResponseCharts:
    def _base(self, **kw):
        defaults = dict(
            suggestion_id=uuid4(),
            correlation_id=uuid4(),
            type="ANSWER",
            intent="generic",
            summary="Resumo",
            facts=[{
                "text": "Facto",
                "citations": [{
                    "source_type": "db", "ref": "t:1", "label": "L",
                    "confidence": 0.9, "trust_index": 0.9,
                }],
            }],
        )
        defaults.update(kw)
        return CopilotResponse(**defaults)

    def test_charts_defaults_to_empty_list(self):
        resp = self._base()
        assert resp.charts == []

    def test_charts_field_accepts_chartspec(self):
        resp = self._base(charts=[{
            "type": "bar",
            "title": "Retrabalho por fase",
            "data": [{"x": "Lixagem", "y": 49}],
            "config": {},
        }])
        assert len(resp.charts) == 1
        assert resp.charts[0].type == "bar"


# ---------------------------------------------------------------------------
# normalize_charts guardrail
# ---------------------------------------------------------------------------

class TestNormalizeCharts:
    def test_none_yields_empty(self):
        charts, warnings = normalize_charts(None)
        assert charts == []
        assert warnings == []

    def test_non_list_is_rejected_with_warning(self):
        charts, warnings = normalize_charts({"type": "line"})
        assert charts == []
        assert len(warnings) == 1

    def test_valid_chart_survives(self):
        charts, warnings = normalize_charts([{
            "type": "line",
            "title": "Throughput",
            "data": [{"x": "Seg", "y": 31200}],
            "config": {"unit": "€"},
        }])
        assert len(charts) == 1
        assert warnings == []
        assert charts[0]["type"] == "line"

    def test_invalid_type_dropped_not_raised(self):
        """Gráfico malformado é descartado, nunca rebenta a resposta."""
        charts, warnings = normalize_charts([
            {"type": "pie", "title": "Bad", "data": [{"x": 1}]},
            {"type": "bar", "title": "Good", "data": [{"x": "a", "y": 1}]},
        ])
        assert len(charts) == 1
        assert charts[0]["title"] == "Good"
        assert len(warnings) == 1

    def test_empty_data_chart_dropped(self):
        charts, warnings = normalize_charts([
            {"type": "line", "title": "Empty", "data": []},
        ])
        assert charts == []
        assert len(warnings) == 1

    def test_non_dict_entry_dropped(self):
        charts, warnings = normalize_charts(["just a string", 42])
        assert charts == []
        assert len(warnings) == 2

    def test_missing_config_defaults_to_empty(self):
        charts, _ = normalize_charts([
            {"type": "gauge", "title": "OEE", "data": [{"value": 18.7}]},
        ])
        assert charts[0]["config"] == {}


# ---------------------------------------------------------------------------
# extract_chart_blocks — charts[] + <chart> blocks
# ---------------------------------------------------------------------------

class TestExtractChartBlocks:
    def test_reads_charts_field(self):
        resp = {"charts": [{"type": "line", "title": "X", "data": [{"x": 1}]}]}
        out = extract_chart_blocks(resp)
        assert len(out) == 1
        assert out[0]["type"] == "line"

    def test_no_charts_yields_empty(self):
        out = extract_chart_blocks({"summary": "sem gráficos aqui"})
        assert out == []

    def test_extracts_chart_block_from_summary(self):
        resp = {
            "summary": (
                'Tendência boa. <chart>{"type": "line", "title": "T", '
                '"data": [{"x": "Seg", "y": 100}]}</chart> Fim.'
            ),
        }
        out = extract_chart_blocks(resp)
        assert len(out) == 1
        assert out[0]["title"] == "T"
        # Bloco removido do texto para não aparecer cru.
        assert "<chart>" not in resp["summary"]
        assert "Tendência boa." in resp["summary"]

    def test_extracts_chart_block_from_fact_text(self):
        resp = {
            "facts": [{
                "text": '<chart>{"type": "bar", "title": "B", "data": [{"x": "a", "y": 1}]}</chart>',
                "citations": [],
            }],
        }
        out = extract_chart_blocks(resp)
        assert len(out) == 1
        assert out[0]["type"] == "bar"
        assert "<chart>" not in resp["facts"][0]["text"]

    def test_invalid_json_block_ignored(self):
        resp = {"summary": "<chart>{not valid json}</chart>"}
        out = extract_chart_blocks(resp)
        assert out == []

    def test_combines_charts_field_and_blocks(self):
        resp = {
            "charts": [{"type": "gauge", "title": "G", "data": [{"value": 1}]}],
            "summary": '<chart>{"type": "line", "title": "L", "data": [{"x": 1}]}</chart>',
        }
        out = extract_chart_blocks(resp)
        assert len(out) == 2
        types = {c["type"] for c in out}
        assert types == {"gauge", "line"}


# ---------------------------------------------------------------------------
# End-to-end através de process_ask
# ---------------------------------------------------------------------------

def _make_service(fake_session, tenant_id) -> CopilotService:
    return CopilotService(
        session=fake_session,
        tenant_id=tenant_id,
        actor_id=uuid4(),
        actor_role="OPERATOR",
    )


@pytest.fixture
def patched_charts_deps(monkeypatch):
    """Stub as dependências externas do process_ask (contexto, RAG, audit,
    tool registry) — espelha o `patched_charts_deps` de test_service.py
    mas vive aqui para o ficheiro ser auto-suficiente."""

    async def _build_context(session, tenant_id, window, role, kpi_snapshot=None):
        return {
            "operational_snapshot": {"orders_total": 0, "data_status": "NO_DATA_AVAILABLE"},
            "quality": {},
            "plan_history": {},
            "trust_index": {"value": 0.65},
        }

    async def _retrieve_rag(session, tenant_id, query, top_k=8):
        return []

    async def _fetch_kpi_none(self):
        return None

    async def _store_audit_noop(
        self, correlation_id, suggestion_id, request, prompt,
        llm_response, response_dict, validation_passed, validation_errors, latency_ms,
    ):
        return {
            "suggestion_id": str(suggestion_id),
            "correlation_id": str(correlation_id),
            "prompt_hash": "x" * 64,
            "llm_response_hash": "y" * 64,
        }

    monkeypatch.setattr("src.copilot.service.build_context_facts", _build_context)
    monkeypatch.setattr("src.copilot.service.retrieve_rag_chunks", _retrieve_rag)
    monkeypatch.setattr(CopilotService, "_fetch_kpi_snapshot", _fetch_kpi_none)
    monkeypatch.setattr(CopilotService, "_store_audit", _store_audit_noop)
    monkeypatch.setattr("src.copilot.tool_registry.get_tool_registry_sync", lambda: None)


class TestProcessAskCharts:
    async def test_llm_charts_field_reaches_response(
        self, fake_session, tenant_id, patched_charts_deps, mock_ollama,
        valid_llm_response_factory,
    ):
        from src.copilot.schemas import CopilotAskRequest

        svc = _make_service(fake_session, tenant_id)
        llm_resp = valid_llm_response_factory(intent="generic")
        llm_resp["charts"] = [{
            "type": "line",
            "title": "Throughput por dia",
            "data": [{"x": "Seg", "y": 31200}, {"x": "Ter", "y": 28400}],
            "config": {"unit": "€"},
        }]
        mock_ollama.queue_chat(llm_resp)

        req = CopilotAskRequest(user_query="evolução do throughput esta semana")
        resp, _ = await svc.process_ask(req)

        assert resp.type == "ANSWER"
        assert len(resp.charts) == 1
        assert resp.charts[0].type == "line"
        assert resp.charts[0].title == "Throughput por dia"

    async def test_malformed_chart_dropped_response_still_ok(
        self, fake_session, tenant_id, patched_charts_deps, mock_ollama,
        valid_llm_response_factory,
    ):
        """Um gráfico inválido do LLM não rebenta a resposta."""
        from src.copilot.schemas import CopilotAskRequest

        svc = _make_service(fake_session, tenant_id)
        llm_resp = valid_llm_response_factory(intent="generic")
        llm_resp["charts"] = [
            {"type": "pie", "title": "Inválido", "data": [{"x": 1}]},
            {"type": "bar", "title": "Válido", "data": [{"x": "a", "y": 1}]},
        ]
        mock_ollama.queue_chat(llm_resp)

        req = CopilotAskRequest(user_query="compara o retrabalho por fase")
        resp, _ = await svc.process_ask(req)

        assert resp.type == "ANSWER"
        assert len(resp.charts) == 1
        assert resp.charts[0].title == "Válido"

    async def test_no_charts_yields_empty_list(
        self, fake_session, tenant_id, patched_charts_deps, mock_ollama,
        valid_llm_response_factory,
    ):
        from src.copilot.schemas import CopilotAskRequest

        svc = _make_service(fake_session, tenant_id)
        mock_ollama.queue_chat(valid_llm_response_factory(intent="generic"))

        req = CopilotAskRequest(user_query="quantos K1 estão em Laminagem")
        resp, _ = await svc.process_ask(req)

        assert resp.type == "ANSWER"
        assert resp.charts == []

    async def test_chart_block_in_summary_extracted_and_stripped(
        self, fake_session, tenant_id, patched_charts_deps, mock_ollama,
        valid_llm_response_factory,
    ):
        from src.copilot.schemas import CopilotAskRequest

        svc = _make_service(fake_session, tenant_id)
        llm_resp = valid_llm_response_factory(intent="generic")
        llm_resp["summary"] = (
            'Throughput em queda. '
            '<chart>{"type": "line", "title": "Throughput", '
            '"data": [{"x": "Seg", "y": 31000}]}</chart>'
        )
        mock_ollama.queue_chat(llm_resp)

        req = CopilotAskRequest(user_query="tendência do throughput")
        resp, _ = await svc.process_ask(req)

        assert resp.type == "ANSWER"
        assert len(resp.charts) == 1
        assert resp.charts[0].type == "line"
        # O bloco cru não vaza para o summary apresentado ao utilizador.
        assert "<chart>" not in resp.summary
