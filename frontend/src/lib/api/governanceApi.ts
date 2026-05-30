/**
 * ProdPlan ONE — API: decisões, improve, learning, política YAML.
 *
 * Infra partilhada (request/retry/circuit-breaker) em ./client.ts.
 * Re-exportado por ./index.ts — importar sempre de 'lib/api'.
 */
import { request, filterParams } from './client';

// ═══════════════════════════════════════════════════════════════════════════════
// DECISIONS MODULE - Decision Intelligence Platform
// ═══════════════════════════════════════════════════════════════════════════════

export interface DecisionRun {
  id: string;
  title: string;
  action_type: string;
  target: string;
  status: 'PROPOSED' | 'APPROVED' | 'EXECUTED' | 'ROLLED_BACK' | 'REJECTED';
  sandbox_result?: Record<string, any>;
  before_state: Record<string, any>;
  after_state?: Record<string, any>;
  /** Sprint Q.13.C — payload that the decision will execute. Editable
   *  via WG05 modify-payload flow. */
  action_data?: Record<string, any>;
  proposed_by: string;
  proposed_at: string;
  executed_at?: string;
  rolled_back_at?: string;
  approvals: Array<{
    approver_id: string;
    status: 'PENDING' | 'APPROVED' | 'REJECTED';
    comment?: string;
    approved_at?: string;
  }>;
}

export interface DecisionListResponse {
  total: number;
  page: number;
  page_size: number;
  // Q.119.5 — o backend (DecisionListResponse Pydantic + orval gerado) devolve
  // `decisions`, NÃO `items`. O tipo à mão dizia `items` → as páginas liam
  // undefined e mostravam sempre "Sem decisões pendentes" apesar de haver
  // decisões PROPOSED. Alinhado ao contrato real.
  decisions: DecisionRun[];
}

export interface DecisionProposalRequest {
  title: string;
  action_type: string;
  target: string;
  sandbox_result?: Record<string, any>;
  before_state: Record<string, any>;
  after_state?: Record<string, any>;
  required_approver_roles?: string[];
  required_approver_ids?: string[];
}

export interface ApprovalRequest {
  status: 'APPROVED' | 'REJECTED';
  comment?: string;
}

