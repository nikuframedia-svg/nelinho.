/**
 * ruleHelpers — lógica partilhada da página /regras (Q.52.L).
 *
 * Concentra: a matriz ACTION_WIRING espelhada do backend, o serializer
 * payload→YAML, os mapas de estado→tom e o wrapper tipado para
 * `GET /v1/governance/rule-firings` (que ainda não tem entrada própria
 * em lib/api.ts — usamos o `apiFetch` exportado).
 */

import { apiFetch, type YamlPolicyRule } from '../../lib/api';

// ─── ACTION_WIRING ──────────────────────────────────────────────────────────
// Espelhada de src/governance/yaml_policy/dispatchers.py. Quando um
// dispatcher passar de wired=False→True no backend, flipar AQUI também.
// Test assertion no backend: test_action_wiring_matrix_has_entry_per_action_type.
export const ACTION_WIRING: Record<string, boolean> = {
  alert: true, // Q.17.F.4 — wired a CopilotAlert row
  block: true,
  modify_fitness: true,
  reassign_worker: true, // Q.17.F.7 — wired a governance.decision_run
  propose_maintenance: true, // Q.17.F.6 — wired a governance.decision_run
  notify: true, // Q.17.F.8 — wired ao RealtimeBridge SSE fan-out
  set_config: true,
  create_decision: true, // Q.17.F.6 — wired a governance.decision_run
  pause_writes: true, // Q.17.F.9 — wired ao PauseWritesMiddleware
  execute_runbook: true, // Q.115.H — wired a governance.decision_run (execute_runbook)
};

/** Devolve as actions de uma regra cujo subsistema ainda não está ligado. */
export function stubbedActions(rule: YamlPolicyRule): string[] {
  const raw = (rule.payload.then ?? [])
    .map((step) => step.action)
    .filter((a) => ACTION_WIRING[a] === false);
  return Array.from(new Set(raw));
}

// ─── Estado → tom visual ────────────────────────────────────────────────────
export type RuleStatus = YamlPolicyRule['status'];

export const STATUS_VARIANTS: Record<
  RuleStatus,
  'success' | 'warning' | 'danger' | 'info' | 'neutral'
> = {
  proposed: 'warning',
  approved: 'info',
  active: 'success',
  suspended: 'neutral',
  rolled_back: 'danger',
  rejected: 'danger',
};

export const STATUS_LABELS: Record<RuleStatus, string> = {
  proposed: 'Proposta',
  approved: 'Aprovada',
  active: 'Activa',
  suspended: 'Suspensa',
  rolled_back: 'Revertida',
  rejected: 'Rejeitada',
};

export const EVENT_LABELS: Record<string, string> = {
  schedule_propose: 'Schedule proposto',
  schedule_committed: 'Schedule comitado',
  kpi_threshold_crossed: 'KPI cruza limite',
  mold_usage_threshold: 'Molde atinge ciclo',
  worker_absent: 'Operador ausente',
  quality_event_logged: 'Evento qualidade',
  transport_loaded: 'Camião carregado',
  phase_drift_detected: 'Drift de fase',
  decision_pending: 'Decisão pendente',
  rule_rejected: 'Regra rejeitada',
  wip_threshold: 'WIP atinge limite',
  time_trigger: 'Trigger temporal',
};

// ─── Axiomas Spelke ─────────────────────────────────────────────────────────
export const AXIOM_DESC: Record<string, string> = {
  continuity: 'Objectos persistem no tempo',
  exclusivity: 'Um objecto, um lugar',
  identity: 'Identidade preservada',
  contact: 'Causalidade por contacto',
  agency: 'Acção tem agente',
  cohesion: 'Partes do todo',
  solidity: 'Não atravessável',
  capacity: 'Capacidade ≥ 0',
  precedence: 'Precedência das fases',
};

// ─── payload → YAML ─────────────────────────────────────────────────────────
/** Serializa deterministicamente o payload da regra para o visor YAML. */
export function payloadToYaml(payload: YamlPolicyRule['payload']): string {
  const lines: string[] = [];
  lines.push(`id: ${payload.id}`);
  lines.push(`description: |`);
  for (const ln of payload.description.split('\n')) lines.push(`  ${ln}`);
  lines.push(`when:`);
  lines.push(`  event: ${payload.when.event}`);
  if (payload.when.conditions?.length) {
    lines.push(`  conditions:`);
    for (const c of payload.when.conditions) {
      lines.push(`    - field: ${c.field}`);
      lines.push(`      op: ${c.op}`);
      lines.push(`      value: ${JSON.stringify(c.value)}`);
    }
  } else {
    lines.push(`  conditions: []`);
  }
  lines.push(`then:`);
  for (const a of payload.then) {
    lines.push(`  - action: ${a.action}`);
    if (Object.keys(a.params).length) {
      lines.push(`    params:`);
      for (const [k, v] of Object.entries(a.params)) {
        lines.push(`      ${k}: ${JSON.stringify(v)}`);
      }
    } else {
      lines.push(`    params: {}`);
    }
  }
  if (payload.constraints?.axioms_required?.length) {
    lines.push(`constraints:`);
    lines.push(`  axioms_required:`);
    for (const ax of payload.constraints.axioms_required) {
      lines.push(`    - ${ax}`);
    }
  }
  if (payload.safety) {
    lines.push(`safety:`);
    lines.push(`  requires_human_approval: true`);
    if (payload.safety.max_fires_per_day !== undefined) {
      lines.push(`  max_fires_per_day: ${payload.safety.max_fires_per_day}`);
    }
    if (payload.safety.expires) {
      lines.push(`  expires: ${payload.safety.expires}`);
    }
  }
  return lines.join('\n');
}

// ─── rule-firings (sem wrapper dedicado em api.ts) ──────────────────────────
export interface RuleFiring {
  id: string;
  rule_id: string;
  variant_id: string | null;
  fired_at: string;
  last_fired_at: string | null;
  fire_count: number;
  outcome: string;
  dedupe_key: string | null;
  correlation_id: string | null;
  trigger_payload: Record<string, unknown>;
  rule_output: Record<string, unknown>;
  accepted_at: string | null;
  accepted_by: string | null;
  notes: string | null;
}

/** GET /v1/governance/rule-firings — disparos da regra seleccionada. */
export function listRuleFirings(params: {
  rule_id?: string;
  limit?: number;
}): Promise<RuleFiring[]> {
  const qs = new URLSearchParams();
  if (params.rule_id) qs.set('rule_id', params.rule_id);
  qs.set('limit', String(params.limit ?? 20));
  return apiFetch<RuleFiring[]>(`/v1/governance/rule-firings?${qs.toString()}`);
}

export const FIRING_OUTCOME_LABELS: Record<string, string> = {
  proposed: 'Proposto',
  accepted: 'Aceite',
  rejected: 'Rejeitado',
  expired: 'Expirado',
  superseded: 'Substituído',
};

export const FIRING_OUTCOME_VARIANTS: Record<
  string,
  'success' | 'warning' | 'danger' | 'info' | 'neutral'
> = {
  proposed: 'info',
  accepted: 'success',
  rejected: 'danger',
  expired: 'neutral',
  superseded: 'neutral',
};
