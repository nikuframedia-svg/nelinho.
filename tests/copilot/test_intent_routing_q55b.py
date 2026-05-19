"""
Q.55.B.2 — routing de intent em PT-PT + o RLM não rouba a pergunta quando
a camada semântica está vazia.

`_detect_intent` era estreito e em inglês: "gargalo" (a pergunta de
diagnóstico mais comum do chefe de turno) e "retrabalho" não disparavam o
intent `diagnostic`. E o agente RLM corria mesmo sobre um `IngestEngine`
vazio, devolvendo "não tenho dados" e roubando a pergunta ao caminho LLM
que — pós-Q.55.B.1 — tem os dados operacionais reais.
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest

from src.copilot.schemas import CopilotAskRequest
from src.copilot.service import CopilotService
from tests.conftest import FakeSession

TENANT = uuid4()


def _svc() -> CopilotService:
    return CopilotService(
        session=FakeSession(), tenant_id=TENANT, actor_id=uuid4(), actor_role="ADMIN",
    )


# ─── _detect_intent — vocabulário PT-PT ──────────────────────────────────


@pytest.mark.parametrize("query", [
    "Onde está o gargalo na fábrica hoje?",
    "A Laminagem está a estrangular a linha",
    "Temos um estrangulamento na Pintura",
])
def test_perguntas_de_gargalo_sao_diagnostic(query):
    assert _svc()._detect_intent(query) == "diagnostic"


@pytest.mark.parametrize("query", [
    "porque disparou o retrabalho",
    "o retrabalho piorou esta semana",
])
def test_retrabalho_com_verbo_de_subida_e_diagnostic(query):
    assert _svc()._detect_intent(query) == "diagnostic"


def test_routing_existente_nao_regride():
    """A adição PT-PT não mexe no que já estava a funcionar."""
    svc = _svc()
    assert svc._detect_intent("Qual é o OEE atual?") == "kpi_current"
    assert svc._detect_intent("o que mudou na produção") == "diagnostic"
    assert svc._detect_intent("investigar a causa do atraso") == "diagnostic"
    assert svc._detect_intent("random query about nothing") == "generic"


# ─── RLM não corre com a camada semântica vazia ──────────────────────────


@pytest.mark.asyncio
async def test_rlm_diagnostic_salta_quando_camada_semantica_vazia(monkeypatch):
    """Sem camada semântica, `_handle_rlm_diagnostic` devolve None — o
    chamador cai no caminho LLM com o contexto operacional real."""
    svc = _svc()
    monkeypatch.setattr(
        CopilotService, "_resolve_semantic_queries", lambda self: None,
    )

    result = await svc._handle_rlm_diagnostic(
        CopilotAskRequest(user_query="Onde está o gargalo?"),
        correlation_id=uuid4(),
        start_time=time.time(),
    )
    assert result is None
