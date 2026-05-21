"""Q.68.D1 — tests para `settings.model_for(task)` (per-task LLM override).

A motivação é permitir benchmark multi-modelo (Q.68.D2) sem reescrever os
3 callers (`service.py:call_llm_for_intent`, `fact_pack_builder._rlm_llm`,
e a entry de auditoria do mesmo). Cada call site declara a sua tarefa
(``chat`` / ``classify`` / ``tool_dispatch``); a config decide o modelo.

Comportamento contratado:
    1. Sem env vars / sem override → todas as tarefas devolvem `ollama_model`.
    2. Override por env var só afecta a tarefa correspondente.
    3. Override `None` (em vez de string vazia) também cai-back.
    4. Tarefa desconhecida cai-back para `ollama_model`.

Estes 4 testes formam a baseline contractual; Q.68.D2 (benchmark) parte
do princípio que estes invariantes valem.
"""

from __future__ import annotations

from src.shared.config import Settings


def _make_settings(**overrides) -> Settings:
    """Constrói Settings com defaults seguros + overrides explícitos.

    Evita herdar env vars do shell que possam contaminar o teste — cada
    teste declara exactamente o que quer ver.
    """
    base = {
        "database_url": "postgresql+asyncpg://test:test@localhost/test",
        "secret_key": "test-secret-key-32-chars-minimum-aaaaaa",
        "ollama_model": "gemma4:e4b",
        "copilot_model_chat": None,
        "copilot_model_tool_dispatch": None,
        "copilot_model_classify": None,
    }
    base.update(overrides)
    return Settings(**base)


def test_default_falls_back_to_ollama_model():
    """Sem nenhum override → todas as tarefas resolvem para `ollama_model`.

    Esta é a invariante crítica: se a config não diz nada, o sistema
    continua a usar o modelo global (preservação de comportamento Q.66
    enquanto o benchmark Q.68.D2 ainda não decidiu o vencedor).
    """
    s = _make_settings()
    assert s.model_for("chat") == "gemma4:e4b"
    assert s.model_for("classify") == "gemma4:e4b"
    assert s.model_for("tool_dispatch") == "gemma4:e4b"


def test_chat_override_only_affects_chat():
    """`copilot_model_chat=X` afecta `chat`, não `classify` nem
    `tool_dispatch` — overrides são per-task, sem leak entre tarefas.
    """
    s = _make_settings(copilot_model_chat="qwen3.5:9b")
    assert s.model_for("chat") == "qwen3.5:9b"
    assert s.model_for("classify") == "gemma4:e4b"
    assert s.model_for("tool_dispatch") == "gemma4:e4b"


def test_three_independent_overrides():
    """Os 3 overrides podem coexistir — cada tarefa resolve para o seu."""
    s = _make_settings(
        copilot_model_chat="qwen3.5:9b",
        copilot_model_classify="qwen2.5vl:7b",
        copilot_model_tool_dispatch="gemma4:e4b",
    )
    assert s.model_for("chat") == "qwen3.5:9b"
    assert s.model_for("classify") == "qwen2.5vl:7b"
    assert s.model_for("tool_dispatch") == "gemma4:e4b"
    # `ollama_model` continua intacto — é fallback, não é apagado.
    assert s.ollama_model == "gemma4:e4b"


def test_unknown_task_falls_back_to_ollama_model():
    """Tarefa nova (ex: ``embeddings``) cai-back para `ollama_model`
    em vez de crashar. Defensivo — callers podem adicionar tarefas sem
    precisar de adicionar fields à config no mesmo PR.
    """
    s = _make_settings(copilot_model_chat="qwen3.5:9b")
    assert s.model_for("embeddings") == "gemma4:e4b"
    assert s.model_for("") == "gemma4:e4b"
    assert s.model_for("anything_else") == "gemma4:e4b"
