# Q.131 — Planeamento sobre dados REAIS (porta+verifica Q.126) · REPORT

**Branch:** `feat/q131-cpo-real-data` (de `feat/q130-bugfix-sweep` @ `546bc46`).
**Objetivo (Luis):** planeamento como produto a sério, 0 demo, sobre dados reais do ERP.

## Q.131.A — Porta Q.126 Stream 1 + reconcilia Q.130.1 (commit `245b984`)

O branch atual tinha duas implementações concorrentes do `_load` do CPO:
- **Q.130.1** lia ordens de `plan.production_orders` (12 demo, `product_id` 4271-6004) →
  keyspace não casa com o routing real (`OF_P_ID` ~20000+) → `400 no operations`.
- **Q.126** (worktree, não merged) reconstrói tudo de `factory_raw.*` no espaço `OF_P_ID`.

Portado o Q.126 Stream 1 (state.py / routing_resolver.py / scheduler_run.py + alerta
`DURATION_FALLBACK_HIGH`), removido o loader partido do Q.130.1, atualizados 4 testes-stopgap.
`tests/plan` 822 verdes; suite completa **zero regressões novas** (6 falhas todas pré-existentes:
4 LLM/SQL-live + 2 ambientais — RLS `rowsecurity` introspeção + percentil boat — provadas
idênticas na base por `git stash`).

## Q.131.B — Verificação AO VIVO (o que o Q.126 nunca correu)

`_audit/q131/verify_real_schedule.py` (read-only) corre o `FactoryState.load()` integrado
contra a BD viva + `RoutingResolver.resolve_many` sobre o WIP real. Resultado
(`verify_real_schedule.json`):

| Métrica | Valor | Veredicto |
|---|---|---|
| `loaded_ok` | True | ✅ |
| open_orders (WIP real, OF_P_ID) | 2000 | ✅ ordens reais, não as 12 demo |
| modelos com rota real reconstruída | 605 | ✅ (= Q.126) |
| **operações resolvidas** | **10 620** | ✅ ops>0 (sem 400) |
| **fallback_fraction** | **0.0** | ✅ ZERO template 2× sintético |
| **source_distribution** | **{history_db: 10620}** | ✅ 100% de histórico real |
| ordens com rota real | 1168 / 2000 (58,4%) | ⚠️ ver nota |
| ordens com molde ligado | 1862 / 2000 (93,1%) | ✅ |
| mediana Laminagem | **4.32 h** | ✅ (real) |
| mediana Cura | **17.38 h** | ✅ (real) |
| mediana Pintura | **3.18 h** | ✅ (real) |

**Conclusão:** o CPO planeia WIP real com rotas/durações/moldes 100% reais (0 fallback
sintético). As durações batem exatamente na verdade-do-terreno do ERP.

**Nota honesta (41,6% sem rota):** os modelos sem ≥2 observações por fase em `of_fp`
(`HAVING count(*) >= 2`, piso estatístico para mediana fiável) não têm rota reconstruível —
são kayaks raros/novos. As suas ordens resolvem 0 operações (ignoradas), NUNCA com dados
falsos (Spelke/zero-mock). Subir a cobertura exigiria histórico, não código. Decisão de
produto deferida (baixar o piso para 1 obs reduz a confiança; criar rotas-template para
modelos sem histórico seria fabricar dados).