export const decisionsApi = {
  list: (params?: { status?: string; page?: number; page_size?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status_filter', params.status);
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString());
    return request<DecisionListResponse>(`/v1/decisions?${searchParams.toString()}`);
  },
  
  get: (id: string) =>
    request<DecisionRun>(`/v1/decisions/${id}`),
  
  propose: (data: DecisionProposalRequest) =>
    request<DecisionRun>('/v1/decisions/propose', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  approve: (id: string, data: ApprovalRequest) =>
    request<DecisionRun>(`/v1/decisions/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  
  execute: (id: string) =>
    request<DecisionRun>(`/v1/decisions/${id}/execute`, {
      method: 'POST',
    }),
  
  rollback: (id: string) =>
    request<DecisionRun>(`/v1/decisions/${id}/rollback`, {
      method: 'POST',
    }),
  
  getAuditTrail: (id: string) =>
    request<{
      decision: DecisionRun;
      approvals: Array<{
        approver_id: string;
        status: string;
        comment?: string;
        approved_at?: string;
      }>;
      state_changes: {
        before_state?: Record<string, any>;
        after_state?: Record<string, any>;
      } | null;
    }>(`/v1/decisions/${id}/audit`),

  /**
   * Sprint Q.9 Onda 3.4 — bulk approve / reject in one round trip.
   * Per-item: SoD violation on one decision does NOT abort the rest;
   * the response carries `{ok, failed, results}`. Plan v4 §8 WG04.
   */
  bulkAct: (
    items: Array<{
      decision_id: string;
      action: 'approve' | 'reject' | 'request_changes';
      reason?: string;
    }>,
  ) =>
    request<{
      ok: number;
      failed: number;
      results: Array<{
        decision_id: string;
        status: 'ok' | 'error';
        error?: string;
      }>;
    }>(`/v1/governance/decisions/bulk`, {
      method: 'POST',
      body: JSON.stringify({ items }),
    }),

  /**
   * Sprint Q.13.C C.3.2 — modify the action_data payload BEFORE
   * approving. Plan v4 §8 WG05: "modificar antes de aprovar". Reason
   * is mandatory (≥10 chars) so the audit trail explains the edit.
   */
  modifyPayload: (
    decisionId: string,
    body: { patch: Record<string, unknown>; reason: string },
  ) =>
    request<DecisionRun>(
      `/v1/governance/decisions/${encodeURIComponent(decisionId)}/payload`,
      { method: 'PATCH', body: JSON.stringify(body) },
    ),
};

export const apiInfo = () => request<any>('/');

// ═══════════════════════════════════════════════════════════════════════════════
// IMPROVE (SUGGESTIONS) API
// ═══════════════════════════════════════════════════════════════════════════════

export const improveApi = {
  listSuggestions: (params?: { status?: string; domain?: string }) => {
    const queryParams = new URLSearchParams(filterParams(params));
    return request<any>(`/v1/improve/suggestions?${queryParams}`);
  },
  
  getSuggestion: (suggestionId: string) => 
    request<any>(`/v1/improve/suggestions/${suggestionId}`),
  
  generateSuggestions: (data: { scope?: string; limit?: number }) => 
    request<any>('/v1/improve/suggestions/generate', { 
      method: 'POST', 
      body: JSON.stringify(data) 
    }),
  
  approveSuggestion: (suggestionId: string) => 
    request<any>(`/v1/improve/suggestions/${suggestionId}/approve`, { 
      method: 'POST' 
    }),
  
  rejectSuggestion: (suggestionId: string, reason?: string) => 
    request<any>(`/v1/improve/suggestions/${suggestionId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  
  getActionsCatalog: () => 
    request<any>('/v1/improve/actions'),
};

// ═══════════════════════════════════════════════════════════════════════════════
// SPRINT R.1 — Learning visibility (Aprendizagem panel)
// ═══════════════════════════════════════════════════════════════════════════════

export interface LearningPairStats {
  total_commits_with_rejection: number;
  total_pairs: number;
  eligible_for_dpo: number;
  by_category: Record<string, number>;
  by_weekday: Record<string, number>;
  last_30d: { commits: number; pairs: number; eligible: number };
  last_90d: { commits: number; pairs: number; eligible: number };
  abl_pairs_today: number;
  min_reason_len: number;
}

export interface LearningRuleStats {
  total: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  last_detector_run_at: string | null;
  rules_re_emitted_count: number;
}

export interface LearningWeightStats {
  status: string;
  current_weights: Record<string, number>;
  default_weights: Record<string, number>;
  multipliers: Record<string, number>;
  pairs_used: number;
  commits_scanned: number;
  trained_at: string | null;
  blend_learned_pct: number;
  min_pairs_threshold: number;
  reason: string | null;
}

// Sprint R.4 — weight history (Camada 2 audit modal)
export interface LearningWeightExplanation {
  kpi: string;
  label: string;
  delta_pct: number;
  direction: 'up' | 'down' | 'stable' | string;
  dominant_category: string | null;
  pairs_used: number;
  human_text: string;
}

export interface LearningWeightHistoryEntry {
  trained_at: string | null;
  valid_from: string | null;
  status: string | null;
  weights: Record<string, number>;
  multipliers: Record<string, number>;
  pairs_used: number;
  explanations: LearningWeightExplanation[];
  warnings: Array<Record<string, any>>;
}

export interface LearningWeightHistoryResponse {
  entries: LearningWeightHistoryEntry[];
}

export const learningApi = {
  pairs: (params?: { window_days?: number; min_reason_len?: number }) => {
    const qs = new URLSearchParams();
    if (params?.window_days !== undefined) qs.set('window_days', String(params.window_days));
    if (params?.min_reason_len !== undefined) qs.set('min_reason_len', String(params.min_reason_len));
    const suffix = qs.toString() ? `?${qs.toString()}` : '';
    return request<LearningPairStats>(`/v1/governance/learning/pairs${suffix}`);
  },
  rules: () => request<LearningRuleStats>('/v1/governance/learning/rules'),
  weights: () => request<LearningWeightStats>('/v1/governance/learning/weights'),
  weightHistory: (limit: number = 12) =>
    request<LearningWeightHistoryResponse>(
      `/v1/governance/learning/weights/history?limit=${limit}`,
    ),
  // Sprint R.5.3 — adapter management
  adapter: () =>
    request<LearningAdapterState>('/v1/governance/learning/adapter'),
  promoteAdapter: (
    version: string,
    payload: {
      reason: string;
      decided_by?: string;
      intent_match_rate?: number;
      safety_violations_count?: number;
    },
  ) =>
    request<LearningAdapterState>(
      `/v1/governance/learning/adapter/promote/${encodeURIComponent(version)}`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  rollbackAdapter: (payload: { reason: string; decided_by?: string }) =>
    request<LearningAdapterState>(
      '/v1/governance/learning/adapter/rollback',
      { method: 'POST', body: JSON.stringify(payload) },
    ),
};

export interface LearningAdapterState {
  active_version: string | null;
  promoted_at: string | null;
  promoted_by: string | null;
  reason: string | null;
  intent_match_rate: number | null;
  safety_violations_count: number | null;
  has_previous: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Q.17.C — YAML POLICY (NL → tenant_rules + lifecycle)
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Shape of a tenant rule as returned by the API.
 * Mirrors `RuleProposalService.serialize_rule` (src/governance/yaml_policy/service.py).
 */
export interface YamlPolicyRule {
  id: string;
  rule_id: string;
  description: string;
  status: 'proposed' | 'approved' | 'active' | 'suspended' | 'rolled_back' | 'rejected';
  event_type: string;
  payload: {
    id: string;
    description: string;
    when: { event: string; conditions: Array<{ field: string; op: string; value: unknown }> };
    then: Array<{ action: string; params: Record<string, unknown> }>;
    constraints?: { axioms_required?: string[] };
    safety?: { max_fires_per_day?: number; expires?: string };
    [key: string]: unknown;
  };
  proposed_by_user_id: string | null;
  approved_by_user_id: string | null;
  proposed_at: string | null;
  approved_at: string | null;
  activated_at: string | null;
  suspended_at: string | null;
  fire_count: number;
  last_fired_at: string | null;
  nl_source: string | null;
}

export interface YamlPolicyRevision {
  id: string;
  action: 'proposed' | 'approved' | 'rejected' | 'modified' | 'suspended' | 'rolled_back' | 'reactivated';
  actor_user_id: string | null;
  reason: string | null;
  created_at: string | null;
}

export const yamlPolicyApi = {
  /** NL → LLM → validated rule, persisted as status=proposed. */
  propose: (nlText: string) =>
    request<{ rule: YamlPolicyRule }>(
      '/v1/governance/yaml-policy/rules/propose',
      { method: 'POST', body: JSON.stringify({ nl_text: nlText }) },
    ),

  list: (params?: { status?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.status) qs.set('status_filter', params.status);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    const tail = qs.toString();
    return request<{ rules: YamlPolicyRule[]; total: number }>(
      `/v1/governance/yaml-policy/rules${tail ? `?${tail}` : ''}`,
    );
  },

  get: (ruleId: string) =>
    request<{ rule: YamlPolicyRule; revisions: YamlPolicyRevision[] }>(
      `/v1/governance/yaml-policy/rules/${encodeURIComponent(ruleId)}`,
    ),

  approve: (ruleId: string, reason?: string) =>
    request<{ rule: YamlPolicyRule }>(
      `/v1/governance/yaml-policy/rules/${encodeURIComponent(ruleId)}/approve`,
      { method: 'POST', body: JSON.stringify({ reason: reason ?? null }) },
    ),

  reject: (ruleId: string, reason: string) =>
    request<{ rule: YamlPolicyRule }>(
      `/v1/governance/yaml-policy/rules/${encodeURIComponent(ruleId)}/reject`,
      { method: 'POST', body: JSON.stringify({ reason }) },
    ),

  suspend: (ruleId: string, reason?: string) =>
    request<{ rule: YamlPolicyRule }>(
      `/v1/governance/yaml-policy/rules/${encodeURIComponent(ruleId)}/suspend`,
      { method: 'POST', body: JSON.stringify({ reason: reason ?? null }) },
    ),

  rollback: (ruleId: string, reason: string) =>
    request<{ rule: YamlPolicyRule }>(
      `/v1/governance/yaml-policy/rules/${encodeURIComponent(ruleId)}/rollback`,
      { method: 'POST', body: JSON.stringify({ reason }) },
    ),
};

// ────────────────────────────────────────────────────────────────────────
// phaseGapsApi — Sprint X.3 (cura/secagem editável via UI).
// Wraps GET /v1/plan/phase-gaps (merged DB + SEED view) and PATCH
// .../{from}/{to} with reason ≥10 chars. Consumed by the new
// "Cura/Secagem" tab in SettingsPage. The CPO scheduler picks up the
// new value on the next /v1/plan/cpo/schedule run via the same
// `state._load_phase_transition_gaps` loader the dispatcher uses.
// ────────────────────────────────────────────────────────────────────────

export interface PhaseGap {
  from_phase_code: string;
  to_phase_code: string;
  min_gap_hours: number;
  reason: string | null;
  n_observations: number | null;
  active: boolean;
  /** 'seed' = fallback to NELO_CURING_GAPS_SEED; 'db' = persisted edit */
  source: 'seed' | 'db' | string;
}

export const phaseGapsApi = {
  list: () => request<{ items: PhaseGap[] }>('/v1/plan/phase-gaps'),

  update: (
    fromPhaseCode: string,
    toPhaseCode: string,
    payload: { min_gap_hours: number; reason: string },
  ) =>
    request<PhaseGap>(
      `/v1/plan/phase-gaps/${encodeURIComponent(fromPhaseCode)}/${encodeURIComponent(toPhaseCode)}`,
      { method: 'PATCH', body: JSON.stringify(payload) },
    ),
};

