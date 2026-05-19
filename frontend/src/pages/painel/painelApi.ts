/**
 * painelApi — wrappers tipados para os endpoints do Painel que ainda
 * não vivem em `lib/api.ts` (factory-map, copilot/alerts, activity).
 *
 * Q.52.D · Onda 1 · T1. Usa o `apiFetch` exportado de `lib/api.ts`
 * (trata headers de tenant, retry e circuit-breaker) — NÃO faz `fetch`
 * cru. Os tipos derivam dos schemas Pydantic do backend
 * (`factory_map.py`, `copilot/alerts/api.py`, `realtime/activity_api.py`).
 *
 * Quando estes endpoints ganharem wrapper canónico em `lib/api.ts`
 * (Onda 2 / Q.53), este ficheiro reexporta-os e é apagado.
 */

import { apiFetch } from '../../lib/api';

// ─── Factory-map snapshot ──────────────────────────────────────────────────

export interface FactoryBottleneck {
  /** Identificador da operação/fase. */
  operation_id?: string | null;
  phase?: string | null;
  /** Nome legível da fase. */
  name?: string | null;
  /** Carga agendada vs capacidade. */
  load?: number | null;
  capacity?: number | null;
  /** Score 0-100 de gargalo (pode vir do serviço semântico). */
  score?: number | null;
  open_phases?: number | null;
  [k: string]: unknown;
}

export interface FactorySnapshotKpis {
  wip: number;
  orders_total: number;
  completed_today: number;
  defect_rate: number | null;
  throughput_eur_day:
    | {
        today?: number;
        target_min?: number;
        target_max?: number;
        on_target?: boolean;
        status?: string;
      }
    | 'unavailable'
    | string;
}

export interface FactorySnapshot {
  timestamp: string;
  availability: Record<string, boolean>;
  trust: Record<string, unknown> | null;
  boats: {
    total: number;
    in_progress: number;
    completed: number;
    [k: string]: number;
  };
  phases: {
    bottlenecks: FactoryBottleneck[];
    skills_risk: unknown[];
    wip: number | null;
  };
  molds: { total: number; [k: string]: number };
  line_load_preview: Array<{
    operation_id: string | null;
    date: string | null;
    load_hours: number;
  }>;
  kpis: FactorySnapshotKpis;
}

export interface LineLoadResponse {
  horizon_days: number;
  has_data: boolean;
  points: Array<{
    operation_id: string | null;
    date: string | null;
    load_hours: number;
  }>;
}

// ─── Copilot alerts ────────────────────────────────────────────────────────

export type AlertSeverity = 'INFO' | 'WARN' | 'CRITICAL' | string;

export interface CopilotAlert {
  id: string;
  severity: AlertSeverity;
  code: string;
  title: string;
  message_pt: string;
  context: Record<string, unknown>;
  entity_refs: string[];
  status: string;
  created_at: string | null;
  acknowledged_at: string | null;
  acknowledged_by: string | null;
  resolved_at: string | null;
}

// ─── Activity feed ─────────────────────────────────────────────────────────

export interface ActivityItem {
  id: string;
  /** Tipo de evento (ex: SCHEDULE_CREATED). */
  event_type?: string;
  kind?: string;
  title?: string;
  message?: string;
  summary?: string;
  created_at?: string | null;
  timestamp?: string | null;
  [k: string]: unknown;
}

export interface ActivityResponse {
  items: ActivityItem[];
}

// ─── API ───────────────────────────────────────────────────────────────────

export const painelApi = {
  /** Snapshot global da fábrica (REAL, Redis-cached). */
  snapshot: () => apiFetch<FactorySnapshot>('/v1/factory-map/snapshot'),

  /** Carga da linha por (operação, dia) — gargalo (REAL). */
  lineLoad: (horizonDays = 14) =>
    apiFetch<LineLoadResponse>(
      `/v1/factory-map/line-load?horizon_days=${horizonDays}`,
    ),

  /** Alertas activos do copiloto (REAL). */
  alerts: (params?: { status?: string; severity?: string; limit?: number }) => {
    const qs = new URLSearchParams();
    qs.set('status', params?.status ?? 'active');
    if (params?.severity) qs.set('severity', params.severity);
    if (params?.limit !== undefined) qs.set('limit', String(params.limit));
    return apiFetch<CopilotAlert[]>(`/v1/copilot/alerts?${qs.toString()}`);
  },

  /** Confirmar um alerta (active → acknowledged). */
  acknowledgeAlert: (alertId: string) =>
    apiFetch<CopilotAlert>(`/v1/copilot/alerts/${alertId}/acknowledge`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  /** Resolver um alerta (→ resolved). */
  resolveAlert: (alertId: string) =>
    apiFetch<CopilotAlert>(`/v1/copilot/alerts/${alertId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  /** Feed de actividade recente (REAL — outbox poll). */
  activity: (limit = 25) =>
    apiFetch<ActivityResponse>(`/v1/activity/recent?limit=${limit}`),
};
