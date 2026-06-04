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
| 2026-06-04 | F0 | — | baseline: verify_invariants OK, `pytest tests/plan` 1074 verdes | — | c1ad10f |
| 2026-06-04 | F1/B | Feature órfã workforce: `api.py`(512)+`service.py`(839) — dependency-graph, cascade-impact, simulate, training-recommendations, **scenarios/compare (custos fabricados 440/880/2000€)**, `spof=3` fallback, `_get_mock_*`, allocations · + 3 testes | 0 callers backend (`grep`); 0 páginas vivas (só `EquipaNiveisTab` importa `workforceApi` e usa só sectors/operadores/níveis — reais); `risks/spof`/`simulate`/etc. nunca chamados | nenhum (sem callers); `models.py` mantido (model_registry); sub-routers sector/operators/employees intactos | d6937ce |
| 2026-06-04 | F2 | Dedup `_safe_float` (5 cópias ml→`src/shared/coerce.py`) | comportamento idêntico (import as `_safe_float`); pytest ml verde | — | 37b3a82 |
| 2026-06-04 | F2 | Dedup `_clamp` (4 jobs scheduler→`src/shared/coerce.clamp`) | idêntico; `dqa/trust_v2._clamp` deixado (ficheiro delicado) | — | 405715a |

## Follow-ups (registar para não esquecer)

- **`frontend/src/lib/workforceApi.ts` — exports mortos** após d6937ce: `simulate`,
  `compareScenarios`, `getDependencyGraph`, `getCascadeImpact`, `trainingRecommendations` +
  tipos (`SimulationResult`, `WorkforceDelta`) apontam aos endpoints apagados. **Verificado:
  nenhum componente vivo os chama** (`EquipaNiveisTab` só usa sectors/operadores/níveis). Trimar
  quando o ficheiro estiver limpo do WIP Q.158/159 (agora dirty → não tocar, evitar tangle).
