# Bootstrap & DB recovery

When the dev DB is in a bad state — failed migration, "table doesn't exist", `DuplicateObject`,
schema drift — the canonical recovery is **drop + recreate + bootstrap_dev_full.py**. Don't try
surgical schema fixes — they're not reproducible.

## Quick reference (PowerShell)

```powershell
# 0. Set PYTHONPATH (every shell session)
$env:PYTHONPATH = "c:/Users/User/nelinho"

# 1. Stop anything holding sessions
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | `
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

# 2. Terminate Postgres sessions on prodplan_one
$psql = "$env:USERPROFILE\scoop\apps\postgresql\current\bin\psql.exe"
& $psql -U postgres -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity ``
  WHERE datname = 'prodplan_one' AND pid <> pg_backend_pid();"

# 3. Drop + create
& $psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS prodplan_one;"
& $psql -U postgres -d postgres -c "CREATE DATABASE prodplan_one OWNER prodplan;"
& $psql -U postgres -d prodplan_one -c "GRANT ALL ON SCHEMA public TO prodplan;"

# 4. Run bootstrap (16 schemas + 93 tables + dev tenant + 183 configs)
.\.venv\Scripts\python.exe scripts/bootstrap_dev_full.py
# Expected output: "OK — DB ready, tenant ..., 183 configs seeded"

# 5. Restart backend
.\.venv\Scripts\python.exe -m uvicorn src.main:app `
  --host 127.0.0.1 --port 8000 --log-level warning
```

5 minutos do início ao fim. Idempotent — corridas múltiplas convergem para o mesmo estado.

## Ordem dev — popular dados do ERP (Q.36)

`bootstrap_dev_full.py` cria as tabelas + tenant + configs, mas as tabelas de dados
operacionais e curados arrancam **vazias**. Para que o copiloto e os 3 detectores causais
(`erro_tree`, `reichenbach`, `mill_diff`) tenham dados reais, corre o sync do ERP a seguir
ao bootstrap, **nesta ordem**:

```powershell
# A. master data (produtos, operadores, routings, BOM) — TEM de correr primeiro:
#    o curated_loader resolve o causador via core.employees.
.\.venv\Scripts\python.exe scripts/sync_nelo_erp.py --only master

# B. factory_curated.* + quality.rework_entry (Q.36) — corre o mirror de
#    qualidade (OF_CHECKLIST) + o curated_loader (OF_FP/OF_CHECKLIST/OFFP_EQ).
.\.venv\Scripts\python.exe scripts/populate_curated.py
# --since YYYY-MM-DD limita a janela (default: 365 dias).
```

O `bootstrap_dev_full.py` já chama o passo B automaticamente **quando `SQLSERVER_ENABLED=true`**
no `.env` (ver `populate_curated_if_erp_available`). Sem ERP acessível é um no-op silencioso —
o bootstrap continua a correr numa máquina sem ligação ao SQL Server, e os detectores causais
devolvem "sem causa" honesto até o `populate_curated.py` correr.

Verificação: uma pergunta causal ("porque caiu a qualidade?") deve devolver uma causa raiz com
`chain` real, não "sem causa significativa".

## Why not Alembic?

