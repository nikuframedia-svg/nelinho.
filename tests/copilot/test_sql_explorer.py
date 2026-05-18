"""Q.39 — guardrails do `sql_explorer`.

A ferramenta dá ao copiloto SQL contra a BD toda — Postgres + ERP NELO.
A única coisa que a torna segura é `validate_readonly_sql`: tem de
recusar tudo o que escreva ou encadeie instruções. Estes testes são o
contrato dessa recusa. `run_query`/`list_schema` precisam de BD/ERP
reais e correm no passo de integração.
"""

from __future__ import annotations

import pytest

from src.copilot.tools.sql_explorer import (
    UnsafeQueryError,
    _norm,
    _token_match,
    validate_readonly_sql,
)


# ── aceita leitura ────────────────────────────────────────────────────────


def test_accepts_plain_select():
    sql = "SELECT count(*) FROM plan.production_orders"
    assert validate_readonly_sql(sql) == sql


def test_accepts_with_cte():
    sql = (
        "WITH t AS (SELECT of_id FROM factory_curated.order_phase) "
        "SELECT count(*) FROM t"
    )
    assert validate_readonly_sql(sql) == sql


def test_accepts_select_with_replace_function():
    """`REPLACE()` é função de string read-only — não pode ser recusada."""
    sql = "SELECT REPLACE(erro_tipo, 'x', 'y') FROM factory_curated.quality_event"
    assert validate_readonly_sql(sql) == sql


def test_strips_trailing_semicolon_and_comments():
    cleaned = validate_readonly_sql(
        "SELECT 1 FROM core.products -- comentário\n;"
    )
    assert cleaned == "SELECT 1 FROM core.products"
    assert ";" not in cleaned


def test_accepts_lowercase_and_leading_whitespace():
    assert validate_readonly_sql("   select 1  ") == "select 1"


# ── recusa escrita ────────────────────────────────────────────────────────


def test_rejects_insert():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("INSERT INTO core.products VALUES (1)")


def test_rejects_update():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("UPDATE core.products SET nome = 'x'")


def test_rejects_delete():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("DELETE FROM core.products")


def test_rejects_drop():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("DROP TABLE core.products")


def test_rejects_truncate():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("TRUNCATE core.products")


def test_rejects_select_into():
    """`SELECT … INTO` escreve uma tabela nova — recusado."""
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("SELECT * INTO copia FROM core.products")


def test_rejects_stacked_statements():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("SELECT 1; DROP TABLE core.products")


def test_rejects_write_hidden_in_comment_then_stacked():
    """Uma instrução proibida escondida depois de um comentário + ';'."""
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql(
            "SELECT 1 /* ok */; UPDATE core.products SET nome='x'"
        )


def test_rejects_grant():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("GRANT SELECT ON core.products TO public")


def test_rejects_exec_procedure():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("EXEC sp_who")


def test_rejects_empty():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("")


def test_rejects_non_select_start():
    with pytest.raises(UnsafeQueryError):
        validate_readonly_sql("EXPLAIN ANALYZE SELECT 1")


# ── intent: data_query ────────────────────────────────────────────────────


@pytest.mark.parametrize("query", [
    "quantos barcos K1 fizemos em Abril?",
    "lista os 10 moldes com mais defeitos",
    "qual o histórico de transportes da última semana",
    "mostra-me o ranking de operadores por horas",
])
def test_data_query_intent_detected(query):
    """Perguntas de consulta/exploração da BD → intent data_query."""
    from src.copilot.service import CopilotService

    svc = CopilotService.__new__(CopilotService)
    assert svc._detect_intent(query) == "data_query"


@pytest.mark.parametrize("query", [
    "porque caiu o throughput?",   # diagnostic ganha
    "qual é o OEE atual?",         # kpi ganha
    "olá",                          # smalltalk ganha
    "mostra-me o FPY",              # kpi-curto ganha (métrica)
])
def test_data_query_does_not_steal_other_intents(query):
    """data_query não pode roubar perguntas de diagnóstico, KPI-atual
    ou smalltalk."""
    from src.copilot.service import CopilotService

    svc = CopilotService.__new__(CopilotService)
    assert svc._detect_intent(query) != "data_query"


@pytest.mark.parametrize("query", [
    "quantos rework entries existem?",          # 'rework' não o torna KPI
    "quantas leituras de qualidade há no ERP?",
    "lista os 10 tipos de erro mais comuns",
])
def test_count_questions_beat_kpi_intent(query):
    """Q.39 — uma pergunta de CONTAGEM ('quantos…') é data_query mesmo
    quando menciona uma palavra de KPI; não pode cair no fast-path KPI."""
    from src.copilot.service import CopilotService

    svc = CopilotService.__new__(CopilotService)
    assert svc._detect_intent(query) == "data_query"


@pytest.mark.parametrize("query", [
    "qual a fase com mais erros de retrabalho?",
    "qual o produto com mais ordens de fabrico?",
    "quantos quality events por mês na curated?",
    "qual a temperatura média nas leituras IoT?",
])
def test_aggregation_questions_route_to_data_query(query):
    """Agregações ('com mais', 'por mês', 'média') → data_query."""
    from src.copilot.service import CopilotService

    svc = CopilotService.__new__(CopilotService)
    assert svc._detect_intent(query) == "data_query"


# ── selecção léxica de tabelas (rede de segurança) ────────────────────────


def test_norm_strips_accents_and_punctuation():
    assert _norm("Produção, à FÁBRICA!") == "producao a fabrica"


@pytest.mark.parametrize("a,b", [
    ("batch", "batches"),       # plural por sufixo
    ("template", "templates"),
    ("schedule", "schedules"),
    ("firing", "firings"),
])
def test_token_match_handles_plurals(a, b):
    assert _token_match(a, b)


def test_token_match_rejects_unrelated():
    assert not _token_match("mold", "order")
    assert not _token_match("rule", "produto")
