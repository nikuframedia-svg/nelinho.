# ERP NELO Activation Checklist (Q.68.6.C)

Como flipar `sqlserver_enabled=False -> True` em produção NELO de forma
segura. Afecta os mirrors ETL mapeados em Q.68.B
(`agent_docs/q68_erp_sync_audit.md`):

| Mirror | Schema Postgres | Origem ERP |
|---|---|---|
| `master` | core/plan (6 tabelas) | produtos, empregados, BOM, routings |
| `molds` | `plan.molds` | catálogo (~91 moldes) |
| `skills` | `hr.skills`, `hr.employee_skills` | matriz de competências |
| `quality` | `quality.error_catalog`, `quality.rework_entries` | retrabalho/defeitos |
| `time_mining` | `plan.routing_template_phases` (P50/P90) | OF_FP, 3 anos |
| `stock` | `supply.warehouse_stock` | `dbo.produto_stocks_por_armazem` |
| `calendar` | `core.factory_calendar_days` | working days + turnos |
| `inventory_ledger` | `supply.inventory_ledger_entries` | event-sourced (Q.64.A) |
| `material_master` | `supply.supply_material_master` | shortage detector (Q.64.B) |
| `purchase_orders` | `supply.purchase_orders` | tab Entregas (Q.64.D) |

Total: 10 mirrors. Os jobs (`nelo_erp_sync`, `nelo_erp_time_mining`,
`nelo_erp_incremental_sync`) ficam todos como **no-op silencioso**
enquanto `sqlserver_enabled=False` — flipar é o gatilho.

---

## 1. Pre-requisitos

### 1.1 Network
- [ ] Servidor `pp1.nelo.local` (torre nelinho) consegue alcançar o host
      SQL Server da fábrica MAR-KAYAKS (ping + porta 1039).
- [ ] Firewall outbound permite TCP 1039 da torre para o ERP.
- [ ] Se via Tailscale: ACL inclui ambos os hosts; teste rápido com
      `nc -zv fabrica.nelo.eu 1039` ou `Test-NetConnection`.

### 1.2 Driver ODBC do SO (NÃO é pacote pip)
- [ ] **ODBC Driver 18 for SQL Server** instalado no Linux da torre:
  ```bash
  curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
  curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list \
       | sudo tee /etc/apt/sources.list.d/mssql.list
  sudo apt-get update
  sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18 unixodbc-dev
  ```
- [ ] Verifica `odbcinst -q -d` lista `ODBC Driver 18 for SQL Server`.
- [ ] `aioodbc` + `pyodbc` já estão em `requirements.txt` — confirmar:
  ```bash
  grep -E "^(aioodbc|pyodbc)" requirements.txt
  ```

### 1.3 Credenciais
- [ ] Conta SQL Server **DataReader-only** criada pela IT da NELO
      (o nelinho nunca escreve no MAR-KAYAKS).
- [ ] Connection string testada localmente fora do nelinho:
  ```bash
  .venv/bin/python -c "import aioodbc, asyncio; asyncio.run(
      aioodbc.connect(dsn='Driver={ODBC Driver 18 for SQL Server};\
  Server=fabrica.nelo.eu,1039;Database=MAR-KAYAKS;UID=USER;PWD=PASS;\
  TrustServerCertificate=yes;Encrypt=no').close())"
  ```
- [ ] Password guardada em `/etc/prodplan/env` (chmod 600, NÃO em git).

---

## 2. Activation procedure

### 2.1 Configurar `/etc/prodplan/env`
```bash
sudo nano /etc/prodplan/env
# definir:
#   SQLSERVER_ENABLED=true
#   SQLSERVER_URL=mssql+aioodbc://USER:PASSWORD@fabrica.nelo.eu:1039/MAR-KAYAKS?\
#     driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes&Encrypt=no
#   SQLSERVER_POOL_SIZE=5
#   SQLSERVER_QUERY_TIMEOUT_S=30
sudo chmod 600 /etc/prodplan/env
sudo systemctl daemon-reload
```

### 2.2 Smoke — validate (read-only, exercita ~13 queries)
```bash
cd /opt/prodplan
./.venv/bin/python scripts/validate_nelo_erp.py
```
Esperado: linhas `OK   health_check`, `OK   count_open_orders`, ... com
contagens reais e amostras de uma linha. Qualquer `FALHA` deve travar a
activação até resolução.

### 2.3 Restart da app
```bash
sudo systemctl restart prodplan-api
journalctl -u prodplan-api -n 100 | grep -iE "nelo|sqlserver"
```
Esperado: arranca sem tracebacks; logs mencionam `sqlserver_enabled=True`
e o scheduler regista `nelo_erp_sync`, `nelo_erp_time_mining`,
`nelo_erp_incremental_sync`.

### 2.4 Primeiro sync manual (sem time_mining, é pesado)
```bash
./.venv/bin/python scripts/sync_nelo_erp.py --exclude time_mining
```
Esperado: 9 mirrors com `Status: ok` e `Read > 0`. Exit code 0. Output
tem a tabela `Mirror | Status | Read | Ins | Upd | Skip`.

### 2.5 Verificar `core.etl_run`
```bash
psql -U prodplan -d prodplan_one -c "
  SELECT source, status, rows_read, rows_inserted + rows_updated AS ins_upd,
         started_at
    FROM core.etl_run
   WHERE started_at > now() - interval '15 minutes'
   ORDER BY started_at DESC;
"
```
Esperado: 9 linhas com `status='ok'`, `rows_read>0`.

