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
  /** Identificador da operação/fase (serviço semântico). */
  operation_id?: string | null;
  phase?: string | null;
  /** Identificador da fase (fallback DB — Q.54.E). */
  fase_id?: string | null;
  /** Nome legível da fase (serviço semântico ou fallback DB). */
  name?: string | null;
  fase_nome?: string | null;
  /** Carga agendada vs capacidade (serviço semântico). */
  load?: number | null;
  capacity?: number | null;
  /** Backlog vs capacidade em horas (fallback DB — Q.54.E). */
  backlog_horas?: number | null;
  capacidade_horas?: number | null;
  /** Score de gargalo (dias de backlog no fallback DB). */
  score?: number | null;
  open_phases?: number | null;
  is_critical?: boolean | null;
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
  /**
   * Q.158 — "barcos em produção" pela regra EXATA da NELO (view
   * factory_raw.v_of_em_producao). `em_producao` = NOT is_fila (≈830, o que a
   * fábrica mostra); `total` = tudo que o CPO planeia (≈1209). `null` quando a
   * view falta (dev sem mirror) → o card cai em `boats.in_progress`.
   */
  boats_em_producao: {
    total: number;
    em_producao: number;
    fila: number;
    reparacao: number;
    nova_producao: number;
  } | null;
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

// ─── OTD risk — risco de atraso de encomendas (Q.54.F) ─────────────────────

export type OtdRiskBand = 'alto' | 'medio' | 'baixo' | string;

export interface OtdRiskOrder {
  of_id: string;
  product_name: string | null;
  product_type: string | null;
  current_phase_id: string | null;
  current_phase_name: string | null;
  transport_date: string | null;
  late_probability: number;
  risk_band: OtdRiskBand;
  features?: Record<string, unknown>;
}

export interface OtdRiskResponse {
  /** false quando ainda não há modelo treinado — degrada com `reason`. */
  model_available: boolean;
  reason?: string | null;
  total_orders?: number;
  high_risk_count?: number;
  orders: OtdRiskOrder[];
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

  /** Risco de atraso de entrega por encomenda (REAL — Q.54.F). */
  otdRisk: (topN = 50) =>
    apiFetch<OtdRiskResponse>(`/v1/plan/orders/otd-risk?top_n=${topN}`),
};
