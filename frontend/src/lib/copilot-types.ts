/**
 * COPILOT Types
 * Separate types file to ensure exports are recognized
 */

export interface CopilotAskRequest {
  user_query: string;
  entity_type?: string;
  entity_id?: string;
  context_window_hours?: number;
  include_citations?: boolean;
  idempotency_key?: string;
}

export interface CopilotResponse {
  suggestion_id: string;
  correlation_id: string;
  type: "ANSWER" | "RUNBOOK_RESULT" | "PROPOSAL" | "ERROR";
  intent: "explain_oee" | "explain_plan_change" | "quality_summary" | "data_integrity" | "generic";
  summary: string;
  facts: Array<{
    text: string;
    citations: Array<{
      source_type: "db" | "rag" | "event" | "calculation";
      ref: string;
      label: string;
      confidence: number;
      trust_index: number;
    }>;
  }>;
  actions: Array<{
    action_type: "CREATE_DECISION_PR" | "DRY_RUN" | "OPEN_ENTITY" | "RUN_RUNBOOK";
    label: string;
    requires_approval: boolean;
    payload: Record<string, unknown>;
  }>;
  warnings: Array<{
    code: "INSUFFICIENT_EVIDENCE" | "SECURITY_FLAG" | "LOW_TRUST_INDEX" | "MODEL_OFFLINE" | "VALIDATION_FAILED" | "SERVICE_ERROR";
    message: string;
  }>;
  meta: {
    model: string;
    tokens: number;
    latency_ms: number;
    validation_passed: boolean;
  };
}

export interface DailyFeedbackResponse {
  date: string;
  bullets: Array<{
    severity: "INFO" | "WARN" | "CRITICAL";
    title: string;
    text: string;
    citations: Array<{ label: string; ref?: string; [k: string]: unknown }>;
    suggested_runbooks: string[];
    suggested_actions: unknown[];
  }>;
  generated_at: string;
  last_updated: string;
}


