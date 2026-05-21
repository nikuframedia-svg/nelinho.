# Bootstrap, backup & DB recovery

Canonical playbook for the **dev** drop+recreate cycle **and** the **prod**
backup / restore loop on the NELO single-server box. Don't fork into ad-hoc
recipes — every shortcut here has already been paid for once.

Related runbooks:

- [`deploy/RUNBOOK.md`](../deploy/RUNBOOK.md) — first-time install on the NELO tower.
- [`docs/disaster-recovery.md`](../docs/disaster-recovery.md) — full-box loss / pgBackRest path.
- This file — DB-only recovery + the pg_dump nightly backup (Q.68.2.C).

---

## 1. Dev recovery — drop + recreate (PowerShell)

When the dev DB is in a bad state (failed migration, `UndefinedTable`,
`DuplicateObject`, schema drift) **don't try surgical schema fixes** —
they're not reproducible. The canonical recovery is:

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

5 minutes start-to-finish. Idempotent — multiple runs converge to the same state.

### Quick safety net before risky dev work

Before a drop+recreate, snapshot the local DB so you can roll back if the
new state is worse than what you had:

```powershell
.\scripts\backup_db.ps1
# Backup OK: C:\Users\User\nelinho-backups\nelinho_20260521T143022Z.dump (12.4 MB)
```

Default backup dir is `$env:USERPROFILE\nelinho-backups`. See §3.4 for
restore.

---

## 2. Why not `alembic upgrade head` in dev?

`init_db()` em [src/shared/database.py](../src/shared/database.py) faz
`Base.metadata.create_all()` em vez de `alembic upgrade head`. Dívida técnica
conhecida (Q.61.16 partial mitigation — production runs `alembic upgrade head`
before uvicorn; dev keeps `create_all` for speed).

Implicação: tabelas só são criadas para modelos **importados no path do startup**.
Modelos de `governance/`, `dqa/`, `quality/`, `factory_data_product/`, `copilot/`,
`explain/` etc. têm que estar todos importados (directa ou transitivamente) em
`main.py` ou `bootstrap_dev_full.py`. Q.61.14 consolidou todos em
`src/shared/model_registry.py`.

`bootstrap_dev_full.py` resolve isto importando explicitamente todos os modelos
antes de chamar `Base.metadata.create_all()`. Por isso é mais robusto que
`init_db()` na startup. Em produção, o `prodplan-api.service` corre
`alembic upgrade head` ANTES do uvicorn — `init_db()` só verifica revision.

### pgvector skip (scoop postgres 18)

scoop postgres 18 não traz `pgvector` por default. Migration
`008_create_pgvector_indexes.py` tem graceful skip:

```python
result = op.get_bind().execute(text(
    "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"
)).fetchone()
if not result:
    print("[008] pgvector not available, skipping")
    return
```

`bootstrap_dev_full.py` exclui a tabela `copilot_rag_chunk` (depends on
`vector` type) por isso o RAG functionality fica indisponível em dev. Tudo o
resto funciona. Para activar em dev: build manual do contrib. Não é
prioridade.

---

## 3. Production backup & restore (Q.68.2.C)

On the NELO box, single-server backup is **`pg_dump` custom format** driven
by a `systemd` timer. pgBackRest (full + WAL archive) lives in
[`docs/disaster-recovery.md`](../docs/disaster-recovery.md) for the
full-box-loss scenario; this section covers the daily DB-only loop.

### 3.1 One-time setup on the tower

```bash
# 1. Copy unit files into place.
sudo cp /opt/nelinho/deploy/systemd/nelinho-backup.service /etc/systemd/system/
sudo cp /opt/nelinho/deploy/systemd/nelinho-backup.timer   /etc/systemd/system/

# 2. Create the backup env file (POSTGRES_PASSWORD + optional overrides).
sudo install -m 0600 -o nelinho -g nelinho /dev/null /etc/nelinho/backup.env
sudo tee /etc/nelinho/backup.env >/dev/null <<'EOF'
POSTGRES_DB=prodplan_one
POSTGRES_USER=prodplan
POSTGRES_HOST=localhost
POSTGRES_PASSWORD=<same as /etc/prodplan/env>
NELINHO_BACKUP_DIR=/var/backups/nelinho
NELINHO_BACKUP_RETENTION_DAYS=30
# Optional offsite copy on the NELO LAN:
# NELINHO_BACKUP_OFFSITE=nelo-backup.local:/srv/nelinho/
EOF

# 3. Create the backup dir owned by the service user.
sudo install -d -m 0700 -o nelinho -g nelinho /var/backups/nelinho

# 4. Mark scripts executable + verify systemd syntax.
sudo chmod +x /opt/nelinho/scripts/backup_db.sh
sudo systemd-analyze verify /etc/systemd/system/nelinho-backup.service
sudo systemd-analyze verify /etc/systemd/system/nelinho-backup.timer

# 5. Enable + start the timer (the service is one-shot, fired by the timer).
sudo systemctl daemon-reload
sudo systemctl enable --now nelinho-backup.timer

# 6. Verify the timer is armed.
systemctl list-timers nelinho-backup.timer
# Expected: NEXT shows tomorrow at 03:00 UTC (+ up to 5 min jitter).
```

