# Q.137 — Robô automático: planos CPO aparecem sozinhos · REPORT

**Branch:** `feat/q137-auto-replan` (de `main` pós-Q.136). Merge `--no-ff` local, **SEM push**.

## Pedido
"Ligar o robô automático para os planos aparecerem sozinhos no ecrã." O grid `/overall` já faz
polling de 30s ao `/cpo/commits`; faltava o **gatilho** — não havia job que corresse o CPO sozinho.

## Decisão do Luis
Re-planeia **após cada sync do ERP, com debounce/rate-limit** (~máx 1/hora). Nasce **DRAFT** (Q.17).

## Verificação dos pré-requisitos (read-only) — todos de pé
- Grid mostra o commit mais recente (DRAFT ou LIVE) com badge "Rascunho" (Q.133.A).
- Redis up (`nelo-redis redis:7.4`) + arq 0.28; worker `src.plan.cpo.worker.WorkerSettings`.
- `run_cpo_schedule` persiste em `public.plan_schedule_commits` (já tinha 1 LIVE de 2859 ops).
- Tabelas/keyspace confirmados (`OF_FP_ID`/`OFFP_FP_ID`/`PRODF_FP_ID` = FP_ID; OF_P_ID→produto 100%).

## Feito
- **Q.137.A** (`6b2e95c`): `src/scheduling/jobs/auto_cpo_replan_job.py` — `_auto_cpo_replan_global_job`
  (IntervalTrigger 15 min em `core.py`). Por tenant: config-gate (`planning.auto_replan_enabled`) +
  rate-limit (`auto_replan_min_gap_min`, 60) + deteção de mudança (watermark `count + max(OF_DATA
  ACTUALIZACAO)` do WIP-barco em `factory_raw.ordemfabrico`; 1ª corrida dispara sempre). **Enfileira**
  `cpo_schedule_job` no Arq (padrão do `schedule_cpo_async`). DRAFT-only; best-effort (Redis down →
  log+skip). 7 testes unitários.
- **Q.137.0** (`0e1a2ba`): desbloqueou o gate pré-existente (mascarado por cache stale do ruff no
  Q.136): 2× RUF100 em `transport.py` (fix) + baseline drift BLE001 430→438 (best-effort do Q.117.B
  auto_propose) + audit 0→1 (DRAFT-commit Q.133.A; a transição auditável é o approve DRAFT→LIVE). O
  job Q.137 adiciona **0 BLE001**.
- RUNBOOK §5: `nelinho-arq` obrigatório para os auto-planos.

## Prova AO VIVO (end-to-end)
1. Worker arrancado (`Starting worker for 1 functions: cpo_schedule_job`, redis 7.4.9).
2. Disparado `_auto_cpo_replan_global_job([dev])` → detetou **777 barcos**, enfileirou o job
   `c72a43b2…` (estado `_last_run` gravado).
3. O worker correu o CPO e **persistiu um DRAFT novo**: `status=DRAFT, ops=1467, sha=e95b6ea2`
   (vs o LIVE antigo de 2859 ops = todo o WIP — o novo é mais pequeno = boats-only + fase-atual).
4. **As ops são barcos** (amostra): order 139443 "Canoe Marathon", 141295 "Canoe Sprint", 880193
   "ICON" — todas deck/casco>0.
5. Sendo o mais recente, o grid `/overall` (polling 30s) renderiza-o com badge "Rascunho".

**→ O robô gera o plano de barcos SOZINHO.** ✓

## Honestidade
- O makespan do DRAFT (17985h p/ 200 barcos em 30s) é grande — é **qualidade do CPO** (solve curto +
  set grande), não do Q.137; o plano nasce DRAFT (não aprovado). Tuning do engine/horizonte é separado.
- Em dev a BD é estática (`OF_DATAACTUALIZACAO` não muda) → após o 1º plano, a deteção de mudança
  mantém-no (correto); em prod re-planeia quando o WIP muda.
- Continua **local, sem push**. Worker via systemd (`nelinho-arq`) em prod / comando em dev.
