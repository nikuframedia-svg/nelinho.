# Observability runbook — Prometheus + Grafana (Q.68.2.D)

> Como pôr observabilidade a correr na torre NELO. Prometheus apanha métricas
> do FastAPI (`/metrics`), Postgres, Kafka, Ollama; Grafana mostra dashboards.
> Sem Docker — tudo nativo + systemd, como o resto do nelinho.
>
> Owner: Luis. Tudo numa torre só.

## 0. Mapa rápido

| Ficheiro | O que é | Editado por |
|---|---|---|
| `deploy/prometheus.yml` | Config principal: scrape targets + global | repo |
| `monitoring/prometheus/prometheus.yml` | Versão "rica" (com node/postgres/kafka exporters) — usa esta se tiveres os exporters instalados | repo |
| `monitoring/prometheus/alerts.yml` | Regras de alerta (APIDown, High5xxRate, …) | repo |
| `deploy/systemd/prometheus.service` | systemd unit do Prometheus | repo |
| `deploy/systemd/grafana.service` | systemd unit do Grafana (drop-in override se vier do apt) | repo |
| `deploy/grafana.ini` | Config nativa do Grafana (provisioning + admin no env) | repo |
| `monitoring/grafana/dashboards/*.json` | Dashboards Grafana (sources of truth) | repo |
| `monitoring/grafana/provisioning/dashboards.yaml` | Provisioning automático | repo |

## 1. Instalar Prometheus

```bash
# Binário oficial — mais estável que apt
cd /opt
sudo wget -q https://github.com/prometheus/prometheus/releases/download/v3.0.0/prometheus-3.0.0.linux-amd64.tar.gz
sudo tar xvf prometheus-3.0.0.linux-amd64.tar.gz
sudo ln -sf /opt/prometheus-3.0.0.linux-amd64 /opt/prometheus

# User dedicated
sudo useradd --no-create-home --shell /bin/false prometheus
sudo mkdir -p /var/lib/prometheus
sudo chown -R prometheus:prometheus /opt/prometheus /var/lib/prometheus

# systemd
sudo cp /opt/nelinho/deploy/systemd/prometheus.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now prometheus

# Verificar
systemctl status prometheus
curl -fsS http://localhost:9090/-/healthy        # esperado: Prometheus Server is Healthy.
curl -fsS http://localhost:9090/api/v1/targets | head
```

Se quiseres usar o `monitoring/prometheus/prometheus.yml` (com alertas +
exporters node/postgres/kafka/ollama), instala primeiro os exporters:

```bash
sudo apt install -y prometheus-node-exporter prometheus-postgres-exporter
# Kafka JMX exporter + Alertmanager: instruções em monitoring/prometheus/prometheus.yml
```

…e ajusta o `ExecStart` do unit para apontar para esse ficheiro em vez
de `deploy/prometheus.yml`.

## 2. Instalar Grafana

```bash
# Pacote oficial (mais fácil de actualizar)
curl -fsSL https://apt.grafana.com/gpg.key | sudo gpg --dearmor \
    -o /usr/share/keyrings/grafana.gpg
echo "deb [signed-by=/usr/share/keyrings/grafana.gpg] https://apt.grafana.com stable main" \
    | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt update && sudo apt install -y grafana

# Admin password no env (NUNCA hardcoded)
sudo tee /etc/grafana/env >/dev/null <<EOF
GF_SECURITY_ADMIN_USER=admin
GF_SECURITY_ADMIN_PASSWORD=$(openssl rand -base64 24)
EOF
sudo chmod 600 /etc/grafana/env

# Provisioning de datasource + dashboards (1× só)
sudo mkdir -p /etc/grafana/provisioning/datasources \
              /etc/grafana/provisioning/dashboards \
              /var/lib/grafana/dashboards

sudo tee /etc/grafana/provisioning/datasources/prometheus.yaml >/dev/null <<EOF
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    uid: prometheus
    url: http://localhost:9090
    access: proxy
    isDefault: true
    editable: false
EOF

sudo ln -sf /opt/nelinho/monitoring/grafana/provisioning/dashboards.yaml \
            /etc/grafana/provisioning/dashboards/nelinho.yaml
sudo ln -sf /opt/nelinho/monitoring/grafana/dashboards \
            /var/lib/grafana/dashboards/nelinho
sudo chown -R grafana:grafana /etc/grafana /var/lib/grafana

# Drop-in override em vez de substituir o unit do pacote:
sudo mkdir -p /etc/systemd/system/grafana-server.service.d
# Copiar apenas a secção [Service] do nosso unit para um override:
sudo cp /opt/nelinho/deploy/systemd/grafana.service \
        /etc/systemd/system/grafana-server.service.d/override.conf
sudo systemctl daemon-reload
sudo systemctl enable --now grafana-server

# Verificar
systemctl status grafana-server
curl -fsS http://localhost:3000/api/health        # esperado: {"database":"ok",...}
```

Abrir `http://<torre-ip>:3000` no browser, login com a admin password do
`/etc/grafana/env`. Os dashboards aparecem na folder *ProdPlan*.

## 3. Dashboards principais

Definidos em `monitoring/grafana/dashboards/`:

| Dashboard | O que mostra | Quando consultar |
|---|---|---|
| `prodplan-overview.json` | SLO 99% uptime, taxa 5xx/4xx, latência P95 HTTP, status de sub-sistemas (DB/Kafka/Ollama) | Diariamente — health-check rápido |
| `prodplan-cpo-performance.json` | Latência P50/P95/P99 do scheduler CPO, throughput de jobs, generations/min do GA | Depois de planeamento em produção, ou se "Plan" demora > 30s |
| `prodplan-silent-fallbacks.json` | `prodplan_silent_fallback_total{module,reason}` — todo o sítio onde o código apanhou erro e devolveu default | Semanalmente — qualquer valor > 0 é regressão silenciosa |
| `deploy/grafana/dashboards/direcao.json` | KPIs para o Luis: outbox lag, Kafka health, latência HTTP, sub-sistemas degradados | Sempre que houver suspeita de drift operacional |

