/**
 * COPILOT Types
 * Separate types file to ensure exports are recognized
 */

/** Q.173.AL — explicação estruturada de uma resposta Cube.
 *  Espelha AskCubeExplicacao do backend (ask_cube.py).
 *  Só presente em respostas do caminho Cube (status ok). */
export interface CubeExplicacao {
  /** Tabela de origem (sql_table do cube, ex: "mart_producao"). */
  tabela: string | null;
  /** Lista de measures usadas e a expressão SQL de cada uma. */
  measures: Array<{ nome: string; formula_sql: string }>;
  /** Filtros aplicados em formato humanizado. */
  filtros: string[];
  /** Período usado, ex: "2026-04-01 a 2026-04-30". Null se sem período. */
  periodo: string | null;
  /** Sempre "Cube" para estes endpoints. */
  fonte: string;
}

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
    payload: any;
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
  /** Q.173.AL — só presente em respostas do caminho Cube (status ok). */
  explicacao?: CubeExplicacao | null;
}

export interface DailyFeedbackResponse {
  date: string;
  bullets: Array<{
    severity: "INFO" | "WARN" | "CRITICAL";
    title: string;
    text: string;
    citations: any[];
    suggested_runbooks: string[];
    suggested_actions: any[];
  }>;
  generated_at: string;
  last_updated: string;
}


