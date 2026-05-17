# Runbook de instalação on-prem — ProdPlan ONE / nelinho

> Receita passo-a-passo para instalar o nelinho de raiz no servidor da NELO
> (Vila do Conde). Deploy **nativo** (sem Docker), Linux + systemd.
>
> Este documento cobre a **primeira instalação**. Para recuperação de desastre
> (perda de máquina, restauro de backups) ver `docs/disaster-recovery.md`.
> Para problemas de dev/arranque ver o skill `nelinho-debug`.

---

## 0. Resumo do que vamos montar

```
  Internet / LAN
       │  :443 (TLS)
       ▼
   ┌────────┐   :8000      ┌──────────────┐
   │ Caddy  │ ───────────▶ │ Uvicorn /API │
   └────────┘  127.0.0.1   └──────┬───────┘
                                  │
                  ┌───────────────┼───────────────┐
                  ▼               ▼               ▼
            Postgres 16       Redis           Ollama (RTX)
            127.0.0.1:5432    :6379           :11434
```

Quatro serviços geridos por `systemd`: `postgresql`, `redis-server`,
`prodplan-api` e `caddy`. O Ollama é opcional (só features de copiloto LLM).

---

## 1. Pré-requisitos

| Componente | Versão mínima | Notas |
|---|---|---|
| OS | Linux com systemd | Debian 12 / Ubuntu 22.04+ recomendado |
| Python | 3.11 | a venv vive em `/opt/prodplan/.venv` |
| PostgreSQL | 16 | porta 5432, localhost |
| Redis | 7 | rate-limit + conversas do copiloto |
| Caddy | 2.7+ | reverse proxy + TLS — binário em `/usr/bin/caddy` |
| Node.js | 20+ | só para compilar o frontend (`npm run build`) |
| Ollama | opcional | LLM local; sem ele o copiloto fica degradado |

Hardware: o servidor já montado na NELO (32 GB RAM, RTX 5060 Ti). Os limites
do `prodplan-api.service` (`MemoryMax=8G`, `CPUQuota=400%`) assumem este perfil.

### 1.1 Utilizadores de sistema

```bash
sudo useradd --system --home /opt/prodplan --shell /usr/sbin/nologin prodplan
sudo useradd --system --home /var/lib/caddy --shell /usr/sbin/nologin caddy
```

### 1.2 Directórios

```bash
sudo mkdir -p /opt/prodplan /etc/prodplan \
              /var/log/prodplan /var/lib/prodplan /var/lib/caddy
sudo chown prodplan:prodplan /opt/prodplan /var/lib/prodplan
sudo chown caddy:caddy        /var/lib/caddy
sudo chmod 750 /etc/prodplan         # o env tem segredos
# /var/log/prodplan é escrito pela API e pelo Caddy:
sudo chgrp prodplan /var/log/prodplan && sudo chmod 775 /var/log/prodplan
```

---

## 2. Obter o código e a venv

```bash
sudo -u prodplan git clone https://github.com/nikufra-ai/prodplan-one /opt/prodplan
cd /opt/prodplan
sudo -u prodplan python3.11 -m venv .venv
sudo -u prodplan .venv/bin/pip install --upgrade pip
sudo -u prodplan .venv/bin/pip install -r requirements.txt
```

Frontend (servido estaticamente pelo Caddy a partir de `frontend/dist`):

```bash
cd /opt/prodplan/frontend
sudo -u prodplan npm ci
sudo -u prodplan npm run build      # produz frontend/dist
```

---

## 3. Configuração — `/etc/prodplan/env`

O `prodplan-api.service` e o `caddy.service` lêem ambos `/etc/prodplan/env`.
Partir de `.env.example` e preencher os valores reais:

```bash
sudo cp /opt/prodplan/.env.example /etc/prodplan/env
sudo chown root:prodplan /etc/prodplan/env
sudo chmod 640 /etc/prodplan/env
sudo nano /etc/prodplan/env
```

Valores **obrigatórios** a mudar em produção:

| Chave | Valor |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://prodplan:<pw>@localhost:5432/prodplan_one` |
| `POSTGRES_PASSWORD` | password forte (gerar com `openssl rand -hex 24`) |
| `SECRET_KEY` | `openssl rand -hex 64` — **nunca** a chave de dev |
| `REDIS_PASSWORD` | password do Redis |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `PRODPLAN_HOST` | FQDN do servidor, ou `prodplan.local` para LAN-only |

> **PENDENTE — confirmar com o Luis:** o domínio/FQDN e se há certificado
> público. Sem domínio real, deixar `PRODPLAN_HOST=prodplan.local` — o Caddy
> emite um certificado da sua CA interna (`tls internal`); os browsers da
> fábrica precisam de confiar nessa CA uma vez (ver §6).

Para ligar o ERP vivo (Plano A / Q.25) há mais chaves — `sqlserver_url`,
`sqlserver_enabled`. Fora do âmbito deste runbook; ver `goal-nelinho-producao.md`.

---

## 4. Base de dados

```bash
# Criar o role e a base de dados (como utilizador postgres):
sudo -u postgres psql -c "CREATE USER prodplan WITH PASSWORD '<pw>';"
sudo -u postgres psql -c "CREATE DATABASE prodplan_one OWNER prodplan;"
```

O schema é criado pelas **migrations Alembic**. O `prodplan-api.service`
corre `alembic upgrade head` no `ExecStartPre` a cada arranque (idempotente —
no-op quando já está no head), portanto na maioria dos casos não é preciso
correr nada à mão. Para validar antes do primeiro arranque:

```bash
cd /opt/prodplan
sudo -u prodplan PYTHONPATH=/opt/prodplan .venv/bin/alembic upgrade head
```

