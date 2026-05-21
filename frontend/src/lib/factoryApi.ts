/**
 * Factory API Client
 *
 * Client for interacting with the Factory Data Product endpoints.
 * Includes semantic queries, capabilities, and governance endpoints.
 */

import { apiFetch, getApiBase } from './api';

// ============================================================================
// TYPES
// ============================================================================

export interface SemanticResponse<T> {
  data: T;
  data_confidence: number;
  semantic_label: string;
  warnings: string[];
  metadata: {
    query_time_ms: number;
    record_count: number;
  };
}

export interface WIPData {
  open_orders: number;
  open_phases: number;
  total_hours_pending: number;
  /** Optional: total phases in factory; some backend builds emit this
   *  alongside `open_phases` (which is open_phases ⊆ phases_total). */
  phases_total?: number;
}

export interface BacklogPhase {
  fase_id: string;
  fase_nome: string;
  backlog_hours: number;
  backlog_days: number;
  capacity_hours_day: number;
}

export interface BacklogData {
  phases: BacklogPhase[];
  total_backlog_hours: number;
  total_backlog_days: number;
}

export interface BottleneckData {
  bottlenecks: Array<{
    fase_id: string;
    fase_nome: string;
    bottleneck_score: number;
    backlog_hours: number;
    is_critical: boolean;
  }>;
}

export interface LeadTimeData {
  average_days: number;
  median_days: number;
  percentile_95_days: number;
  by_model: Array<{
    modelo: string;
    avg_days: number;
  }>;
}

export interface QualityErrorItem {
  error_type: string;
  count: number;
  percentage: number;
  /** Optional: PT-PT description from some backend builds. */
  descricao?: string;
  /** Optional: phase culpability percentage. */
  fase_culpada_pct?: number;
}

export interface QualityData {
  total_errors: number;
  by_type: QualityErrorItem[];
  by_phase: Array<{
    fase_nome: string;
    count: number;
  }>;
  /** Optional alias for `by_type` used by some Q.13+ payloads. The
   *  Dashboard treats both identically. */
  top_items?: QualityErrorItem[];
}

export interface CapabilityStatus {
  id: string;
  name: string;
  status: 'enabled' | 'degraded' | 'disabled' | 'blocked';
  reason?: string;
  trust_score?: number;
  semantic_label?: string;
  required_permissions?: string[];
  how_to_enable?: string;
  data_requirements?: string[];
}

export interface ModuleCapability {
  id: string;
  name: string;
  status: 'enabled' | 'degraded' | 'disabled' | 'blocked';
  features: CapabilityStatus[];
  data_available: boolean;
  active_ingestion_id?: string;
  trust_score_avg?: number;
}

export interface CapabilitiesResponse {
  modules: ModuleCapability[];
  has_active_data: boolean;
  active_ingestion_id?: string;
  blocked_metrics: string[];
  allowed_metrics: string[];
  evaluated_at: string;
  version: string;
}

export interface CapabilitiesSummary {
  has_active_data: boolean;
  active_ingestion_id?: string;
  total_features: number;
  enabled: number;
  degraded: number;
  disabled: number;
  blocked: number;
  health_score: number;
  evaluated_at: string;
}

// ============================================================================
// HELPERS
// ============================================================================

// Q.21.A — todo o tráfego JSON passa pelo `apiFetch` (api.ts) para partilhar
// circuit breaker, retry e headers de tenant/user. O `getTenantId()` local
// anterior lia a chave errada de localStorage (`tenantId`) e caía no zero-UUID,
// que o backend rejeita por design (Q.12 Onda 0.1).
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  return apiFetch<T>(endpoint, options);
}

// ============================================================================
// CAPABILITIES API
// ============================================================================

