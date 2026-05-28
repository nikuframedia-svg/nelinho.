/**
 * ProdPlan ONE — API: saúde, factory, sandbox, capabilities, diagnósticos, config, auth, pesquisa, relatórios.
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 */
import { request, filterParams } from './client';

// ═══════════════════════════════════════════════════════════════════════════════
// HEALTH & UTILITY
// ═══════════════════════════════════════════════════════════════════════════════

export const healthApi = {
  check: () => request<any>('/health'),
  ready: () => request<any>('/health/ready'),
  live: () => request<any>('/health/live'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// FACTORY DATA PRODUCT API (C10)
// ═══════════════════════════════════════════════════════════════════════════════

export const factoryApi = {
  getActiveRun: () => 
    request<any>('/v1/factory/meta/active-run'),
  
  getSemanticView: (viewId: string, params?: Record<string, any>) => {
    const queryParams = params ? `?${new URLSearchParams(filterParams(params))}` : '';
    return request<any>(`/v1/factory/semantic/${viewId}${queryParams}`);
  },
  
  getSnapshot: (params?: { run_id?: string }) => {
    const queryParams = params?.run_id ? `?run_id=${params.run_id}` : '';
    return request<any>(`/v1/factory/snapshot${queryParams}`);
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// SANDBOX API
// ═══════════════════════════════════════════════════════════════════════════════

export const sandboxApi = {
  createScenario: (data: any) => 
    request<any>('/v1/sandbox/scenarios', { 
      method: 'POST', 
      body: JSON.stringify(data) 
    }),
  
  getScenario: (scenarioId: string) => 
    request<any>(`/v1/sandbox/scenarios/${scenarioId}`),
  
  listScenarios: () => 
    request<any>('/v1/sandbox/scenarios'),
  
  applySuggestion: (scenarioId: string, suggestionId: string) => 
    request<any>(`/v1/sandbox/scenarios/${scenarioId}/apply-suggestion`, {
      method: 'POST',
      body: JSON.stringify({ suggestion_id: suggestionId }),
    }),
  
  simulate: (scenarioId: string) => 
    request<any>(`/v1/sandbox/scenarios/${scenarioId}/simulate`, { 
      method: 'POST' 
    }),
  
  getExecPack: (scenarioId: string) => 
    request<any>(`/v1/sandbox/scenarios/${scenarioId}/exec-pack`),
  
  publish: (scenarioId: string) => 
    request<any>(`/v1/sandbox/scenarios/${scenarioId}/publish`, { 
      method: 'POST' 
    }),
  
  deleteScenario: (scenarioId: string) =>
    request<void>(`/v1/sandbox/scenarios/${scenarioId}`, { method: 'DELETE' }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// CAPABILITIES API (Feature Gating)
// ═══════════════════════════════════════════════════════════════════════════════

export const capabilitiesApi = {
  // Barra final: a rota é /v1/capabilities/ — sem ela o backend devolve
  // um 307 redirect que nem sempre é seguido com os headers de tenant.
  get: () =>
    request<any>('/v1/capabilities/'),

  getModules: () => 
    request<any>('/v1/capabilities/modules'),
  
  getFeatures: () => 
    request<any>('/v1/capabilities/features'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// CATALOG API (API Discovery)
// ═══════════════════════════════════════════════════════════════════════════════

export const catalogApi = {
  get: () => 
    request<any>('/v1/catalog'),
  
  getSummary: () => 
    request<any>('/v1/catalog/summary'),
  
  getEndpoints: () => 
    request<any>('/v1/catalog/endpoints'),
  
  getViews: () => 
    request<any>('/v1/catalog/views'),
  
  getMetrics: () => 
    request<any>('/v1/catalog/metrics'),
  
  getBlockedMetrics: () => 
    request<any>('/v1/catalog/blocked-metrics'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// KPI REGISTRY API
// ═══════════════════════════════════════════════════════════════════════════════

export const kpiRegistryApi = {
  list: () => 
    request<any>('/v1/kpi/registry'),
  
  get: (kpiId: string) => 
    request<any>(`/v1/kpi/registry/${kpiId}`),
  
  explain: (kpiId: string) => 
    request<any>(`/v1/kpi/registry/${kpiId}/explain`),
  
  getBlocked: () => 
    request<any>('/v1/kpi/blocked'),
  
  calculate: (data: { kpi_id: string; scope?: any; period?: any }) => 
    request<any>('/v1/kpi/calculate', { 
      method: 'POST', 
      body: JSON.stringify(data) 
    }),
  
  getDomains: () =>
    request<any>('/v1/kpi/domains'),

  getTrustGuide: () =>
    request<any>('/v1/kpi/trust-index-guide'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// SPRINT Q.7 — Diagnostics dashboard (per-module health + infra pings)
// ═══════════════════════════════════════════════════════════════════════════════

export type ModuleHealthStatus = 'green' | 'yellow' | 'red';

export interface DiagnosticsModule {
  module: string;
  src_files: number;
  test_files: number;
  routes: number;
  todo_count: number;
  import_errors: string[];
  import_error_count: number;
  health: ModuleHealthStatus;
}

export interface DiagnosticsModulesResponse {
  modules: DiagnosticsModule[];
  summary: {
    total: number;
    green: number;
    yellow: number;
    red: number;
    total_routes: number;
    total_import_errors: number;
    total_todos: number;
  };
  module_catalogue: string[];
}

export interface InfraComponent {
  component: string;
  healthy: boolean;
  detail: string;
  latency_ms: number | null;
}

export interface InfrastructureResponse {
  items: InfraComponent[];
  summary: {
    total: number;
    healthy: number;
    unhealthy: number;
  };
}

export interface DiagnosticsFullResponse {
  modules: DiagnosticsModule[];
  modules_summary: { total: number; green: number; yellow: number; red: number };
  infrastructure: InfrastructureResponse;
  trust_index: {
    composite?: number;
    components?: Record<string, number | null>;
    effective_gates?: Record<string, boolean>;
    error?: string;
    source?: string;
  };
  commits: {
    commits_last_7_days?: number;
    latest_commit_sha?: string | null;
    latest_commit_at?: string | null;
    error?: string;
    source?: string;
  };
}

export const diagnosticsApi = {
  modules: () => request<DiagnosticsModulesResponse>('/v1/diagnostics/modules'),
  infrastructure: () => request<InfrastructureResponse>('/v1/diagnostics/infrastructure'),
  full: () => request<DiagnosticsFullResponse>('/v1/diagnostics/full'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// SPRINT Q.1 — Tenant Configuration (ConfigStore)
// ═══════════════════════════════════════════════════════════════════════════════

export type ConfigDataType =
  | 'int'
  | 'float'
  | 'bool'
  | 'string'
  | 'json'
  | 'duration'
  | 'currency';

export interface ConfigEntry {
  id: string;
  category: string;
  key: string;
  value: unknown;
  data_type: ConfigDataType;
  valid_from: string;
  valid_to: string | null;
  last_modified_by: string | null;
  last_modified_at: string;
  // Sprint X.1 — Plan v4 §4.7 provenance: 'default' | 'manual' | 'learned_rule'
  source: ConfigSource;
}

export type ConfigSource = 'default' | 'manual' | 'learned_rule';

export interface ConfigCategoryValues {
  category: string;
  values: Record<string, unknown>;
}

export interface ConfigBulkEntry {
  category: string;
  key: string;
  value: unknown;
  data_type: ConfigDataType;
}

export const configApi = {
  /** Latest active value for one key. 404 if never set. */
  get: (category: string, key: string) =>
    request<ConfigEntry>(`/v1/config/${encodeURIComponent(category)}/${encodeURIComponent(key)}`),

  /** All active values in a category as `{key: value}`. */
  listCategory: (category: string) =>
    request<ConfigCategoryValues>(`/v1/config/${encodeURIComponent(category)}`),

  /** Full audit history (oldest → newest, including soft-deleted). */
  history: (category: string, key: string) =>
    request<ConfigEntry[]>(
      `/v1/config/${encodeURIComponent(category)}/${encodeURIComponent(key)}/history`,
    ),

  /** Set or override a single key. */
  set: (
    category: string,
    key: string,
    payload: { value: unknown; data_type: ConfigDataType },
  ) =>
    request<ConfigEntry>(
      `/v1/config/${encodeURIComponent(category)}/${encodeURIComponent(key)}`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),

  /** Apply many overrides atomically (one audit row per entry). */
  bulkSet: (entries: ConfigBulkEntry[]) =>
    request<ConfigEntry[]>('/v1/config/bulk', {
      method: 'PATCH',
      body: JSON.stringify({ entries }),
    }),

  /** Revert a config row by id; creates a new audit row pointing at the reverted value. */
  rollback: (configId: string) =>
    request<ConfigEntry>(`/v1/config/rollback/${encodeURIComponent(configId)}`, {
      method: 'POST',
    }),

  /** Sprint Q.6 — list every category that has at least one seeded default. */
  listCategories: () =>
    request<{ categories: Array<{ category: string; default_keys: number }>; total: number }>(
      '/v1/config/categories',
    ),

  /** Sprint Q.6 — reset a key to its seeded default value. 404 if no seed exists. */
  resetToDefault: (category: string, key: string) =>
    request<ConfigEntry>(
      `/v1/config/${encodeURIComponent(category)}/${encodeURIComponent(key)}/reset-to-default`,
      { method: 'POST' },
    ),

  /** Snapshot the entire tenant config (read-only). */
  exportSnapshot: () => request<Record<string, unknown>>('/v1/config/snapshot/export'),

  /** Replace the tenant config with the supplied snapshot. */
  importSnapshot: (snapshot: Record<string, unknown>) =>
    request<{ written: number }>('/v1/config/snapshot/import', {
      method: 'POST',
      body: JSON.stringify(snapshot),
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// AUTH (Sprint Q.18.UI.A.1) — minimal /v1/auth/me for the Sidebar user chip.
// ═══════════════════════════════════════════════════════════════════════════════

export interface CurrentUser {
  user_id: string | null;
  tenant_id: string;
  role: string;
  name: string;
  email: string;
  umwelt: 'manager' | 'operator' | 'ceo' | string;
}

/** Resposta de POST /v1/auth/login — Q.31.G. */
export interface LoginResponse {
  access_token: string;
  refresh_token: string | null;
  token_type: string;
  role: string | null;
  user_id: string | null;
}

export const authApi = {
  /** Identidade actual (vem de JWT quando existir; dev usa headers X-*). */
  me: () => request<CurrentUser>('/v1/auth/me'),
  /** Q.31.G — login real por password. */
  login: (email: string, password: string) =>
    request<LoginResponse>('/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// Q.31.F — Pesquisa global
// ═══════════════════════════════════════════════════════════════════════════════

export interface SearchHit {
  type: 'barco' | 'operador' | 'molde' | 'erro';
  id: string;
  label: string;
  sublabel: string;
}

export interface SearchResponse {
  query: string;
  results: SearchHit[];
}

export const searchApi = {
  /** Pesquisa barcos / operadores / moldes / erros num só pedido. */
  query: (q: string, limit = 5) =>
    request<SearchResponse>(
      `/v1/search?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),
};

// ═══════════════════════════════════════════════════════════════════════════════
// Q.52.C — Relatórios (/v1/reports/*)
// ═══════════════════════════════════════════════════════════════════════════════
//
// `generate` é REAL — delega aos generators live (producao/cliente/qualidade/
// payroll/cogs/inventario). Quando uma tabela não tem dados o relatório vem
// `ready` com 0 linhas, nunca placeholders. `schedule` e `email` persistem em
// `reports.*` mas o plano Q.52 trata-os como STUB ("brevemente") porque o envio
// SMTP está desligado em dev — em dev o email vem `skipped` / `status:generated`.

export type ReportTemplateId =
  | 'producao'
  | 'cliente'
  | 'qualidade'
  | 'payroll'
  | 'cogs'
  | 'inventario';

export type ReportFormat = 'csv' | 'json';

export interface ReportGenerateRequest {
  template_id: ReportTemplateId;
  format?: ReportFormat;
  since?: string;
  until?: string;
}

export interface ReportGenerateResponse {
  template_id: ReportTemplateId;
  status: 'ready' | 'not_implemented';
  format: ReportFormat;
  filename: string;
  /** CSV text ou JSON string. Vazio se not_implemented. */
  content: string;
  row_count: number;
  generated_at: string;
  message: string | null;
}

export interface ReportSchedule {
  id: string;
  template_id: string;
  cron: string;
  enabled: boolean;
  format: ReportFormat;
  recipients: string[];
  retention_days: number;
  created_at: string;
}

/** Resposta de POST /v1/reports/email — STUB em dev (SMTP desligado). */
export interface ReportEmailResponse {
  run_id: string;
  template_id: string;
  status: 'delivered' | 'generated' | 'failed';
  recipients: string[];
  row_count: number;
  sent: boolean;
  skipped: boolean;
  generated_at: string;
  message: string | null;
}

export const reportsApi = {
  /** Gera um relatório (REAL — delega aos generators live). */
  generate: (payload: ReportGenerateRequest) =>
    request<ReportGenerateResponse>('/v1/reports/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Lista os agendamentos de relatórios do tenant. */
  listSchedules: () =>
    request<ReportSchedule[]>('/v1/reports/schedule'),

  /** STUB — agenda execução periódica; persiste mas o envio SMTP está off em dev. */
  createSchedule: (payload: {
    template_id: ReportTemplateId;
    cron: string;
    enabled?: boolean;
    format?: ReportFormat;
    recipients?: string[];
    retention_days?: number;
  }) =>
    request<ReportSchedule>('/v1/reports/schedule', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** STUB — gera e tenta entregar por email; em dev vem `skipped`.
   *  Q.67.2.B — `schedule_cron` opcional (panel admin ReportsAdminPanel
   *  permite agendar entrega periódica). */
  email: (payload: {
    template_id: ReportTemplateId;
    to: string[];
    format?: ReportFormat;
    since?: string;
    until?: string;
    schedule_cron?: string | null;
  }) =>
    request<ReportEmailResponse>('/v1/reports/email', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** Q.67.2.B — define a janela de retenção GDPR (Q.22 D-G) para o template.
   *  Actualiza `retention_days` em todos os schedules do template no tenant. */
  setRetention: (payload: {
    template_id: ReportTemplateId;
    retention_days: number;
  }) =>
    request<{ template_id: string; retention_days: number; [k: string]: unknown }>(
      '/v1/reports/retention',
      { method: 'POST', body: JSON.stringify(payload) },
    ),
};

// ═══════════════════════════════════════════════════════════════════════════════
// Q.52.C — Registry ML (/v1/ml/*)
// ═══════════════════════════════════════════════════════════════════════════════
//
// Lifecycle + inspecção de artefactos já treinados. `promote` abre uma
// DecisionRun de governança quando `via_governance` (default true) — auto-aprova
// promoções low-risk, exige aprovação humana caso contrário. `via_governance:
// false` é admin-only (bypassa o audit trail).

export interface MlArtifact {
  id: string;
  model_name: string;
  version: number;
  storage_uri: string;
  metrics: Record<string, unknown>;
  active: boolean;
  promoted_at: string | null;
  promoted_by: string | null;
  promoted_by_decision_id: string | null;
  trained_by: string;
  training_duration_sec: number | null;
  training_samples: number | null;
  created_at: string | null;
}

/** Resposta de POST .../promote — shape varia conforme governança/auto-aprovação. */
export interface MlPromoteResponse {
  status: 'promoted' | 'awaiting_approval';
  artifact: MlArtifact;
  decision_id: string | null;
  decision_status?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Q.115.B — Revenue Target (/v1/config/revenue-target)
// ═══════════════════════════════════════════════════════════════════════════════

export interface RevenueTarget {
  id: string;
  effective_from: string;
  target_eur: number;
  created_by: string;
  created_at: string;
}

export interface RevenueTargetCreate {
  effective_from: string;
  target_eur: number;
}

export const revenueTargetApi = {
  list: () => request<RevenueTarget[]>('/v1/config/revenue-target'),
  create: (payload: RevenueTargetCreate) =>
    request<RevenueTarget>('/v1/config/revenue-target', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// Q.115.B — Client Priority (/v1/config/client-priority)
// ═══════════════════════════════════════════════════════════════════════════════

export interface ClientPriority {
  id: string;
  cliente_id: string;
  prioridade: number;
  razao: string | null;
  updated_at: string;
}

export interface ClientPriorityUpdate {
  prioridade: number;
  razao?: string;
}

export const clientPriorityApi = {
  list: (params?: { page?: number; page_size?: number }) => {
    const qs = params ? `?${new URLSearchParams(filterParams(params))}` : '';
    return request<ClientPriority[]>(`/v1/config/client-priority${qs}`);
  },
  update: (clienteId: string, payload: ClientPriorityUpdate) =>
    request<ClientPriority>(`/v1/config/client-priority/${encodeURIComponent(clienteId)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),
};

// ═══════════════════════════════════════════════════════════════════════════════
// Q.115.B — User Input (/v1/user-input)
// ═══════════════════════════════════════════════════════════════════════════════

export type UserInputStatus = 'pending' | 'in_progress' | 'done' | 'rejected';

export interface UserInput {
  id: string;
  what: string;
  where_page: string;
  economic_reason: string;
  status: UserInputStatus;
  pr_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserInputCreate {
  what: string;
  where_page: string;
  economic_reason: string;
}

export const userInputApi = {
  create: (payload: UserInputCreate) =>
    request<UserInput>('/v1/user-input', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  list: (params?: { status?: UserInputStatus }) => {
    const qs = params?.status ? `?status=${params.status}` : '';
    return request<UserInput[]>(`/v1/user-input${qs}`);
  },
};

// ═══════════════════════════════════════════════════════════════════════════════

export const mlApi = {
  /** Nomes de todos os modelos no registry (array nu de strings). */
  listModels: () => request<string[]>('/v1/ml/models'),

  /** Versões de um modelo, mais recente primeiro. */
  listVersions: (modelName: string, params?: { limit?: number }) =>
    request<MlArtifact[]>(
      `/v1/ml/models/${encodeURIComponent(modelName)}/versions?${new URLSearchParams(filterParams(params))}`,
    ),

  /** Versão activa de um modelo. 404 quando nenhuma está promovida. */
  getActive: (modelName: string) =>
    request<MlArtifact>(
      `/v1/ml/models/${encodeURIComponent(modelName)}/active`,
    ),

  /** Promover uma versão a activa. Default via governança (audit trail). */
  promote: (
    modelName: string,
    artifactId: string,
    payload: { via_governance?: boolean } = {},
  ) =>
    request<MlPromoteResponse>(
      `/v1/ml/models/${encodeURIComponent(modelName)}/versions/${encodeURIComponent(artifactId)}/promote`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
};