### 3.2 What the timer does

- `nelinho-backup.timer` fires **daily at 03:00 UTC** (`Persistent=true` catches
  missed runs on next boot; `RandomizedDelaySec=300` spreads load across nodes).
- It triggers `nelinho-backup.service` (`Type=oneshot`), which executes
  `/opt/nelinho/scripts/backup_db.sh` as the `nelinho` user with the env file.
- The script writes `/var/backups/nelinho/nelinho_<UTC ISO timestamp>.dump`,
  validates the dump with `pg_restore --list`, prunes anything older than
  `NELINHO_BACKUP_RETENTION_DAYS` (default 30), and optionally rsyncs to
  `NELINHO_BACKUP_OFFSITE`.
- All output goes to journald: `journalctl -u nelinho-backup -n 50`.

### 3.3 Manual ad-hoc backup

```bash
# Linux / production:
sudo systemctl start nelinho-backup.service
journalctl -u nelinho-backup -n 30 --no-pager

# Or run the script directly under the service env:
sudo -u nelinho env $(cat /etc/nelinho/backup.env | xargs) \
    /opt/nelinho/scripts/backup_db.sh
```

```powershell
# Windows dev (uses scoop postgres pg_dump.exe by default):
.\scripts\backup_db.ps1
```

### 3.4 Restore playbook

The dumps are in `pg_dump --format=custom` (`-Fc`) so `pg_restore` can do
parallel restore and selective table inclusion.

```bash
LATEST=$(ls -1t /var/backups/nelinho/nelinho_*.dump | head -1)
echo "Restoring from: $LATEST"

# 1. Stop the app so no connections race against the restore.
sudo systemctl stop prodplan-api

# 2. Terminate stray sessions on the target DB.
sudo -u postgres psql -d postgres -c "
    SELECT pg_terminate_backend(pid) FROM pg_stat_activity
    WHERE datname = 'prodplan_one' AND pid <> pg_backend_pid();
"

# 3. (Destructive!) Drop + recreate the DB.
#    Replace this block with a parallel-name DB if you want to keep the
#    old data for forensics — see §3.5.
sudo -u postgres psql -d postgres -c "DROP DATABASE prodplan_one;"
sudo -u postgres psql -d postgres -c "CREATE DATABASE prodplan_one OWNER prodplan;"

# 4. pg_restore (parallel, ignore owner/privs — they get re-derived from the role).
sudo -u postgres pg_restore \
    --dbname=prodplan_one \
    --jobs=4 \
    --no-owner \
    --no-privileges \
    "$LATEST"

# 5. Restart the app.
sudo systemctl start prodplan-api
sudo /opt/nelinho/scripts/dr-smoke.sh
```

Restore RTO on a ~5 GB dump: ~3–8 minutes. For the full-box-loss path
(provision OS + restore Postgres via pgBackRest + Kafka + Ollama + app),
see [`docs/disaster-recovery.md`](../docs/disaster-recovery.md) §3.3.

### 3.5 Safer restore — side-by-side DB

If you're not sure the dump is good, restore into a parallel DB first:

```bash
sudo -u postgres createdb prodplan_one_restore
sudo -u postgres pg_restore --dbname=prodplan_one_restore --jobs=4 \
    --no-owner --no-privileges "$LATEST"

# Sanity counts on the restored DB:
sudo -u postgres psql -d prodplan_one_restore -c "
    SELECT 'tenants' AS t, count(*) FROM core.tenants
    UNION ALL SELECT 'orders', count(*) FROM factory_curated.production_orders
    UNION ALL SELECT 'commits', count(*) FROM plan.schedule_commits;
"

# Promote by renaming, if the counts look right:
sudo systemctl stop prodplan-api
sudo -u postgres psql -d postgres -c "ALTER DATABASE prodplan_one RENAME TO prodplan_one_old;"
sudo -u postgres psql -d postgres -c "ALTER DATABASE prodplan_one_restore RENAME TO prodplan_one;"
sudo systemctl start prodplan-api
# Drop the old one once smoke tests are green for >24h.
```

