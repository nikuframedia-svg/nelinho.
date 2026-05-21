# Failure Modes Runbook (Q.68.6.B)

Como nelinho se comporta quando subsistemas críticos caem. Sintomas
visíveis + mitigação + restart + escalação.

Este runbook complementa `bootstrap_recovery.md` (recuperação de raiz) e
`observability_runbook.md` (instrumentação Prometheus/Grafana). Use este
documento durante incidentes: cada secção é auto-contida.

Princípio: nelinho prefere **degradar com transparência** a falhar em
silêncio. Cada subsistema crítico tem fallback documentado.

---

## 1. Postgres down — CRITICAL (impacto total)

### Sintomas
- Endpoint `/health/db` retorna 500.
- App não arranca (lifespan falha em `init_db()` / `alembic upgrade head`).
- Frontend mostra "Backend offline" banner global.
- Todas as mutations falham com `5xx`.

### Mitigação imediata
1. `systemctl status postgresql` — verificar se o serviço está up.
2. `journalctl -u postgresql -n 50` — ler últimos erros (OOM kill?).
3. Se OOM kill: aumentar memória/swap, reduzir `shared_buffers`.
4. Se disk full: limpar `/var/lib/postgresql/data/log/` (logs antigos).
5. Se locks bloqueados: `pg_stat_activity` + `pg_terminate_backend(pid)`.

### Restore
- Se DB corrupt: aplicar último backup (ver `bootstrap_recovery.md`).
- Se apenas WAL danificado: PITR para o último checkpoint válido.
- Recovery canónica para dev: drop DB → recreate → `scripts/bootstrap_dev_full.py`.

### Alertas Prometheus
- `PostgresDown` (crítico, page Luis).
- `PostgresReplicationLagHigh` (warning, só se replica configurada).
- `PostgresConnectionsExhausted` (warning, >80% do pool).

### Escalação
- Luis directo (Telegram/SMS).
- Se restore falha: contactar DBA externo (contrato Q.X).

---

## 2. Kafka down — DEGRADED (graceful fallback)

### Sintomas
- SSE eventos não chegam ao frontend (LiveActivityFeed parado).
- `/v1/realtime/status` retorna `{"degraded": true, "fallback": "outbox+notify"}`.
- LOG backend: `kafka unavailable, using event_outbox + LISTEN/NOTIFY fallback`.

### Behaviour (graceful — Q.59.A)
- App continua a funcionar 100% nas operações síncronas.
- Eventos persistem em `event_outbox` (drenam quando Kafka volta).
- Frontend recebe via LISTEN/NOTIFY directo (Q.14.B).
- Nenhuma escrita perdida.

### Mitigação
1. `systemctl restart kafka`.
2. Verificar topic creation (nelinho não pré-cria — broker tem
   `auto.create.topics.enable=true`).
3. Verificar disco em `/var/lib/kafka/logs/` (logs retidos 7d).
4. Confirmar Zookeeper up: `systemctl status zookeeper`.

### Restore
- Outbox drena automaticamente quando Kafka volta (Q.59.A `outbox_drainer`).
- Verificar lag: `SELECT count(*) FROM event_outbox WHERE delivered_at IS NULL`.

### Alertas
- `KafkaDown` (warning, não crítico — fallback existe).
- `EventOutboxLagHigh` (warning, >1000 pendentes).

---

## 3. Redis down — DEGRADED (rate limiter offline)

### Sintomas
- Copilot rate limiter retorna `503` em `/v1/copilot/ask`.
- CPO async (Arq) não enfileira novos jobs.
- Conversation store cai para in-memory (perde histórico em restart).

### Behaviour
- Endpoints críticos (planning, governance, ERP) **não dependem de Redis**.
- Copilot fica indisponível mas resto da app funciona.
- CPO síncrono (via `/v1/plan/run`) continua a operar.

