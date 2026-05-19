// DirecaoPage — tipos das respostas (Q.60.W).


export interface KpiMetric {
  value: number | null;
  reason?: string | null;
}

export interface KpiSnapshot {
  oee: KpiMetric;
  availability: KpiMetric;
  performance: KpiMetric;
  quality_fpy: KpiMetric;
  rework_rate: KpiMetric;
  orders_total: KpiMetric;
  orders_in_progress: KpiMetric;
  orders_completed: KpiMetric;
  updated_at: string;
}

export interface ThroughputDashboard {
  date: string;
  throughput_eur: {
    today: number;
    mtd: number;
    ytd: number;
    target_min: number;
    target_max: number;
    on_target: boolean;
  };
  trend_14d: { date: string; eur: number }[];
  currency: string;
  source: string;
}

export interface OtdResponse {
  window_days: number;
  otd_pct: number;
  on_time: number;
  late: number;
  total: number;
}

export interface TransportBatch {
  id: string;
  code?: string;
  status?: string;
  transport_date?: string | null;
  destination?: string | null;
  truck_capacity_units?: number;
  assigned_orders?: number;
}

export interface LiveKpis {
  throughputToday: number | null;
  otdPct: number | null;
  fpyPct: number | null;
  reworkRate: number | null;
}

/**
 * Devolve o valor realizado (vivo) para um KPI da banda, na mesma
 * unidade da banda. `throughput` vem em €/dia → divide-se por 1000 para
 * casar com a banda (semeada em € mas mostrada em K). `rework` vive em
 * 0–1 na snapshot → ×100 para %. null quando o KPI não tem dados.
 */