### 3.6 Point-in-time recovery (PITR)

`pg_dump` is a **logical snapshot at 03:00 UTC** — there is no WAL replay,
so the worst case is **24 hours of lost writes**. For sub-hour RPO the NELO
deployment runs **pgBackRest** in parallel (see `docs/disaster-recovery.md`
§1 and §3.3.2). PITR steps:

```bash
sudo -u postgres pgbackrest --stanza=prodplan --type=time \
    --target="2026-05-21 14:00:00+00" restore
sudo systemctl start postgresql
```

The two backup paths are complementary, not redundant:

| Path | Granularity | Setup cost | Restore complexity | Used for |
|---|---|---|---|---|
| `pg_dump` nightly (this doc) | daily | low | low | dev clones, schema rollbacks, fast logical restore |
| pgBackRest + WAL | every 5 min | medium | medium | sub-hour RPO, PITR, full-box DR |

### 3.7 Verifying a backup without restoring

```bash
# Inspect TOC (fast, no DB needed):
pg_restore --list /var/backups/nelinho/nelinho_<ts>.dump | head -40

# Count rows for the canonical tables (requires a scratch DB):
sudo -u postgres createdb nelinho_verify
sudo -u postgres pg_restore --dbname=nelinho_verify --jobs=4 --no-owner \
    --no-privileges /var/backups/nelinho/nelinho_<ts>.dump
sudo -u postgres psql -d nelinho_verify -c "
    SELECT relname, n_live_tup
    FROM pg_stat_user_tables
    WHERE schemaname IN ('core','factory_curated','plan','governance')
    ORDER BY n_live_tup DESC LIMIT 20;
"
sudo -u postgres dropdb nelinho_verify
```

The quarterly `scripts/restore_drill.sh` automates this against the staging
box and is wired to the `BackupStale` Prometheus alert.

---

## 4. Disaster scenarios

### 4.1 `relation "<schema>.<table>" does not exist` (dev)

Sintoma: 5xx com message `UndefinedTable: relation "governance.decision_run" does not exist`.

Causa: modelo importado pelo startup mas tabela ainda não existe (DB drop sem
subsequent bootstrap), OU modelo não importado por nenhum caminho até
`Base.metadata.create_all()`.

Fix:
1. `psql -d prodplan_one -c "\dt governance.*"`
2. Se faltam tabelas: `scripts/bootstrap_dev_full.py`
3. Se a tabela existe noutros schemas mas não neste: confirmar import do
   modelo (`grep -r "class DecisionRun" src/`)

### 4.2 `type "<x>" already exists` (dev)

Sintoma: alembic `DuplicateObjectError: type "schedule_status" already exists`.

Causa: collision entre `init_db()` create_all e Alembic migrations.

Fix: drop DB completo + bootstrap_dev_full (§1).

### 4.3 `database "prodplan_one" is being accessed by other users`

Causa: uvicorn ou pytest têm sessions abertas.

Fix: passos 1-2 de §1 (`pg_terminate_backend` + kill local processes).

### 4.4 Accidental `DROP TABLE` in production

The single most expensive 30 seconds you can have on the NELO box.

```bash
# 1. STOP writes immediately.
sudo systemctl stop prodplan-api

# 2. If the drop was minutes ago, prefer PITR (pgBackRest, §3.6) so you
#    keep everything else after the drop. If you can afford to lose since
#    03:00 UTC (the last pg_dump), use §3.4 instead.
sudo -u postgres pgbackrest --stanza=prodplan --type=time \
    --target="<timestamp BEFORE the drop>" restore
sudo systemctl start postgresql

# 3. Smoke test, then resume.
sudo /opt/nelinho/scripts/dr-smoke.sh
sudo systemctl start prodplan-api
```

Always favour PITR over `pg_dump` restore for accidental DDL — losing
≤5 min of WAL is cheaper than losing 24 h of writes.

### 4.5 Filesystem corruption on the data dir

```bash
# 1. Boot into rescue mode, fsck the volume. If the data dir is unreadable,
#    treat as full-box loss → docs/disaster-recovery.md §3.3.
# 2. If recoverable but Postgres won't start, do NOT pg_resetwal — it's a
#    one-way ticket to silent corruption. Restore from the latest pg_dump:
LATEST=$(ls -1t /var/backups/nelinho/nelinho_*.dump | head -1)
sudo -u postgres dropdb --if-exists prodplan_one
sudo -u postgres createdb prodplan_one OWNER prodplan
sudo -u postgres pg_restore --dbname=prodplan_one --jobs=4 \
    --no-owner --no-privileges "$LATEST"
sudo systemctl start prodplan-api
```

