# Load tests (Sprint J.1)

k6 scripts for ProdPlan ONE. Run against the on-prem stack at Nelo,
not CI — k6 is a standalone binary and nothing in this folder is
imported by pytest.

## Install

```bash
# Native install on Ubuntu (docs.k6.io):
sudo gpg -k
sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
    --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
    | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install -y k6
```

## Scripts

| Script | Purpose | Run with |
|---|---|---|
| `k6-smoke.js` | 30 s, 1 VU — proves the app is up and routes respond. Runs after every deploy. | `k6 run tests/load/k6-smoke.js` |
| `k6-read-load.js` | 5 min, ramps 1 → 50 VUs. Measures read-path P95. Use for capacity planning. | `k6 run tests/load/k6-read-load.js` |
| `k6-cpo-stress.js` | 30 min, 10 concurrent schedules, SLA target 50 concurrent. Stress test the GA. | `k6 run --quiet tests/load/k6-cpo-stress.js` |

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PRODPLAN_BASE` | `http://localhost:8000` | API base URL |
| `PRODPLAN_TENANT` | `00000000-0000-0000-0000-000000000000` | Tenant header |
| `PRODPLAN_USER` | `load-test-user` | User header |

## Thresholds

Thresholds are encoded inside each script and map to `docs/sla.md`
targets. A failed threshold exits non-zero so CI / cron gates on it.

Example: `k6-read-load.js` enforces `http_req_duration{path:GET}` P95
≤ 500 ms (matches the SLO).