Painéis cobrem (entre outros):
- **App overview** — `up{job="nelinho-api"}`, request rate, error rate
- **Copilot latency** — `prodplan_copilot_request_duration_seconds_bucket`
- **CPO jobs** — `prodplan_cpo_solve_duration_seconds`, fitness convergence
- **Outbox status** — `prodplan_outbox_dispatcher_latency_seconds`
- **ETL freshness** — `prodplan_erp_sync_last_success_seconds_ago`
- **Silent fallbacks** — `prodplan_silent_fallback_total` (vital — explicit > implicit)

## 4. Alertmanager (opcional, mas recomendado)

```bash
sudo apt install -y prometheus-alertmanager
sudo tee /etc/prometheus/alertmanager.yml >/dev/null <<EOF
route:
  receiver: 'luis-email'
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
receivers:
  - name: 'luis-email'
    email_configs:
      - to: 'luis@nikufra.ai'
        from: 'nelinho@nelo.local'
        smarthost: 'smtp.gmail.com:587'
        auth_username: '...'
        auth_password: '...'
EOF
sudo systemctl enable --now prometheus-alertmanager
```

Críticos para o Luis (severity=critical em `alerts.yml`):
- `APIDown` (2m sem `/metrics`)
- `PostgresDown` (1m sem ligação)
- `KafkaDown` (3m sem broker)
- `High5xxRate` (>5% 5xx por 5m)
- `HostDiskCritical` (<10% free)
- `PostgresReplicationLagHigh` (>60s — RPO em risco)
- `BackupStale` (>26h sem backup)

Sub-sistemas degradados (severity=warning):
- `OllamaDown`, `OutboxLagHigh`, `TrustIndexCollapsed`, `SilentFallbackRateHigh`

## 5. Verificação end-to-end

```bash
# 1. App expõe métricas?
curl -fsS http://localhost:8001/metrics | grep -E '^prodplan_' | head -5

# 2. Prometheus a scrape com sucesso?
curl -fsS 'http://localhost:9090/api/v1/query?query=up' \
  | python3 -m json.tool | grep -A2 '"value"'
#   { "value": [..., "1"] } por cada target — 1=up, 0=down

# 3. Grafana lê do Prometheus?
curl -fsS -u admin:$GF_PWD \
    http://localhost:3000/api/datasources/proxy/1/api/v1/query?query=up \
  | python3 -m json.tool

# 4. Alerts armed?
curl -fsS http://localhost:9090/api/v1/rules | python3 -m json.tool \
  | grep -c '"state":"inactive"'
#   deve devolver o nº total de regras em alerts.yml
```

## 6. Troubleshooting

**Scrape failures (`up == 0`)**
1. `journalctl -u prometheus --since '5 min ago' | tail -30`
2. Confirmar que o target está vivo: `curl -fsS http://localhost:<porta>/metrics`
3. Firewall: o Prometheus precisa chegar a `localhost:8001` (api),
   `:9100` (node), `:9187` (postgres), `:7071` (kafka), `:11434` (ollama).
4. Se `nelinho-api` está em `:8000` em vez de `:8001`, editar
   `deploy/prometheus.yml:39` (e *não* alterar `src/main.py`).

**Grafana dashboard "No data"**
1. Datasource: *Connections → Data sources → Prometheus → Test* deve passar.
2. Confirmar que o painel usa `uid: prometheus` (não nome qualquer).
3. Time range: dashboards default a "last 1h" — se o serviço só arrancou
   agora, mete em "last 5m".
4. `curl -fsS http://localhost:9090/api/v1/label/__name__/values | head`
   — se `prodplan_*` não aparecer, o problema é no scrape, não no Grafana.

**Grafana não arranca após drop-in override**
1. `systemctl status grafana-server` — procurar `Failed to parse config`.
2. Se o override conflitua com o unit do pacote, simplificar: manter só
   `ExecStart=` + `Environment=GF_PATHS_CONFIG=/opt/nelinho/deploy/grafana.ini`.
3. Logs detalhados: `journalctl -u grafana-server -n 100 --no-pager`.

**Prometheus consome muito disco**
1. `du -sh /var/lib/prometheus` — esperado < 5 GB para 30d com 15s scrape.
2. Reduzir retenção: editar `prometheus.service` para
   `--storage.tsdb.retention.time=15d` e reiniciar.
3. Drop labels de alta cardinalidade no `relabel_configs`.

**Dashboard JSON editado pela UI não persiste**
- Esperado: `monitoring/grafana/provisioning/dashboards.yaml` tem
  `allowUiUpdates: true`, mas a fonte de verdade continua a ser o JSON
  no repo. Para guardar uma alteração da UI: exportar JSON
  (*Dashboard settings → JSON Model*) e commit para `monitoring/grafana/dashboards/`.

## 7. Manutenção

- **Upgrade Prometheus**: pôr o serviço down, trocar o symlink
  `/opt/prometheus`, restart. Migrations da TSDB são auto.
- **Upgrade Grafana**: `sudo apt update && sudo apt install grafana` —
  o pacote preserva `/etc/grafana/env` e `/var/lib/grafana/grafana.db`.
- **Backups**: incluir `/var/lib/prometheus` (TSDB) + `/var/lib/grafana/grafana.db`
  no rsync diário. Sem isto, perde-se 30d de histórico mas dashboards reaparecem
  do repo (provisioning).
