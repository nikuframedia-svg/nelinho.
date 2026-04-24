// ProdPlan ONE — CPO scheduler stress (Sprint J.1)
//
// Exercises the heaviest POST in the system:
//     POST /v1/plan/cpo/schedule
//
// SLO: P95 ≤ 90 s end-to-end. Capacity target: 50 concurrent solves
// (Blueprint §7.2). This script runs 10 concurrent for 30 minutes as
// the first measurement; raise VUs to 50 once the pool survives 10.
//
// IMPORTANT: this script hammers the GA. Run against staging only.

import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.PRODPLAN_BASE || 'http://localhost:8000';
const TENANT = __ENV.PRODPLAN_TENANT || '00000000-0000-0000-0000-000000000000';
const VUS = Number(__ENV.PRODPLAN_VUS || 10);

export const options = {
    vus: VUS,
    duration: __ENV.PRODPLAN_DURATION || '30m',
    thresholds: {
        'http_req_failed': ['rate<0.02'],
        // SLO, tagged separately so read probes don't pollute the
        // histogram.
        'http_req_duration{kind:schedule}': ['p(95)<90000'],
        'checks': ['rate>0.98'],
    },
};

const headers = {
    'Content-Type': 'application/json',
    'X-Tenant-Id': TENANT,
    'X-User-Id': __ENV.PRODPLAN_USER || 'load-test-user',
};

// Seed payload — a realistic 14-day horizon for the current tenant.
// The backend resolves orders + machines + operations from the DB so
// we don't ship them in the body; `proposal` is the minimum contract.
const body = JSON.stringify({
    proposal: 'Load test — auto-generate plan',
    delta: { entity_type: 'load_test', patch: {} },
    horizon_days: 14,
    time_limit_sec: 30,
    population_size: 50,
    generations: 20,
});

export default function () {
    const res = http.post(`${BASE}/v1/copilot/poetiq/propose`, body, {
        headers,
        tags: { kind: 'schedule' },
    });
    check(res, {
        'schedule accepted 200/202': (r) => r.status === 200 || r.status === 202,
        'response has commit sha': (r) => {
            try {
                const payload = r.json();
                return payload && (payload.commit_sha256 || payload.status === 'ok_no_commit');
            } catch (_) {
                return false;
            }
        },
    });
}