`init_db()` em [src/shared/database.py:198](src/shared/database.py#L198) faz
`Base.metadata.create_all()` em vez de `alembic upgrade head`. Dívida técnica conhecida
(memory: `project_alembic_create_all_legacy.md`).

Implicação: tabelas só são criadas para modelos **importados no path do startup**. Os modelos
do `governance/`, `dqa/`, `quality/`, `factory_data_product/`, `copilot/`, `explain/`, etc.
têm que estar todos importados (directa ou transitivamente) em `main.py` ou `bootstrap_dev_full.py`.

`bootstrap_dev_full.py` resolve isto importando explicitamente todos os modelos antes de
chamar `Base.metadata.create_all()`. Por isso é mais robusto que `init_db()` na startup.

Future cleanup: migrar para Alembic-only. Q.18+ scope.

## pgvector skip (scoop postgres 18)

scoop postgres 18 não traz `pgvector` por default. Migration `008_create_pgvector_indexes.py`
tem graceful skip:

```python
# alembic/versions/008_create_pgvector_indexes.py
result = op.get_bind().execute(text(
    "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
)).fetchone()
if not result:
    print("[008] pgvector not available, skipping")
    return
```

`bootstrap_dev_full.py` exclui a tabela `copilot_rag_chunk` (depends on vector type) por isso
o RAG functionality fica indisponível em dev. Tudo o resto funciona.

Para activar pgvector em dev: instalar manualmente do contrib. Tipicamente disponível mas
requer build local. Não é prioridade até Q.18+ RAG features.

## Common errors and fixes

### `relation "<schema>.<table>" does not exist`

Sintoma: 5xx com message `UndefinedTable: relation "governance.decision_run" does not exist`.

Causa: modelo importado pelo startup mas tabela ainda não existe (DB drop sem subsequent bootstrap),
OU modelo não importado por nenhum caminho até `Base.metadata.create_all()`.

Fix:
1. Verificar se a tabela existe: `psql -d prodplan_one -c "\dt governance.*"`
2. Se faltam tabelas: `bootstrap_dev_full.py`
3. Se a tabela existe noutros schemas mas não neste: confirmar import do modelo (`grep -r "class DecisionRun" src/`)

### `type "<x>" already exists`

Sintoma: alembic `DuplicateObjectError: type "schedule_status" already exists`.

Causa: collision entre `init_db()` create_all e Alembic migrations. Geralmente por correr
ambos em sequência sem drop entre.

Fix: drop DB completo (passo 1-3 acima) + bootstrap_dev_full.

### `database "prodplan_one" is being accessed by other users`

Causa: uvicorn ou pytest têm sessions abertas.

Fix: passos 1-2 acima (`pg_terminate_backend` + kill local processes).

### `extension "vector" is not available`

Esperado em scoop postgres 18 dev. Migration 008 tem skip graceful. Usar bootstrap_dev_full
em vez de `alembic upgrade head` para evitar.

### Backend `exit code 255` randomly

Normalmente uvicorn die — pytest concurrente esgotou pool de DB.

Fix: restart uvicorn. Em CI separar processos não conflituam.

## Realtime (Kafka) is degraded by design in dev

`/v1/realtime/events` retorna 503 quando Kafka offline — RealtimeBridge fail-closed. Isto **NÃO
é um bug** em dev. Frontend cai a polling automaticamente.

Se apareceres a tentar instalar Kafka em dev: pára. Não é necessário até production deploy.

## Common rationalizations

| "Vou correr alembic upgrade head em vez do bootstrap_dev_full" | Vai falhar em pgvector. bootstrap_dev_full é o caminho dev. |
| "Vou editar a migration que falhou para a fazer passar" | Migration são fact. Se a migration está errada, **fixa o modelo**, gera nova migration. Editing migrations history breaks reproducibility. |
| "DROP DATABASE só em prod, em dev edito à mão" | A dev em estado não-reproduzível é dívida. Sempre passar pelo bootstrap. |
| "Adiciono um try: except em init_db para suprimir o erro" | Bare except esconde bugs. Confirma que o modelo está importado correctamente. |

## Verifying the recovery worked

```bash
# 1. Health endpoints respond
curl http://localhost:8000/health         # 200
curl http://localhost:8000/health/ready   # 200
curl http://localhost:8000/health/live    # 200

# 2. Tenant exists
psql -d prodplan_one -c "SELECT id, slug FROM core.tenants;"
# Expected: 00000000-0000-0000-0000-000000000001 / nelo-dev

# 3. Configs seeded (183 expected)
psql -d prodplan_one -c "SELECT COUNT(*) FROM core.tenant_config;"

# 4. Canary tests
.\.venv\Scripts\python.exe -m pytest tests/governance/ -q
# Expected: 348 passed in ~53s
```

Se os 4 passam, recovery completa.