### 2.6 Verificar `scripts/check_nelo_sync.py`
```bash
./.venv/bin/python scripts/check_nelo_sync.py
```
Faz cross-check contagens Postgres vs ERP (subset).

### 2.7 Verificar endpoints frontend
- [ ] `GET /v1/factory/semantic` — devolve produtos não-vazio.
- [ ] `GET /v1/supply/inventory` — stock não-vazio.
- [ ] `POST /v1/copilot/ask` body `{"question": "Quanto stock de fibra?"}`
      — resposta cita números reais (não `"não tenho dados"`).
- [ ] `GET /v1/quality/rework-entries` — paginação OK, contagem cresceu.

### 2.8 Time-mining (uma vez, manual)
```bash
./.venv/bin/python scripts/sync_nelo_erp.py --only time_mining
```
Estimativa: 30-60 min na primeira run (3 anos de OF_FP). Vai actualizar
`plan.routing_template_phases` com P50/P90 reais — depois o CPO começa a
usar tempos minerados em vez do default.

---

## 3. Rollback (seguro, no-op clean)

Se algo correr mal:
```bash
sudo sed -i 's/^SQLSERVER_ENABLED=true/SQLSERVER_ENABLED=false/' /etc/prodplan/env
sudo systemctl restart prodplan-api
```
Os 3 jobs do scheduler voltam a no-op silencioso. Os mirrors **não**
escrevem dados parciais — `EtlRunner` faz tudo dentro de transacção, e
um erro no meio dá `ROLLBACK`. O frontend volta a depender do que já
estava em Postgres (último sync OK).

Rollback é seguro porque:
- Mirrors são idempotentes (upsert por business-key).
- A próxima activação parte do mesmo estado — sem dados orfãos.
- `core.etl_run` mantém o histórico (`status='error'` para diagnóstico).

---

## 4. Watch — 24 a 48h após activação

- [ ] `core.etl_run` mostra runs **incrementais a cada 5 min**
      (mirrors: `stock`, `calendar`, `quality`).
- [ ] `core.etl_run` mostra **full sync diário a 02:00 UTC**
      (todos excepto `time_mining`).
- [ ] `core.etl_run` mostra **time_mining semanal — Domingo 01:00 UTC**.
- [ ] `journalctl -u prodplan-api --since "1 day ago" | grep -i error`
      vazio (ou só erros benignos conhecidos).
- [ ] Alarme: agendar cron 06:00 UTC com:
  ```bash
  ./.venv/bin/python scripts/check_etl_runs.py \
      --mode freshness --stale-hours 26 --json
  ```
  Exit `1` -> mandar email/Slack à equipa (Q.69 candidato é UI alert).

---

## 5. Failure modes conhecidos

| Sintoma | Causa típica | Mitigação |
|---|---|---|
| `Login failed for user '...'` no `validate_nelo_erp.py` | password errada ou conta sem `db_datareader` | confirma credenciais com IT NELO; testa com `sqlcmd` se possível |
| `IM002 Data source name not found` | driver ODBC 18 em falta no SO | reinstala `msodbcsql18`; `odbcinst -q -d` |
| `time_mining` falha por OOM (`MemoryError`) | RAM <4GB livre durante a janela das 3 anos | corre com `--since YYYY-MM-DD` mais recente para reduzir scope; sobe RAM da torre |
| `nelo_erp_incremental_sync` corre mas `rows_read=0` constante | clock skew torre vs ERP (watermark futuro) | sincroniza relógios (chrony/ntpd); verifica `MAX(finished_at)` em `core.etl_run` |
| Schema ERP mudou — query do mirror parte | NELO IT mexeu numa tabela | erro aparece em `core.etl_run.error`; ver `src/adapters/nelo/services.py list_<mirror>` |
| Copiloto continua a dizer "não tenho dados" | mirror correu mas frontend ainda lê camada curated antiga | confirma que o endpoint cai em `production_orders`/`rework_entry`, não em mocks (Q.34.A) |

---

## 6. Variáveis de ambiente

Ver `.env.production.example` (secção `ERP NELO`). Variáveis efectivas:

| Var | Default | Notas |
|---|---|---|
| `SQLSERVER_ENABLED` | `false` | flip para `true` apenas após este checklist |
| `SQLSERVER_URL` | (vazio) | URL async SQLAlchemy `mssql+aioodbc://...` |
| `SQLSERVER_POOL_SIZE` | `5` | conservador; subir se latência alta |
| `SQLSERVER_QUERY_TIMEOUT_S` | `30` | corta queries presas no SQL Server |

NÃO há prefixo `NELINHO_` — `pydantic-settings` lê directo do ambiente.

---

## 7. Referências cruzadas

- `agent_docs/q68_erp_sync_audit.md` — audit dos 10 mirrors e schedule.
- `deploy/RUNBOOK.md §7` — versão curta do "ligar o ERP vivo".
- `src/shared/config.py:53-70` — `sqlserver_enabled`/`sqlserver_url`.
- `src/adapters/nelo/etl/sync.py` — orchestrator.
- `scripts/validate_nelo_erp.py` — smoke read-only.
- `scripts/sync_nelo_erp.py` — sync manual / CLI.
- `scripts/check_etl_runs.py` — freshness check (cron alarm candidate).
