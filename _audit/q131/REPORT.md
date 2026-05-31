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

## Q.131.C — "0 demo" na lista de ordens (mirror ERP → production_orders)

Auditoria do caminho de leitura: `/v1/plan/orders`, `/stats`, `/active`, `/v1/work-orders`
**todos** liam `plan.production_orders` (12 demo, seed SQLite `product_id` 4271-6004); **nenhum
sync ERP** a alimentava. Blast-radius de mudar `product_id`→`OF_P_ID`: 13/16 consumidores usam
`legacy_id`/`product_name` (seguros); os 2 que usam `product_id` (MRP, pricing) já estavam
partidos/vazios com as 12 demo — `OF_P_ID` só melhora (`core.products.product_code` = `OF_P_ID`).
Nenhum código assume `product_id==legacy_id`.

**Solução:** `scripts/q131_setup_production_orders_mirror.py` — upsert idempotente SQL puro de
`factory_raw.ordemfabrico` (WIP: `OF_DATAFIM` NULL + `FP_PRODUCAO=true`) → `production_orders`,
keyed por `OF_P_ID`. Lê o `factory_raw` já espelhado (sem dependência SQL Server). Job
`_nelo_erp_production_orders_job` (5/5 min, Postgres-interno) em `src/scheduling/core.py`.
Guard: no-op se WIP vazio (protege dev/test). Sem audit por-linha (precedente dos mirrors ERP
`customers`/`raw` — ingestão de dados, não decisão governada).

Resultado (corrida live): `production_orders` **12 → 5315** (prune das 12 demo, 0 restantes);
**overlap com routing real 5261/5315 ≈ 99%** (era 0/12); `product_id` em 20205-54141 (OF_P_ID);
idempotente (2ª corrida 5315→5315). Comentário obsoleto "27 380 orders" corrigido em
`frontend/src/lib/api/planApi.ts`.

**Nota honesta (88,7% `product_type='Other'`):** o WIP real (5315) é dominado por
**acessórios/componentes** (assentos, tábuas, "p/ montar"), não barcos — os barcos K1/K2/K4/
C1/C2/C4 são 601 (11,3%). É o filtro `FP_PRODUCAO=true` (o mesmo que o CPO usa), portanto dados
reais e honestos. Se o Luis quiser a lista/planeamento só de barcos, é um filtro de uma linha
(por `product_type` ou `produto.P_TP_ID`) — decisão de produto, não fabricar dados.

Verificação via API live (backend :8001): `/v1/plan/orders/stats` → `total=5315`
(era 12), fases reais ("Laminagem peças" 1273, "Corte peças" 1168); `/v1/plan/orders` →
OFs reais ("C1 28 XL FC Prepreg", "Ocean Ski 510 Pl"), UTF-8 correto. 0 demo confirmado.

## Q.131.F — Cap do horizonte de planeamento (~200 ordens mais urgentes)

A verificação live do `POST /v1/plan/cpo/schedule` destapou um problema de produto: com o WIP
inteiro (`_load_open_orders_db` LIMIT 2000 → ~11k operações) a GA **esgotava o orçamento na
geração 1** (sem optimização) e o pedido não voltava em <90s — inútil para um "Replanear"
interactivo. O Luis tinha pedido ~200.

Reduzido o LIMIT 2000 → `_OPEN_ORDERS_PLAN_CAP=200` (constante nomeada), mantendo
`ORDER BY data_entrega_prevista NULLS LAST` (rolling horizon: as 200 mais urgentes).

| Antes (2000) | Depois (200) |
|---|---|
| GA budget exhausted @ **geração 1** | GA optimiza até **geração 8** |
| POST não volta em >90s | HTTP 200 em **31s**, `degraded=False`, commit real (ops=2838) |

**Nota honesta (qualidade do schedule):** o `makespan` ainda é irrealista porque o
`skill_matrix` real é parcial (483 pares de `offp_eq`) → muitas fases sem operador são agendadas
como "manual" e serializadas. Isto é **qualidade de optimização** (cobertura de skills + budget
da GA), não "dados reais" — campanha futura. Os dados de ENTRADA são 100% reais.

## Q.131.E — Gate + revisão adversarial

- `& .\scripts\verify.ps1 -QuickPython`: **ALL GREEN** (ruff, lint-imports, verify_invariants
  estáticas+AST, **lint-audit-coverage invariante 7 OK**, drift gate, tsc, vitest 172, lint:mocks
  0 erros). Invariantes WG/CO/ME/H0 + imports CPO todos OK.
- Suite Python completa: **zero regressões novas** (6 falhas todas pré-existentes — 4 LLM/SQL-live
  + 2 ambientais — provadas idênticas na base por `git stash`).
- **Revisão independente (`nelo-reviewer`): APROVADO.** CX1 limpo (durações só de DATAINICIO→FIM,
  zero campos €); axiomas Spelke não tocados (`generations=200`, `routing_choices`,
  `rejected_alternatives`, idle-axis intactos); reconciliação sem referências mortas; mirror
  idempotente com guard de WIP-vazio; PT-PT; zero mocks. 3 ressalvas não-bloqueantes (título do
  commit A com 73 chars; `print()` num script CLI; teste CX1 best-effort com docstrings).

## Resumo

A pergunta do Luis ("o planeamento usa dados reais? a BD é real?") está respondida:
**a BD é real e o planeamento usa-a a sério.** O CPO planeia WIP real com rotas/durações/moldes
100% reais (0 fallback sintético), a lista de ordens tem 0 demo (5315 OFs reais), e o horizonte
interactivo é tratável (200 mais urgentes, GA optimiza). Limitações honestas e deferidas:
cobertura de rota (58%) e de skills (parcial) dependem de histórico/dados, não de código;
filtro boats-only e qualidade do `makespan` são decisões/campanhas futuras.
