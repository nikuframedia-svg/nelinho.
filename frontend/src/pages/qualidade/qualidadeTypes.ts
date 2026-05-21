// Tipos das respostas REAIS da página Qualidade (Q.60.Q).

export interface QualityDashboardItem {
  key: string;
  events: number;
  share_pct: number;
}
export interface QualityDashboardResponse {
  group_by: string;
  window: { from: string; to: string };
  total_events: number;
  items: QualityDashboardItem[];
}

export interface ReworkRow {
  id: string;
  of_id: string;
  error_code: string;
  error_description: string | null;
  phase_id_causer: string | null;
  causer_employee_id: string | null;
  detected_at: string | null;
  resolved_at: string | null;
  cost_estimate_eur: number | null;
}

export interface OeeItem {
  group_value: string;
  availability: number;
  performance: number;
  quality: number;
  oee: number;
  sample_size: number;
  sample_excluded: number;
}
export interface OeeResponse {
  date_from: string;
  date_to: string;
  group_by: string;
  overall: OeeItem;
  breakdown: OeeItem[];
}

export interface SupplierLotRow {
  supplier_id?: string;
  lot_id?: string;
  events: number;
}
export interface SupplierLotResponse {
  items: SupplierLotRow[];
  count: number;
}

/** Q.54.S — molde real do ERP com o seu histórico de defeitos. */
export interface MoldQuality {
  molde_id: string;
  nome: string | null;
  tipo: string | null;
  em_manutencao: boolean;
  defect_events: number;
  defect_qty: number;
  last_defect: string | null;
}
