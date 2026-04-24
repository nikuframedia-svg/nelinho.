#!/usr/bin/env bash
# ProdPlan ONE — DR smoke checks (Sprint J.2)
#
# Run immediately after a restore. Exits non-zero on any failure so
# `if scripts/dr-smoke.sh; then …` is a reliable gate.

set -euo pipefail

API="${PRODPLAN_API:-http://localhost:8000}"
OLLAMA="${OLLAMA_URL:-http://localhost:11434}"

pass=0
fail=0

check() {
    local label="$1"; shift
    printf "%-44s" "$label"
    if "$@" >/dev/null 2>&1; then
        echo "OK"
        pass=$((pass + 1))
    else
        echo "FAIL"
        fail=$((fail + 1))
    fi
}

check "API /v1/ping"           curl -sf "$API/v1/ping"
check "Realtime /health"       curl -sf "$API/v1/realtime/health"
check "Metrics endpoint"       curl -sf "$API/metrics"
check "Postgres SELECT 1"      sudo -u postgres psql -c 'SELECT 1'
check "Kafka topic list"       bash -lc 'kafka-topics.sh --bootstrap-server localhost:9092 --list'
check "Ollama /api/tags"       curl -sf "$OLLAMA/api/tags"

echo "---"
echo "Passed: $pass  |  Failed: $fail"

if [ "$fail" -gt 0 ]; then
    echo "SMOKE CHECK: FAILED"
    exit 1
fi
echo "SMOKE CHECK: PASSED"
