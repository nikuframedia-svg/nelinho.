# DELETION_LOG — saneamento (chore/saneamento)

> Registo de tudo o que é apagado/desmontado na campanha de saneamento, com a prova de que estava
> morto/oco e o commit. Evita o "seis meses depois ninguém sabe porquê". Regra: provar antes de apagar
> (`grep` aos callers), uma categoria por commit, gates verdes.

## Plano de referência
`.claude/plans/quero-uma-analise-completa-spicy-nygaard.md` — âmbito: **A** matar mocks · **B** apagar
fachada (features ocas + 89 endpoints + 3 páginas órfãs) · clareza (F3) · **C** copiloto = ADIADO · **D**
motores/legacy = SALTADO. **Não reescrever.**

## Registo

| Data | Fase | O que saiu | Prova (grep/dados) | Stub de fronteira | Commit |
|------|------|-----------|--------------------|-------------------|--------|
| 2026-06-04 | F0 | — | baseline: verify_invariants OK, `pytest tests/plan` 1074 verdes | — | (guardrails) |