> **pgvector:** a migration 008 (embeddings) faz *graceful skip* se a extensão
> `pgvector` não estiver disponível. RAG/embeddings ficam dormentes — não
> bloqueia o arranque. Instalar `pgvector` só se as features de RAG forem
> critical-path.

> **Migration vs `create_all`:** algumas tabelas `governance.*` só são criadas
> pelo `init_db()` no arranque da app, não por Alembic (dívida conhecida). Se
> aparecer `UndefinedTable` num endpoint de governance, ver o skill
> `nelinho-debug`.

Dados de arranque (tenant, configs base) — só na **primeira** instalação:

```bash
sudo -u prodplan PYTHONPATH=/opt/prodplan .venv/bin/python scripts/bootstrap_dev_full.py
```

---

## 5. Instalar os serviços systemd

```bash
sudo cp /opt/prodplan/deploy/systemd/prodplan-api.service /etc/systemd/system/
sudo cp /opt/prodplan/deploy/systemd/caddy.service        /etc/systemd/system/
sudo systemctl daemon-reload
```

O `caddy.service` lê o Caddyfile de `/opt/prodplan/deploy/Caddyfile` — não é
preciso copiá-lo. Editar lá se for preciso afinar headers/rotas.

### Ordem de arranque (importante)

Postgres e Redis primeiro, depois a API, depois o Caddy:

```bash
sudo systemctl enable --now postgresql redis-server
sudo systemctl enable --now prodplan-api      # corre as migrations e sobe o Uvicorn
sudo systemctl enable --now caddy             # termina o TLS e faz proxy
```

`enable --now` arranca já **e** marca para arrancar no boot. Depois disto o
sistema sobrevive a um reboot sem intervenção (o `After=`/`Wants=` nos units
trata da sequência).

---

## 6. Verificação de saúde

```bash
# 1. A API responde directamente (loopback):
curl -s http://127.0.0.1:8000/health
#    esperado: {"status":"healthy","service":"prodplan-one"}

# 2. Readiness — confirma DB + Redis (+ Kafka se não-dev):
curl -s http://127.0.0.1:8000/health/ready
#    esperado: HTTP 200 {"status":"ready","checks":{"database":true,"redis":true}}
#    503 = alguma dependência em baixo (ver checks no corpo)

# 3. Através do Caddy, com TLS:
curl -sk https://prodplan.local/health
#    esperado: o mesmo JSON do passo 1

# 4. O frontend é servido em /app:
curl -skI https://prodplan.local/app/ | head -1
#    esperado: HTTP/2 200
```

Estado dos serviços e logs:

```bash
systemctl status prodplan-api caddy
journalctl -u prodplan-api -n 50 --no-pager
journalctl -u caddy        -n 50 --no-pager
```

CA interna do Caddy (deploy LAN-only): exportar o certificado raiz e instalá-lo
uma vez nos PCs/tablets da fábrica para tirar o aviso de "ligação não segura":

```bash
# o ficheiro fica em (XDG_DATA_HOME está definido para /var/lib/caddy no unit):
ls /var/lib/caddy/caddy/pki/authorities/local/root.crt
```

Monitorização (Prometheus + Grafana + alertas) já existe — ver os cabeçalhos de
`monitoring/prometheus/prometheus.yml` e `docs/disaster-recovery.md` §5.

---

## 7. Recuperação rápida

| Sintoma | Acção |
|---|---|
| API não arranca | `journalctl -u prodplan-api -n 80` — normalmente migration ou env errado |
| `/health/ready` → 503 | ver `checks` no corpo; subir o serviço em falta (Postgres/Redis) |
| Caddy não arranca | `caddy validate --config /opt/prodplan/deploy/Caddyfile` mostra o erro |
| Reload sem downtime | `sudo systemctl reload caddy` (recarrega o Caddyfile) |
| Reiniciar a API | `sudo systemctl restart prodplan-api` (corre migrations de novo) |
| Pôr o sistema todo em baixo | `sudo systemctl stop caddy prodplan-api` |
| Perda total da máquina | seguir `docs/disaster-recovery.md` §3.3 |
| Erros de schema / dev | skill `nelinho-debug` (tabela sintoma→causa→recuperação) |

Após um reboot, confirmar que tudo subiu sozinho:

```bash
systemctl is-active postgresql redis-server prodplan-api caddy
#  esperado: active (x4)
```

---

## 8. Actualizar uma instalação existente

```bash
cd /opt/prodplan
sudo -u prodplan git pull
sudo -u prodplan .venv/bin/pip install -r requirements.txt
cd frontend && sudo -u prodplan npm ci && sudo -u prodplan npm run build && cd ..
sudo systemctl restart prodplan-api    # ExecStartPre corre alembic upgrade head
sudo systemctl reload caddy            # só se o Caddyfile mudou
```

Confirmar com a verificação de saúde do §6.

---

## 9. Trabalho futuro — CD (Q.29.C)

Hoje a actualização é manual (§8). Automação possível, **não feita** de
propósito (a máquina está montada on-site, deploy é prioridade menor —
decisão registada em `goal-nelinho-producao.md`, Plano E):

- *runner* de CI no servidor da NELO que faz `git pull` + restart num push
  para `main` (ou num tag de release);
- script `deploy/install.sh` que encadeia os §2–§5 (o `.env.example` e o
  `KNOWN_ISSUES.md` já o referenciam, mas o ficheiro ainda não existe);
- *health-gate* pós-deploy que faz rollback se o `/health/ready` falhar.

Antes de investir nisto, confirmar com o Luis que a frequência de releases
justifica a automação. Enquanto for raro, o §8 chega.
