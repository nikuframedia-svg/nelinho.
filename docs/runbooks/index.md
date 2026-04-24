# Runbooks

Alert-driven response guides. Every Prometheus alert in
`monitoring/prometheus/alerts.yml` links back to a runbook here.
The goal is a page per alert — under 2 minutes to read, concrete
commands.

## Platform

- [API down](api-down.md)
- [Postgres down](postgres-down.md)
- [Kafka down](kafka-down.md)
- [Ollama down](ollama-down.md)

## Capacity

- [Disk filling up](disk-full.md)
- [Replication lag high](replication-lag.md)
- [High 5xx rate](high-5xx-rate.md)

## Data

- [TrustIndex collapsed](trust-index-collapsed.md)
- [Backup stale](backup-stale.md)

## Incident template

- [Post-incident review](incident-template.md)