export const capabilitiesApi = {
  /**
   * Get full capabilities response with all modules and features.
   */
  async getCapabilities(): Promise<CapabilitiesResponse> {
    return fetchApi<CapabilitiesResponse>('/v1/capabilities/');
  },

  /**
   * Get capabilities summary (health score, counts).
   */
  async getSummary(): Promise<CapabilitiesSummary> {
    return fetchApi<CapabilitiesSummary>('/v1/capabilities/summary');
  },

  /**
   * Get list of modules with their status.
   */
  async getModules(): Promise<Array<{
    id: string;
    name: string;
    status: string;
    data_available: boolean;
    trust_score_avg?: number;
  }>> {
    return fetchApi('/v1/capabilities/modules');
  },

  /**
   * Get features, optionally filtered by module or status.
   */
  async getFeatures(moduleId?: string, status?: string): Promise<CapabilityStatus[]> {
    const params = new URLSearchParams();
    if (moduleId) params.append('module_id', moduleId);
    if (status) params.append('status_filter', status);
    const query = params.toString() ? `?${params.toString()}` : '';
    return fetchApi(`/v1/capabilities/features${query}`);
  },

  /**
   * Get all blocked capabilities with reasons.
   */
  async getBlocked(): Promise<Array<{
    module_id: string;
    feature_id: string;
    feature_name: string;
    reason: string;
    data_requirements: string[];
    how_to_enable: string;
  }>> {
    return fetchApi('/v1/capabilities/blocked');
  },

  /**
   * Get all degraded capabilities with improvement suggestions.
   */
  async getDegraded(): Promise<Array<{
    module_id: string;
    feature_id: string;
    feature_name: string;
    trust_score: number;
    reason: string;
    how_to_enable: string;
  }>> {
    return fetchApi('/v1/capabilities/degraded');
  },
};

// ============================================================================
// FACTORY SEMANTIC QUERIES API
// ============================================================================

export const factoryApi = {
  /**
   * Get Work in Progress (WIP) data.
   */
  async getWIP(): Promise<SemanticResponse<WIPData>> {
    return fetchApi<SemanticResponse<WIPData>>('/v1/factory/semantic/queries/wip');
  },

  /**
   * Get backlog by phase.
   */
  async getBacklog(): Promise<SemanticResponse<BacklogData>> {
    return fetchApi<SemanticResponse<BacklogData>>('/v1/factory/semantic/queries/backlog');
  },

  /**
   * Get bottleneck analysis.
   */
  async getBottlenecks(): Promise<SemanticResponse<BottleneckData>> {
    return fetchApi<SemanticResponse<BottleneckData>>('/v1/factory/semantic/queries/bottlenecks');
  },

  /**
   * Get lead time analysis.
   */
  async getLeadTime(): Promise<SemanticResponse<LeadTimeData>> {
    return fetchApi<SemanticResponse<LeadTimeData>>('/v1/factory/semantic/queries/lead-time');
  },

  /**
   * Get quality analysis.
   */
  async getQuality(): Promise<SemanticResponse<QualityData>> {
    return fetchApi<SemanticResponse<QualityData>>('/v1/factory/semantic/queries/quality');
  },

  /**
   * Get mold conflicts analysis.
   */
  async getMoldConflicts(): Promise<SemanticResponse<any>> {
    return fetchApi<SemanticResponse<any>>('/v1/factory/semantic/queries/mold-conflicts');
  },

  /**
   * Get skills risk analysis.
   */
  async getSkillsRisk(): Promise<SemanticResponse<any>> {
    return fetchApi<SemanticResponse<any>>('/v1/factory/semantic/queries/skills-risk');
  },

  /**
   * Get data overview (curated data summary).
   */
  async getOverview(): Promise<SemanticResponse<any>> {
    return fetchApi<SemanticResponse<any>>('/v1/factory/semantic/queries/overview');
  },
};

// ============================================================================
// INGESTION API
// ============================================================================

