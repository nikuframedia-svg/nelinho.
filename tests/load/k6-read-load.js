// ProdPlan ONE — read-path load test (Sprint J.1)
//
// 5-minute ramp 1 → 50 VUs, 50 VUs for 2 min, 50 → 0 ramp-down.
// Measures the read-path P95 against the SLO (500 ms).
//
// Hits the endpoints a live Gestor dashboard hits when the tab is
// open: KPIs, commits list, realtime health, preference rules.

import http from 'k6/http';
import { check, group } from 'k6';
import { randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

const BASE = __ENV.PRODPLAN_BASE || 'http://localhost:8000';
const TENANT = __ENV.PRODPLAN_TENANT || '00000000-0000-0000-0000-000000000000';

export const options = {
    stages: [
        { duration: '1m', target: 20 },
        { duration: '1m', target: 50 },
        { duration: '2m', target: 50 },
        { duration: '1m', target: 0 },
    ],
    thresholds: {
        'http_req_failed': ['rate<0.01'],              // < 1% failures
        'http_req_duration{kind:read}': ['p(95)<500'], // SLO
        'checks': ['rate>0.99'],
    },
};

const headers = { 'X-Tenant-Id': TENANT };

export default function () {
    group('dashboard-reads', () => {
        const endpoints = [
            '/v1/profit/dashboard',
            '/v1/profit/kpis',
            '/v1/plan/cpo/commits?limit=10',
            '/v1/plan/cpo/timeline',
            '/v1/governance/preference-rules?status=detected',
            '/v1/realtime/health',
        ];
        const url = endpoints[randomIntBetween(0, endpoints.length - 1)];
        const res = http.get(`${BASE}${url}`, {
            headers,
            tags: { kind: 'read', endpoint: url },
        });
        check(res, {
            'status 200/503': (r) => r.status === 200 || r.status === 503,
        });
    });
}