### 4.6 Postgres lost entirely (cluster gone)

Full-box-loss path: [`docs/disaster-recovery.md`](../docs/disaster-recovery.md)
§3.3. The pgBackRest restore there handles a brand-new cluster.

### 4.7 `extension "vector" is not available` (dev)

Esperado em scoop postgres 18 dev. Migration 008 tem skip graceful. Usar
`bootstrap_dev_full.py` em vez de `alembic upgrade head` para evitar.

### 4.8 Backend `exit code 255` randomly

Normalmente uvicorn die — pytest concurrente esgotou pool de DB.

Fix: restart uvicorn. Em CI separar processos não conflituam.

### 4.9 Realtime (Kafka) returning 503 in dev

`/v1/realtime/events` retorna 503 quando Kafka offline — RealtimeBridge
fail-closed. Isto **NÃO é um bug** em dev. Frontend cai a polling
automaticamente. Não instalar Kafka em dev.

---

## 5. Backup health monitoring

The nightly job is only useful if its failures are loud.

1. **`journalctl -u nelinho-backup -n 100`** after every drill — confirm
   `Backup OK:` line and the dump size is in the expected range
   (~few MB for empty dev, growing with ERP sync data).
2. **Prometheus `BackupStale` alert** (defined in
   `monitoring/prometheus/alerts.yml`) fires if no fresh dump appears
   within 36 h. It pages whoever owns the on-call rotation.
3. **Quarterly drill** — `scripts/restore_drill.sh` (Sprint Q.13.B / B6)
   takes the latest dump, restores it to a temp DB, runs a smoke test,
   and drops the temp DB. Run it manually after any schema migration
   that changed how tables are wired.

```bash
# Quick health check (any operator can run this):
ls -lh /var/backups/nelinho/ | tail -10
# Latest file should be < 36h old; sizes should be roughly stable.

# Sanity dump on the latest:
LATEST=$(ls -1t /var/backups/nelinho/nelinho_*.dump | head -1)
pg_restore --list "$LATEST" | wc -l
# Expect > 500 TOC entries (16 schemas × ~10 tables average).
```

### Retention & offsite

- Local retention: `NELINHO_BACKUP_RETENTION_DAYS` (default 30) — fits a
  month of dumps on the tower's data volume.
- Offsite copy: set `NELINHO_BACKUP_OFFSITE=nelo-backup.local:/srv/nelinho/`
  in `/etc/nelinho/backup.env` to `rsync` each fresh dump to the NELO
  backup box. Failures are non-fatal (the local dump is kept), but they
  log a `WARN` to journald and trip the `OffsiteBackupStale` alert.
- Long-term archive: pgBackRest already covers this in `docs/disaster-recovery.md`.
  Don't double-archive `pg_dump` files manually.

---

## 6. Verifying the recovery worked

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

# 5. (Prod only) DR smoke
sudo /opt/nelinho/scripts/dr-smoke.sh
```

Se os 5 passam, recovery completa.

---

## 7. Common rationalizations

| "Vou correr alembic upgrade head em vez do bootstrap_dev_full" | Vai falhar em pgvector. bootstrap_dev_full é o caminho dev. |
| "Vou editar a migration que falhou para a fazer passar" | Migration são fact. Se a migration está errada, **fixa o modelo**, gera nova migration. Editing migrations history breaks reproducibility. |
| "DROP DATABASE só em prod, em dev edito à mão" | A dev em estado não-reproduzível é dívida. Sempre passar pelo bootstrap. |
| "Adiciono um try: except em init_db para suprimir o erro" | Bare except esconde bugs. Confirma que o modelo está importado correctamente. |
| "pg_dump nightly chega — não preciso de pgBackRest" | Em produção perdes até 24h de writes. pgBackRest dá ≤5 min RPO. As duas paths são complementares. |
| "Vou fazer pg_resetwal para o Postgres arrancar" | One-way ticket para silent corruption. Restore from `pg_dump` (§3.4) ou pgBackRest (`disaster-recovery.md` §3.3). |
| "O backup falhou ontem mas a app trabalha, vejo amanhã" | Backup silencioso é o pior tipo de bug. Resolve hoje — `journalctl -u nelinho-backup` + `/var/backups/nelinho/`. |