export interface IngestionResult {
  success: boolean;
  ingestion_id: string | null;
  status: string;
  is_duplicate: boolean;
  duplicate_of?: string;
  total_rows_raw: number;
  total_rows_curated: number;
  quality_gate_status: string;
  has_schema_drift: boolean;
  errors: string[];
  warnings: string[];
  duration_seconds?: number;
}

export interface IngestionRun {
  id: string;
  status: string;
  source_filename: string;
  source_type: string;
  file_hash: string;
  total_rows: number;
  created_at: string;
  created_by: string;
  is_active: boolean;
}

export interface ActiveRun {
  active_ingestion_id: string | null;
  activated_at_utc: string | null;
  activated_by: string | null;
  has_active: boolean;
}

export interface RollbackRequest {
  to_ingestion_id: string;
  rolled_back_by: string;
  reason: string;
}

export const ingestionApi = {
  /**
   * Upload and ingest an Excel file.
   */
  async ingestFile(
    file: File,
    autoActivate: boolean = true,
    user: string = 'frontend_user'
  ): Promise<IngestionResult> {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams({
      auto_activate: autoActivate.toString(),
      user,
    });

    // Upload multipart mantém `fetch` cru — o `apiFetch` força Content-Type
    // JSON, o que partiria o boundary do FormData. Headers espelham o api.ts:
    // chaves snake_case de localStorage + dev tenant não-zero.
    const tenantId =
      localStorage.getItem('tenant_id') || '00000000-0000-0000-0000-000000000001';
    const userId =
      localStorage.getItem('user_id') || '00000000-0000-0000-0000-000000000001';
    const response = await fetch(
      `${getApiBase()}/v1/factory/ingest?${params.toString()}`,
      {
        method: 'POST',
        body: formData,
        headers: {
          'X-Tenant-Id': tenantId,
          'X-User-Id': userId,
          'X-User-Role': localStorage.getItem('user_role') || 'admin',
        },
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
      throw new Error(error.detail || `Upload error: ${response.status}`);
    }

    return response.json();
  },

  /**
   * Get list of all ingestion runs.
   */
  async getIngestions(): Promise<{ ingestions: IngestionRun[]; total: number }> {
    return fetchApi('/v1/factory/meta/ingestions');
  },

  /**
   * Get the currently active ingestion run.
   */
  async getActiveRun(): Promise<ActiveRun> {
    return fetchApi('/v1/factory/meta/active-run');
  },

  /**
   * Activate a specific ingestion run.
   */
  async activateIngestion(
    ingestionId: string,
    user: string = 'frontend_user'
  ): Promise<{ success: boolean; message: string }> {
    return fetchApi(`/v1/factory/activate/${ingestionId}?user=${user}`, {
      method: 'POST',
    });
  },

  /**
   * Rollback to a previous ingestion.
   */
  async rollback(request: RollbackRequest): Promise<{ success: boolean; message: string }> {
    return fetchApi('/v1/factory/rollback', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  },

  /**
   * Get quality report for an ingestion.
   */
  async getQualityReport(ingestionId: string): Promise<any> {
    return fetchApi(`/v1/factory/meta/quality-report/${ingestionId}`);
  },

  /**
   * Get schema drift report for an ingestion.
   */
  async getSchemaDrift(ingestionId: string): Promise<any> {
    return fetchApi(`/v1/factory/meta/schema-drift/${ingestionId}`);
  },

  /**
   * Get trust heatmap.
   */
  async getTrustHeatmap(): Promise<any> {
    return fetchApi('/v1/factory/quality/trust-heatmap');
  },

  /**
   * Get blocked metrics.
   */
  async getBlockedMetrics(): Promise<any> {
    return fetchApi('/v1/factory/semantic/blocked-metrics');
  },
};

// ============================================================================
// GOVERNANCE API
// ============================================================================

export interface DecisionRun {
  id: string;
  action_type: string;
  status: string;
  created_at: string;
  created_by: string;
  approved_by?: string;
  executed_at?: string;
  audit_hash: string;
  input_snapshot_hash: string;
  policy_version?: string;
}

export interface DecisionPolicy {
  id: string;
  action_type: string;
  autonomy_level: number;
  requires_approval: boolean;
  approver_roles: string[];
  is_active: boolean;
}

export const governanceApi = {
  /**
   * Get all decision runs (audit trail).
   */
  async getDecisions(status?: string): Promise<DecisionRun[]> {
    const query = status ? `?status=${status}` : '';
    return fetchApi<DecisionRun[]>(`/v1/governance/decisions${query}`);
  },

  /**
   * Get a specific decision run.
   */
  async getDecision(id: string): Promise<DecisionRun> {
    return fetchApi<DecisionRun>(`/v1/governance/decisions/${id}`);
  },

  /**
   * Propose a new decision.
   */
  async proposeDecision(data: {
    action_type: string;
    input_data: Record<string, any>;
    created_by: string;
    reason: string;
  }): Promise<DecisionRun> {
    return fetchApi<DecisionRun>('/v1/governance/decisions/propose', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /**
   * Approve a decision.
   */
  async approveDecision(id: string, approvedBy: string): Promise<DecisionRun> {
    return fetchApi<DecisionRun>(`/v1/governance/decisions/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ approved_by: approvedBy }),
    });
  },

  /**
   * Execute an approved decision.
   */
  async executeDecision(id: string): Promise<DecisionRun> {
    return fetchApi<DecisionRun>(`/v1/governance/decisions/${id}/execute`, {
      method: 'POST',
    });
  },

  /**
   * Rollback a decision.
   */
  async rollbackDecision(id: string, reason: string): Promise<DecisionRun> {
    return fetchApi<DecisionRun>(`/v1/governance/decisions/${id}/rollback`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  },

  /**
   * Get all policies.
   */
  async getPolicies(): Promise<DecisionPolicy[]> {
    return fetchApi<DecisionPolicy[]>('/v1/governance/policies');
  },

  /**
   * Activate kill switch.
   */
  async activateKillSwitch(actionType: string, reason: string): Promise<{
    message: string;
    affected_policies: number;
  }> {
    return fetchApi('/v1/governance/kill-switch', {
      method: 'POST',
      body: JSON.stringify({ action_type: actionType, reason }),
    });
  },
};

// ============================================================================
// SANDBOX API
// ============================================================================

export interface SandboxScenario {
  id: string;
  title: string;
  description?: string;
  status: string;
  suggestion_id?: string;
  created_at: string;
  updated_at: string;
  before_state: Record<string, any>;
  after_state?: Record<string, any>;
  impact?: Record<string, any>;
}

export const sandboxApi = {
  /**
   * List all sandbox scenarios.
   */
  async getScenarios(status?: string): Promise<SandboxScenario[]> {
    const query = status ? `?status=${status}` : '';
    return fetchApi<SandboxScenario[]>(`/v1/sandbox/scenarios${query}`);
  },

  /**
   * Create a new sandbox scenario.
   */
  async createScenario(data: {
    title: string;
    description?: string;
    suggestion_id?: string;
  }): Promise<SandboxScenario> {
    return fetchApi<SandboxScenario>('/v1/sandbox/scenarios', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /**
   * Get a specific scenario.
   */
  async getScenario(id: string): Promise<SandboxScenario> {
    return fetchApi<SandboxScenario>(`/v1/sandbox/scenarios/${id}`);
  },

  /**
   * Simulate a scenario.
   */
  async simulate(id: string, suggestionType = 'default'): Promise<SandboxScenario> {
    return fetchApi<SandboxScenario>(
      `/v1/sandbox/scenarios/${id}/simulate?suggestion_type=${suggestionType}`,
      { method: 'POST' }
    );
  },

  /**
   * Publish a scenario.
   */
  async publish(id: string): Promise<{ scenario_id: string; status: string; decision_id: string }> {
    return fetchApi(`/v1/sandbox/scenarios/${id}/publish`, { method: 'POST' });
  },

  /**
   * Get blocked metrics info.
   */
  async getBlockedMetrics(): Promise<{
    blocked_metrics: Array<{
      id: string;
      reason: string;
      required_data: string[];
    }>;
    available_metrics: string[];
    note: string;
  }> {
    return fetchApi('/v1/sandbox/blocked-metrics');
  },
};

// ============================================================================
// RUNBOOKS API
// ============================================================================

export interface Runbook {
  name: string;
  title: string;
  description: string;
  steps_count: number;
  tags: string[];
}

export interface RunbookExecution {
  runbook_name: string;
  mode: string;
  status: string;
  started_at: string;
  completed_at?: string;
  results: unknown[];
}

export const runbooksApi = {
  /**
   * List all runbooks.
   */
  async getRunbooks(): Promise<Runbook[]> {
    return fetchApi<Runbook[]>('/v1/runbooks');
  },

  /**
   * Execute a runbook.
   */
  async execute(
    name: string,
    mode: 'DRY_RUN' | 'PREVIEW' | 'EXECUTE' = 'DRY_RUN',
    params?: Record<string, any>
  ): Promise<RunbookExecution> {
    return fetchApi<RunbookExecution>(`/v1/runbooks/${name}/execute`, {
      method: 'POST',
      body: JSON.stringify({ mode, params }),
    });
  },

  /**
   * Get execution history.
   */
  async getHistory(): Promise<RunbookExecution[]> {
    return fetchApi<RunbookExecution[]>('/v1/runbooks/history');
  },
};

// ============================================================================
// EXPLAIN API
// ============================================================================

export interface MetricDefinition {
  id: string;
  name: string;
  description: string;
  domain: string;
  unit: string;
  formula: string;
  data_sources: string[];
  trust_index: number;
  is_blocked: boolean;
  blocked_reason?: string;
  required_data?: string[];
  semantic_label?: string;
}

export interface ExplainedValue {
  value: unknown;
  unit: string;
  display: string;
  status: string;
  explanation: {
    definition: string;
    formula: string;
    inputs: Array<{
      name: string;
      value: unknown;
      source: string;
      coverage_pct: number;
    }>;
    filters: Record<string, any>;
    data_version: string;
    lineage: {
      query_id: string;
      service_version: string;
    };
  };
  trust: {
    index: number;
    coverage: number;
    warnings: string[];
    blockers: string[];
  };
  suggestions: string[];
}

export const explainApi = {
  /**
   * Get full metric catalog.
   */
  async getCatalog(): Promise<MetricDefinition[]> {
    return fetchApi<MetricDefinition[]>('/v1/explain/catalog');
  },

  /**
   * Get a specific metric definition.
   */
  async getMetric(metricId: string): Promise<MetricDefinition> {
    return fetchApi<MetricDefinition>(`/v1/explain/metrics/${metricId}`);
  },

  /**
   * Get explanation for a metric value.
   */
  async explainMetric(metricId: string): Promise<ExplainedValue> {
    return fetchApi<ExplainedValue>(`/v1/explain/metrics/${metricId}/explain`);
  },

  /**
   * Get blocked metrics.
   */
  async getBlockedMetrics(): Promise<MetricDefinition[]> {
    return fetchApi<MetricDefinition[]>('/v1/explain/blocked');
  },

  /**
   * Search metrics.
   */
  async searchMetrics(query: string): Promise<MetricDefinition[]> {
    return fetchApi<MetricDefinition[]>(`/v1/explain/search?q=${encodeURIComponent(query)}`);
  },
};

// ============================================================================
// DEFAULT EXPORT
// ============================================================================

export default {
  capabilities: capabilitiesApi,
  factory: factoryApi,
  governance: governanceApi,
  sandbox: sandboxApi,
  runbooks: runbooksApi,
  explain: explainApi,
  ingestion: ingestionApi,
};


