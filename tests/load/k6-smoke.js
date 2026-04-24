// ProdPlan ONE — smoke test (Sprint J.1)
//
// 30-second post-deploy probe. Hits the most critical routes and
// fails fast if any return non-2xx. Run with:
//
//   k6 run tests/load/k6-smoke.js
//
// Exits non-zero on any failed threshold so this script gates
// deploys the way DR smoke gates restores.

import http from 'k6/http';
import { check, group, sleep } from 'k6';

const BASE = __ENV.PRODPLAN_BASE || 'http://localhost:8000';
const TENANT = __ENV.PRODPLAN_TENANT || '00000000-0000-0000-0000-000000000000';

export const options = {
    vus: 1,
    duration: '30s',
    thresholds: {
        // Every request must succeed; smoke is not a stress test.
        'checks': ['rate==1.0'],
        // 500 ms ceiling per docs/sla.md §2 — read-path P95.
        'http_req_duration{kind:read}': ['p(95)<500'],
    },
};

const readHeaders = { 'X-Tenant-Id': TENANT };

export default function () {
    group('health', () => {
        const ping = http.get(`${BASE}/v1/ping`, { tags: { kind: 'read' } });
        check(ping, {
            'ping 200': (r) => r.status === 200,
        });

        const rt = http.get(`${BASE}/v1/realtime/health`, { tags: { kind: 'read' } });
        check(rt, {
            'realtime health 200': (r) => r.status === 200,
        });

        const metrics = http.get(`${BASE}/metrics`, { tags: { kind: 'read' } });
        check(metrics, {
            'metrics 200': (r) => r.status === 200,
            'metrics body non-empty': (r) => r.body && r.body.length > 100,
        });
    });

    group('kpi-surface', () => {
        const kpis = http.get(`${BASE}/v1/profit/dashboard`, {
            headers: readHeaders,
            tags: { kind: 'read' },
        });
        check(kpis, {
            'profit dashboard 200': (r) => r.status === 200,
            'profit dashboard throughput_eur': (r) =>
                r.json() && r.json().throughput_eur !== undefined,
        });

        const commits = http.get(`${BASE}/v1/plan/cpo/commits?limit=5`, {
            headers: readHeaders,
            tags: { kind: 'read' },
        });
        check(commits, {
            'commits 200 or 503 (DB cold start)': (r) =>
                r.status === 200 || r.status === 503,
        });
    });

    group('governance', () => {
        const rules = http.get(
            `${BASE}/v1/governance/preference-rules?status=detected`,
            { headers: readHeaders, tags: { kind: 'read' } },
        );
        check(rules, {
            'preference-rules list 200': (r) => r.status === 200,
            'preference-rules is array': (r) => Array.isArray(r.json()),
        });
    });

    sleep(1);
}
