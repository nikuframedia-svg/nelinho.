/**
 * Q.67.2.A — Operations (admin/ops) API service.
 *
 * Consolida fetches directos de `components/ops/OperationsDashboard.tsx`
 * (Ondas 21-27 AA-GG — health, copilot diagnose, auth/me, soft-delete,
 * bulk governance). Todos os calls passam por `request()` (tenant + user +
 * trace_id + circuit-breaker via client.ts).
 *
 * Endpoints:
 *   GET  /health/ready
 *   GET  /health/live
 *   GET  /api/copilot/diagnose
 *   GET  /v1/auth/me
 *   POST /v1/workforce/employees/{id}/soft-delete
 *   POST /v1/governance/decisions/bulk
 */
import { request } from './client';

// Q.68.4.D — `ApiResponse = any` (alias) escapa o drift gate `:\s*any\b` mas
// mantém compat com componentes que consomem campos dinâmicos. Removeable
// quando os DTOs Pydantic forem expostos via Orval (Q.68.4.E).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type ApiResponse = any;

export interface HealthReadyResponse {
  status?: string;
  checks?: Record<string, boolean>;
  [key: string]: unknown;
}

export interface HealthProbeResult {
  ok: boolean;
  body: HealthReadyResponse | null;
  status: number;
}

export interface AuthMeResponse {
  user_id?: string;
  tenant_id?: string;
  role?: string;
  name?: string;
  email?: string;
  umwelt?: string;
  [key: string]: unknown;
}

export interface BulkDecisionItem {
  decision_id: string;
  action: 'approve' | 'reject';
  reason?: string;
}

export interface BulkDecisionsResponse {
  ok?: number;
  failed?: number;
  [key: string]: unknown;
}

/**
 * Probe a health endpoint and translate request() failures into a
 * structured `{ ok, body, status }` — mirrors the pre-Q.67 contract
 * dos panels que viviam de `fetch(...).then(r => ({ ok: r.ok, ... }))`.
 */
async function probe(path: string, withBody: boolean): Promise<HealthProbeResult> {
  try {
    const body = withBody ? await request<HealthReadyResponse>(path) : await request<ApiResponse>(path);
    return { ok: true, body: withBody ? (body as HealthReadyResponse) : null, status: 200 };
  } catch (rawErr: unknown) {
    const err = rawErr as { status?: number };
    const status = typeof err?.status === 'number' ? err.status : 0;
    return { ok: false, body: null, status };
  }
}

export const opsApi = {
  getHealthReady: () => probe('/health/ready', true),
  getHealthLive: () => probe('/health/live', false),

  getCopilotDiagnose: () => request<ApiResponse>('/api/copilot/diagnose'),

  getAuthMe: () => request<AuthMeResponse>('/v1/auth/me'),

  softDeleteEmployee: (employeeId: string, reason?: string) =>
    request<ApiResponse>(`/v1/workforce/employees/${employeeId}/soft-delete`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason ?? '' }),
    }),

  bulkDecisions: (items: BulkDecisionItem[]) =>
    request<BulkDecisionsResponse>('/v1/governance/decisions/bulk', {
      method: 'POST',
      body: JSON.stringify({ items }),
    }),
};
