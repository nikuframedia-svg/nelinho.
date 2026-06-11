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
| 2026-06-04 | F1 | `_DEV_TENANT` fallback no auto_cpo_replan → log ERROR (não silencioso) | comportamento idêntico, só severidade; pytest scheduling 66 verdes | — | b066034 |
| 2026-06-04 | F2 | Dedup `get_tenant_id` (23 routers → `require_tenant_header`) | 23 importam, 1678+ testes, 5 testes 422→401 (auth correto) | `require_tenant_header` (canónico) | a19b418 |
| 2026-06-04 | B | `painel/painelApi.ts` (7k, órfão real) + funções mortas de `painelHelpers` (só `fmtEuro` vivo) | grep: painelApi só importado por painelHelpers; painelHelpers só por MoveBoatConfirm (usa `fmtEuro`); página /painel sem rota | `fmtEuro` mantido em painelHelpers | (próximo) |
| 2026-06-10 | Q.172/F4.E | 4 endpoints factory-map órfãos: `GET /v1/factory-map/{boats/{of_id},projection,line-load,kpis}` + `TrajectoryMixin` (`trajectory.py`: `boat_view`+`projection`) + 9 testes | grep frontend: só `/snapshot` (fabricaApi.ts:202) e `/shortage-risks` (supplyApi.ts:396) consumidos; zero hits p/ os 4; `boat_view`/`projection` liam camada curated vazia (ETL Fase B pendente) | `line_load()`/`kpis()` de serviço MANTIDOS (o `snapshot()` compõe-nos); guard `test_orphan_endpoints_removed` + `test_trajectory_methods_removed` | (próximo) |
| 2026-06-11 | Q.171.H/F4.E | `src/plan/services/replan_hook.py` (138 LOC) + bloco P.14 de `test_sprint_p.py` + teste de coexistência em `test_q115_d_auto_propose.py` (reduzido a auto_propose-only) | CODIGO_MORTO.md:60 já o listava; grep src/: zero callers de produção (só docstring em auto_propose.py); o replan real é o robô APScheduler Q.137 + auto_propose | auto_propose (vivo) cobre o evento config.updated | (próximo) |
| 2026-06-11 | Q.172.E | FE: `configApi`+interfaces (zero consumidores desde Q.1), `decisionsApi.execute/rollback` (advisory sem UI, ERP write fora por decisão), `BarcodeScanButton.tsx` (zero imports desde Q.52.S), `ConfigParam.tsx` (órfão da mesma família tenant-config) + exports do dark/index | re-rastreio F5.D marcou VAZIO_DESONESTO/MEIO_LIGADO; grep: zero consumidores; tsc -b 0 erros após remoção | backend /v1/config/* e advisory endpoints continuam vivos (admin-via-API) | (próximo) |

## Follow-ups (registar para não esquecer)

- **`frontend/src/lib/workforceApi.ts` — exports mortos** após d6937ce: `simulate`,
  `compareScenarios`, `getDependencyGraph`, `getCascadeImpact`, `trainingRecommendations` +
  tipos (`SimulationResult`, `WorkforceDelta`) apontam aos endpoints apagados. **Verificado:
  nenhum componente vivo os chama** (`EquipaNiveisTab` só usa sectors/operadores/níveis). Trimar
  quando o ficheiro estiver limpo do WIP Q.158/159 (agora dirty → não tocar, evitar tangle).
