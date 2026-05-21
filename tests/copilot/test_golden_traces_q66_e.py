"""
Q.66.E.2 — Golden trace suite (10 prompts canonicos) para o copiloto.

Motivacao
---------
O post-mortem da Anthropic (Abril 2026) avisa: "tests + dogfooding nao chegam
para apanhar drift semantico". Os testes existentes em ``tests/copilot/`` cobrem
control-flow (security flag, ollama-down, validation-failed, evidence
enforcement), mas nao garantem que, para um conjunto canonico de perguntas, o
copiloto continua a devolver uma resposta *com a forma certa* (type, intent
class, nº de facts, presenca de actions/warnings, meta keys).

Estrategia
----------
- 10 traces JSON em ``tests/copilot/golden_traces/`` — um por intent canonico:
  kpi_current, kpi_history, schedule_propose, root_cause, worker_status,
  mold_health, quality_drilldown, decision_propose, audit_query, escalation.
- Cada trace carrega: ``input`` (user_query + context window), ``canonical_llm_response``
  (resposta que o MockOllamaClient devolve para esta pergunta), e ``expected_shape``
  (asseroes estruturais).
- Nao testamos *strings exactas*. Testamos *forma*: que o copiloto preserve o
  ``type``, esteja num dos ``intent_in`` esperados, tenha summary nao-vazio,
  facts entre min/max, actions/warnings nos ranges definidos, e que ``meta``
  contenha as chaves obrigatorias.

Porque shape-only?
- Snapshot tests com strings exactas rebentam com qualquer mudanca de wording
  do LLM e geram churn de manutencao sem valor.
- Shape-based tests apanham drift semantico real: se de repente o copiloto
  comecar a devolver 0 facts para perguntas KPI, ou esquecer-se de marcar
  PROPOSAL com action, *isso* e bug; mudar "OEE de hoje" para "OEE actual"
  nao e.

Cada teste corre em <100ms (Ollama mockado, sem RAG real, sem KPI snapshot).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

import pytest

from src.copilot.schemas import CopilotAskRequest
from src.copilot.service import CopilotService


# ---------------------------------------------------------------------------
# Trace loader (corre no import-time do parametrize)
# ---------------------------------------------------------------------------

TRACES_DIR = Path(__file__).parent / "golden_traces"


def _load_traces() -> List[Path]:
    """Devolve a lista ordenada dos 10 ficheiros de trace JSON.

    A ordem alfabetica do nome (01_..., 02_..., ...) garante reproducibilidade
    do output do pytest e do report.
    """
    traces = sorted(TRACES_DIR.glob("*.json"))
    if len(traces) != 10:
        raise RuntimeError(
            f"Esperava 10 golden traces em {TRACES_DIR}, encontrei {len(traces)}."
        )
    return traces


# ---------------------------------------------------------------------------
# Fixture: copia o patched_service_deps de test_service.py, adaptado.
# ---------------------------------------------------------------------------

@pytest.fixture
def patched_copilot_deps(monkeypatch):
    """Stubs minimos para o copiloto correr sem DB/RAG/Ollama reais.

    - ``build_context_facts`` -> contexto sintetico minimo.
    - ``retrieve_rag_chunks`` -> lista vazia (sem RAG).
    - ``_fetch_kpi_snapshot`` -> None (forca fallback do fast-path para LLM).
    - ``_store_audit`` -> dict ack sem tocar na DB.
    - ``tool_registry`` -> None (skip do ToolExecutor agentico).
    - ``_resolve_semantic_queries`` -> None (skip do RLM agent).
    """

    async def _build_context(session, tenant_id, window, role, kpi_snapshot=None):
        return {
            "operational_snapshot": {
                "orders_total": 0,
                "data_status": "NO_DATA_AVAILABLE",
            },
            "quality": {},
            "plan_history": {},
            "trust_index": {"value": 0.65},
        }

    async def _retrieve_rag(session, tenant_id, query, top_k=8):
        return []

    async def _fetch_kpi_none(self):
        return None  # forca fallback do fast-path para LLM

    async def _store_audit_noop(
        self,
        correlation_id,
        suggestion_id,
        request,
        prompt,
        llm_response,
        response_dict,
        validation_passed,
        validation_errors,
        latency_ms,
    ):
        return {
            "suggestion_id": str(suggestion_id),
            "correlation_id": str(correlation_id),
            "prompt_hash": "x" * 64,
            "llm_response_hash": "y" * 64,
        }

    def _no_semantic(self):
        return None  # skip do RLM diagnostic

    monkeypatch.setattr("src.copilot.service.build_context_facts", _build_context)
    monkeypatch.setattr("src.copilot.service.retrieve_rag_chunks", _retrieve_rag)
    monkeypatch.setattr(CopilotService, "_fetch_kpi_snapshot", _fetch_kpi_none)
    monkeypatch.setattr(CopilotService, "_store_audit", _store_audit_noop)
    monkeypatch.setattr(CopilotService, "_resolve_semantic_queries", _no_semantic)
    monkeypatch.setattr(
        "src.copilot.tool_registry.get_tool_registry_sync", lambda: None
    )


def _make_service(fake_session, tenant_id) -> CopilotService:
    return CopilotService(
        session=fake_session,
        tenant_id=tenant_id,
        actor_id=uuid4(),
        actor_role="OPERATOR",
    )


def _make_request(query: str, context_window_hours: int) -> CopilotAskRequest:
    return CopilotAskRequest(
        user_query=query,
        context_window_hours=context_window_hours,
        include_citations=True,
    )


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------

def _assert_shape(response: Any, expected: Dict[str, Any], trace_id: str) -> None:
    """Asseroes estruturais derivadas do ``expected_shape`` do trace."""

    # 1. type
    assert response.type == expected["type"], (
        f"[{trace_id}] type esperado {expected['type']}, obtido {response.type}"
    )

    # 2. intent — verifica que esta num dos valores aceites (lista para tolerar
    #    coercoes do servico p.ex. quando o LLM devolve intent invalido).
    intent_in = expected["intent_in"]
    assert response.intent in intent_in, (
        f"[{trace_id}] intent {response.intent!r} nao esta em {intent_in!r}"
    )

    # 3. summary nao-vazio quando esperado
    if expected["has_summary"]:
        assert response.summary and len(response.summary.strip()) > 0, (
            f"[{trace_id}] summary deveria ser nao-vazio"
        )

    # 4. facts count range
    facts_n = len(response.facts)
    lo, hi = expected["min_facts"], expected["max_facts"]
    assert lo <= facts_n <= hi, (
        f"[{trace_id}] facts count={facts_n}, esperado entre {lo} e {hi}"
    )

    # 5. actions count range
    actions_n = len(response.actions)
    a_lo, a_hi = expected["actions_count_range"]
    assert a_lo <= actions_n <= a_hi, (
        f"[{trace_id}] actions count={actions_n}, esperado entre {a_lo} e {a_hi}"
    )

    # 6. warnings count range (inclui warnings injectados pelo evidence-enforcement)
    warnings_n = len(response.warnings)
    w_lo, w_hi = expected["warnings_count_range"]
    assert w_lo <= warnings_n <= w_hi, (
        f"[{trace_id}] warnings count={warnings_n}, esperado entre {w_lo} e {w_hi}"
    )

    # 7. meta tem todas as chaves obrigatorias
    for key in expected["meta_must_have_keys"]:
        assert key in response.meta, (
            f"[{trace_id}] meta nao tem chave obrigatoria {key!r}; tem {list(response.meta.keys())!r}"
        )

    # 8. cada fact tem >=1 citation (invariant do schema)
    for i, fact in enumerate(response.facts):
        assert len(fact.citations) >= 1, (
            f"[{trace_id}] fact[{i}] nao tem citations"
        )


# ---------------------------------------------------------------------------
# Test parametrizado
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("trace_path", _load_traces(), ids=lambda p: p.stem)
@pytest.mark.asyncio
async def test_copilot_golden_trace(
    trace_path: Path,
    fake_session,
    tenant_id,
    mock_ollama,
    patched_copilot_deps,
) -> None:
    """Para cada trace canonico: queue da resposta no MockOllama, corre
    process_ask, verifica shape estavel.
    """
    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    # Queue da resposta canonica no MockOllama (vai ser consumida pela primeira
    # chamada a ollama_client.chat dentro do process_ask).
    mock_ollama.queue_chat(trace["canonical_llm_response"])

    svc = _make_service(fake_session, tenant_id)
    req = _make_request(
        query=trace["input"]["user_query"],
        context_window_hours=trace["input"].get("context_window_hours", 24),
    )

    response, audit = await svc.process_ask(req)

    _assert_shape(response, trace["expected_shape"], trace["trace_id"])

    # Verificacoes adicionais comuns a todos os traces.
    assert audit.get("suggestion_id"), (
        f"[{trace['trace_id']}] audit nao tem suggestion_id"
    )
    assert "perf_metrics" in audit, (
        f"[{trace['trace_id']}] audit nao tem perf_metrics"
    )


# ---------------------------------------------------------------------------
# Meta-test: a propria suite tem 10 traces
# ---------------------------------------------------------------------------

def test_golden_traces_count_is_ten() -> None:
    """Sanity: a campanha Q.66.E.2 fixou 10 intents canonicos. Adicionar/remover
    um intent obriga a actualizar este teste deliberadamente (drift do contrato).
    """
    traces = _load_traces()
    assert len(traces) == 10, f"Esperava 10 traces, obtive {len(traces)}"

    # Verifica que cada ficheiro tem os campos obrigatorios.
    required_keys = {
        "trace_id",
        "intent_label",
        "input",
        "canonical_llm_response",
        "expected_shape",
        "stability_pinned_at",
    }
    for path in traces:
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = required_keys - data.keys()
        assert not missing, f"{path.name} faltam campos: {missing}"
