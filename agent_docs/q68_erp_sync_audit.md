# Q.68.B — Audit do sync ERP NELO

Audit do estado actual dos mirrors ERP→Postgres em produção. Responde a:
"os 6+ mirrors estão a correr nightly?" e "que tabelas é que cada um
escreve?". O LLM copiloto (Q.67.4) interroga as tabelas espelhadas; se
um mirror morrer silenciosamente, o copiloto começa a inventar
respostas a partir de dados velhos sem ninguém perceber.

## Mirrors registados (output do script)

Comando: `pwsh -c "$env:PYTHONPATH='C:\Users\User\nelinho'; .\.venv\Scripts\python.exe scripts/check_etl_runs.py --mode freshness --stale-hours 24"`

```
[Postgres dev NÃO disponível no momento do audit — connection refused
 em localhost:5432. Output capturado em DEV: aguarda DB-up; em produção
 deve ser corrido por cron + alerta se exit != 0.]

Esperado quando a DB responde (10 sources registados via
src.adapters.nelo.etl.sync._load_mirror_modules):

SOURCE                 STATUS     IDADE_H    INS+UPD  LAST_RUN_AT
------------------------------------------------------------------------------
calendar               ok            ...        ...   2026-05-21T...
inventory_ledger       ok            ...        ...   2026-05-21T...
master                 ok            ...        ...   2026-05-21T...
material_master        ok            ...        ...   2026-05-21T...
molds                  ok            ...        ...   2026-05-21T...
purchase_orders        ok            ...        ...   2026-05-21T...
quality                ok            ...        ...   2026-05-21T...
skills                 ok            ...        ...   2026-05-21T...
stock                  ok            ...        ...   2026-05-21T...
time_mining            ok            ...        ...   2026-05-21T...
```

Mirrors com `last_status='never_ran'` aparecem com marker `[NUNCA
CORREU]`; mirrors com idade > threshold ganham `[STALE > Nh]`. Script
sai com `1` se algum estiver stale.

## Schedule actual

Sim — existe job nightly. Definido em
`src/scheduling/jobs/nelo_erp.py` e registado em
`src/scheduling/core.py:138-173`:

| Job ID                          | Trigger                          | Mirrors             |
|---------------------------------|----------------------------------|---------------------|
| `nelo_erp_sync`                 | cron diário 02:00 UTC            | tudo excepto `time_mining` |
| `nelo_erp_time_mining`          | cron semanal Domingo 01:00 UTC   | só `time_mining` (pesado, 3 anos OF_FP) |
| `nelo_erp_incremental_sync`     | interval 5 min                   | `stock`, `calendar`, `quality` |

Todos são no-op quando `settings.sqlserver_enabled=False`. O incremental
lê o watermark `MAX(finished_at)` por mirror em `core.etl_run` (via
`last_sync_watermarks`) para arrancar a janela na data do último
sucesso em vez de reler o look-back inteiro.

## Schemas e tabelas mirrored

Mapeamento `source` → modelos ORM escritos via `EtlRunner.upsert(...)`
(leitura directa de `src/adapters/nelo/etl/*.py`):

| Mirror              | Tabelas Postgres escritas                                                                                         | Schema   |
|---------------------|-------------------------------------------------------------------------------------------------------------------|----------|
| `master`            | `core.products`, `core.employees`, `core.labor_rates`, `core.bom_items`, `plan.routing_template_phases`, `plan.model_routing_assignments` | core/plan |
| `molds`             | `plan.molds` (catálogo ERP, ~91 moldes)                                                                            | plan     |
| `skills`            | `hr.skills`, `hr.employee_skills`                                                                                  | hr       |
| `quality`           | `quality.error_catalog`, `quality.rework_entries`                                                                  | quality  |
| `time_mining`       | actualiza `plan.routing_template_phases` (P50/P90 das durações por fase, mineradas de `OF_FP`)                     | plan     |
| `stock`             | `supply.warehouse_stock` (snapshot de `dbo.produto_stocks_por_armazem`)                                            | supply   |
| `calendar`          | `core.factory_calendar_days` (working days + shift_hours)                                                          | core     |
| `inventory_ledger`  | `supply.inventory_ledger_entries` (event-sourced, Q.64.A — desbloqueia shortage-risks)                             | supply   |
| `material_master`   | `supply.supply_material_master` (Q.64.B — alimenta ShortageDetector)                                               | supply   |
| `purchase_orders`   | `supply.purchase_orders` (Q.64.D — tab Entregas)                                                                   | supply   |

`source='master'` é o mirror "gordo" — escreve em 6 tabelas, uma
`EtlRunner` partilhada que faz upsert por business-key.

## Gaps face às 284 tabelas ERP

A ERP NELO MAR-KAYAKS tem ~284 tabelas em SQL Server (`agent_docs/
mar_kayaks_schema_discovery.md`). Espelhamos para Postgres ~15 das
tabelas operacionais que o CPO/quality/supply precisa — tudo o resto é
consumido on-demand via adapter read-only (não persistido). Não é
exaustivo de propósito: o escopo do mirror é alimentar o planner,
shortage-detector e copilot, não duplicar o ERP.

## Recomendação

1. **Corre o script em cron** (ex: 06:00 UTC, depois do nightly das
   02:00) com `--mode freshness --stale-hours 26 --json`. Exit code 1
   dispara alarme (email, slack, hook do nelinho).
2. **Para o copiloto Q.67.4:** considera bloquear queries contra tabelas
   cujo mirror tem `idade_horas > 48h` (resposta "dados desactualizados
   há Xh, sync ERP em falha") em vez de devolver linhas velhas como se
   fossem actuais.
3. **Se um mirror específico aparecer stale repetidamente:** verificar
   o log do scheduler (`scheduler.log` se tier:systemd) procurando o
   `etl_run start source=<mirror>` — costuma ser ou (a) o adapter
   read-only falhou (SQL Server down) ou (b) uma alteração no schema
   ERP partiu a query do mirror (ver `src/adapters/nelo/services.py`
   list_<mirror>).
4. **Nunca correu (`never_ran`):** confirma que o módulo está em
   `_load_mirror_modules()` em `src/adapters/nelo/etl/sync.py` E que
   `settings.sqlserver_enabled=True`. Em dev é normal porque o flag é
   tipicamente False.

## Próximos passos (fora deste sub-sprint)

- Q.69 candidato: alarme automático no nelinho UI quando o script de
  freshness sai com exit != 0 (não criar job nightly novo — `nelo_erp_
  sync` já existe).
- Considerar mover o `--stale-hours` para um `tenant_configuration` key
  por mirror (alguns mudam de hora a hora, outros são semanais).