### Mitigação
1. `systemctl restart redis-server`.
2. Verificar memory limit: `redis-cli info memory` (maxmemory atingido?).
3. Verificar persistência: `redis-cli config get appendonly` (deve ser `yes`).

### Alertas
- `RedisDown` (warning).
- `RedisMemoryHigh` (warning, >80% maxmemory).

---

## 4. Ollama down — DEGRADED (copilot offline)

### Sintomas
- Copilot retorna `{"summary": "Não tenho acesso ao modelo LLM neste momento"}`.
- Circuit breaker abre após 3 falhas consecutivas (60s timeout antes de retry).
- Health endpoint mostra `ollama: "down"`.
- Nenhuma chamada LLM é feita enquanto o breaker está aberto.

### Behaviour
- Resto da app funciona normalmente (planning, ERP, governance).
- Frontend mostra empty state explícito no copiloto.
- Não há fallback para outro provider on-prem (intencional — privacy first).

### Mitigação
1. `systemctl restart ollama`.
2. Verificar GPU memory: `nvidia-smi` (gemma4:e4b precisa ~9.6GB VRAM).
3. `ollama list` confirmar modelo presente; se ausente: `ollama pull gemma4:e4b`.
4. Verificar logs: `journalctl -u ollama -n 100`.
5. Se loop de OOM: reduzir `num_ctx` no copilot config.

### Alertas
- `OllamaDown` (warning).
- `OllamaCircuitBreakerOpen` (warning, indicates flapping).
- `OllamaLatencyHigh` (warning, p95 > 15s).

---

## 5. Frontend offline (Caddy / Tailscale)

### Sintomas
- Browser mostra "Connection refused" ou "Site can't be reached".
- Backend `/health` continua a responder se acedido directo (porta 8001).

### Mitigação
1. `systemctl status caddy` — reverse proxy up?
2. `tailscale status` — túnel ativo, peers visíveis?
3. `journalctl -u caddy -n 50` — erros TLS?
4. Restart: `systemctl restart caddy`.
5. Se Tailscale auth expirou: `tailscale up --authkey=...`.

### Alertas
- `CaddyDown` (crítico).
- `TailscaleDisconnected` (crítico se demo remota ativa).

---

## 6. Disk full

### Sintomas
- Logs param de escrever.
- Postgres recusa writes (`could not extend file`).
- Backups falham silenciosamente.
- Kafka pára de aceitar produces.

### Mitigação
1. `df -h` — identificar partição cheia.
2. `du -sh /var/log/* /var/lib/postgresql/* /var/backups/* /var/lib/kafka/*`.
3. Limpar logs antigos: `journalctl --vacuum-time=7d`.
4. Verificar retention backup (30d default em `scripts/backup.sh`).
5. Rodar pg_dump antigo para storage externo se >30 dias.

### Alertas
- `DiskFull` (crítico, page Luis se <5% livre).
- `DiskFillingFast` (warning, projeta cheio em <24h).

---

## 7. Network partition (DB unreachable mas up)

### Sintomas
- App arranca, depois falha em queries com `connection timeout`.
- `/health/db` 500, mas Postgres está up se acedido localmente.

### Mitigação
1. `nc -zv <db_host> 5432` do app host.
2. Verificar `pg_hba.conf` — IP do app está autorizado?
3. Firewall: `iptables -L` / `ufw status`.

---

## Cross-ref

- Prometheus alerts: [`monitoring/prometheus/alerts.yml`](../monitoring/prometheus/alerts.yml)
- Backup procedures: [`agent_docs/bootstrap_recovery.md`](bootstrap_recovery.md)
- Observability runbook: [`agent_docs/observability_runbook.md`](observability_runbook.md)
- Architecture overview: [`agent_docs/architecture.md`](architecture.md)

---

*Q.68.6.B (P18 audit) — runbook canónico para failure modes. Sempre que um*
*novo subsistema crítico for adicionado, criar secção aqui ANTES de fazer merge.*
