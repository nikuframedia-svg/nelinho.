# src/copilot

**Propósito: LLM-based assistant (Gemma na RTX 5060 Ti). Chat + tools dispatch + RAG + escalação. Q.17 rules `requires_human_approval=True`.**

## Invariantes locais (always-true neste módulo)

- ZERO MOCKS no frontend (chat/copilot UI). Backend pode usar `AsyncMock` em unit tests.
- LLM NUNCA opt-out de write-gate / human approval (Pydantic `Literal[True]` no schema Q.17).
- Dispatchers usam `_stubbed_or_ok()` helper — NUNCA `status="ok"` string literal (bug Q.17.F.1 risk #5).
- `ollama_client.py` tem circuit breaker — toda a chamada Ollama passa por lá.
- LLM com `format='json'` exige fallback retry (parse failure → retry sem `format='json'`).
- Gemma é thinking model: `think:false` no payload (Q.32 lesson — `think:true` custava ~22s descartados).

## Quando entrar aqui, lê primeiro

- `service.py` — 1708L god-file (Q.66.D.2 vai decompor). Carregar antes de qualquer edit.
- `api.py` — endpoints `/v1/copilot/*`.
- `conversation_store.py` — Redis com fallback in-memory.
- `tool_registry.py` + `tool_executor.py` — dispatch matrix.
- `rag.py` — RAG sobre `copilot_rag_chunk` (pgvector quando disponível).

## Comandos

```powershell
.\.venv\Scripts\python.exe -m pytest tests/copilot/ -q
.\.venv\Scripts\python.exe scripts/e2e_llm_smoke.py
```

## Anti-padrões deste módulo

- NÃO editar `service.py` em >5 sítios num turn — god-file frágil, vai partir até Q.66.D.2 decompor.
- NÃO chamar Ollama direct sem passar pelo `ollama_client.circuit_breaker`.
- NÃO usar `format='json'` sem retry path quando o parse falha.
- NÃO popular fact_packs / tools sem actualizar `tool_registry.py` (drift entre LLM prompt e dispatcher real).
- NÃO baixar `num_predict` para "compensar" thinking lento — fixa com `think:false`.

## Referências

- `agent_docs/q17_logic_as_data.md` — 12 events × 9 actions × 8 ops whitelist.
- MEMORY: `copilot_data_plumbing.md`, `e2e_llm_harness.md`, `project_copilot_thinking_model.md`.
