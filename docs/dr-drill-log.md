# DR drill log

Quarterly DR drill results. Fill in one row per drill so we can spot
RTO regressions over time. See [`disaster-recovery.md`](disaster-recovery.md)
§4 for the procedure.

## Current contract

| SLO | Target | Source |
|---|---|---|
| RTO | ≤ 2h | [`sla.md` §3](sla.md) |
| RPO | ≤ 1h | [`sla.md` §3](sla.md) |
| Drill cadence | every 3 months | [`sla.md` §3](sla.md) |

## Log

| Date | Operator | Scenario | Observed RTO | Observed RPO | Pass/Fail | Notes |
|---|---|---|---|---|---|---|
| _(first drill pending — scheduled for 2026-07-XX)_ | Luis | §3.3 full-box loss | — | — | — | — |

## Drill-run checklist

Copy-paste into a new issue at drill time so nothing is skipped:

```markdown
- [ ] Staging box wiped (Postgres data dir + Kafka data dir)
- [ ] Timer started
- [ ] §3.3.1 Provision (apt-get + venv + systemd units)
- [ ] §3.3.2 Restore Postgres (pgBackRest)
- [ ] §3.3.3 Restore Kafka + Ollama + object-store
- [ ] §3.3.4 App starts + `/v1/ping` returns 200
- [ ] `scripts/dr-smoke.sh` exits 0
- [ ] Grafana dashboard flips green
- [ ] Timer stopped
- [ ] RTO recorded in this log
- [ ] Action items opened for anything slower than expected
```

## Drill history template

When you run a drill, append a section like this:

```markdown
### 2026-07-15 — Full-box restore

- **Operator**: Luis
- **Scenario**: §3.3 — wipe Postgres + Kafka, restore from pgBackRest + rsync
- **Observed RTO**: 1h 47m  ✅ under target
- **Observed RPO**: 22m (WAL archive interval)  ✅ under target
- **Pass/Fail**: Pass

**Timings**:
- Provision: 28m
- Postgres restore: 52m (← 7m over plan; pgBackRest parallel jobs bumped)
- Kafka + object-store: 18m
- Smoke: 9m

**Action items**:
- `INFRA-2026-Q3-01` — bump `pgbackrest` `process-max` from 2 to 4 to cut the 7-minute overrun.
- `INFRA-2026-Q3-02` — add Grafana panel for WAL archive latency.
```

Every row becomes a git commit — no DR drill is "off the record".
