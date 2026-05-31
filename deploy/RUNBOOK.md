# Runbook — instalar o nelinho na torre da fábrica NELO

> Guia passo-a-passo para pôr o ProdPlan ONE a correr em produção, ligado ao
> ERP vivo MAR-KAYAKS. Tudo numa torre só: Postgres + FastAPI + Ollama + Caddy.
> Comandos para Linux (systemd). Owner: Luis.

## 0. Pré-requisitos na torre

| Componente | Notas |
|---|---|
| Python 3.11 | `python3.11 -m venv` para o `.venv` |
| PostgreSQL 16 | serviço systemd `postgresql.service` (o unit do nelinho depende dele) |
| Redis | serviço `redis-server.service`; rate-limiting cai para memória se faltar |
| Ollama + modelo Gemma | `ollama pull gemma4:e4b` (+ `nomic-embed-text` para embeddings) |
| Caddy | reverse-proxy + TLS; usa `deploy/Caddyfile` |
| **ODBC Driver 18 for SQL Server** | do SO — necessário para o adapter do ERP. NÃO é pacote pip |

## 1. Instalar o nelinho

```bash
sudo mkdir -p /opt/prodplan /etc/prodplan /var/log/prodplan /var/lib/prodplan
# copiar o repositório para /opt/prodplan (git clone ou cópia do PC de dev)
cd /opt/prodplan
python3.11 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

`requirements.txt` já inclui `aioodbc` + `pyodbc` (adapter do ERP).

## 2. Configurar

```bash
cp /opt/prodplan/.env.production.example /etc/prodplan/env
# editar /etc/prodplan/env e preencher TODOS os CHANGE_ME:
#   SECRET_KEY      -> openssl rand -hex 32
#   DATABASE_URL / POSTGRES_PASSWORD / REDIS_PASSWORD
#   SQLSERVER_URL   -> credenciais reais do ERP (conta DataReader-only)
#   PRODPLAN_HOST   -> o FQDN da torre (ex.: pp1.nelo.local)
sudo chmod 600 /etc/prodplan/env   # contém segredos
```

`ENVIRONMENT=production` liga o RBAC estrito e o fail-closed do auth; o
arranque recusa um `SECRET_KEY` de dev.

## 3. Base de dados

A cadeia Alembic está sã (1 head). O systemd corre `alembic upgrade head` antes
de arrancar (`ExecStartPre`) — é idempotente.

**CRÍTICO (Q.135):** numa BD FRESCA, correr `scripts/init-db.sql` ANTES do
`alembic upgrade head`. As migrações usam `uuid_generate_v4()` mas nenhuma cria
a extensão; `init-db.sql` cria as extensões (`uuid-ossp`, `pgcrypto`) + os
schemas base. Sem este passo o `upgrade head` rebenta em "uuid_generate_v4()
does not exist".

```bash
# primeira vez, criar a BD + extensões/schemas + correr as migrations:
sudo -u postgres createdb prodplan_one
sudo -u postgres psql -d prodplan_one -f /opt/prodplan/scripts/init-db.sql
cd /opt/prodplan && ./.venv/bin/alembic upgrade head
```

`alembic upgrade head` cria as 124 tabelas ORM TODAS (incl. governance.*),
verificado pelo guard `tests/integration/test_alembic_table_parity.py` (Q.135).
O `init_db()` do arranque (Q.61.16) **só verifica a revisão** — NÃO faz
`create_all` (esse é só o caminho dev/tests `init_db_create_all`).

## 4. Build do frontend

O Caddy serve o bundle estático; o frontend fala com a API na mesma origem.

```bash
cd /opt/prodplan/frontend
echo "VITE_API_URL=https://pp1.nelo.local" > .env.production   # ajustar ao FQDN
npm install && npm run build        # gera frontend/dist/
```

`.env.production` está no `.gitignore` — cria-se na torre, não vem do git.

## 5. Caddy + systemd

```bash
sudo cp /opt/prodplan/deploy/systemd/prodplan-api.service /etc/systemd/system/
sudo cp /opt/prodplan/deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl enable --now prodplan-api
sudo systemctl reload caddy
```

O uvicorn fica em `127.0.0.1:8000`; o Caddy termina o TLS em `:443` e faz
proxy. Em LAN (`.local`) o Caddy usa a CA interna (`tls internal`).

## 6. Smoke test

```bash
systemctl status prodplan-api          # active (running)
curl -k https://pp1.nelo.local/health  # 200
journalctl -u prodplan-api -n 50       # sem tracebacks no arranque
```

Abrir o browser → `https://pp1.nelo.local/` → a DirecaoPage carrega.

## 7. Ligar o ERP vivo

```bash
cd /opt/prodplan
./.venv/bin/python scripts/validate_nelo_erp.py     # valida a ligação read-only
./.venv/bin/python scripts/sync_nelo_erp.py         # corre os 5 mirrors ETL
./.venv/bin/python scripts/check_nelo_sync.py       # confere o resultado
```

Depois confirmar que `core.products`, `core.employees`,
`plan.routing_template_phase`, `hr.skills`, `quality.*` têm contagens reais.
O sync nightly fica agendado pelo APScheduler (Q.25.D).

## 8. Operação do dia-a-dia

- **Logs:** `journalctl -u prodplan-api -f` · Caddy: `/var/log/prodplan/`.
- **Reiniciar:** `sudo systemctl restart prodplan-api`.
- **Backups Postgres:** agendar `pg_basebackup`/pgBackRest nightly + testar restore.
- **Sync do ERP:** corre sozinho de noite; verificar `core.etl_run` se houver dúvidas.

## 9. Caveats conhecidos

- **Frontend em `/` vs `/app/`** — o `Caddyfile` tem um bloco `handle_path
  /app/*`, mas o `vite.config.ts` não define `base`. Decidir na instalação:
  servir o SPA em `/` (e mover os assets do API para fora de `/`) **ou** pôr
  `base: '/app/'` no `vite.config.ts` e rebuildar. Confirmar com um teste no
  browser antes do go-live.
- **Kafka** — desligado de propósito (`KAFKA_BOOTSTRAP_SERVERS` vazio); o
  `/v1/realtime/events` pode dar 503, é esperado.
- **pgvector** — o RAG do copiloto precisa da extensão; sem ela faz fallback.
- A conta do ERP é **DataReader-only** — o nelinho nunca escreve no MAR-KAYAKS.
