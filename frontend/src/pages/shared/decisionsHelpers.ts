// Tipos, constantes e helpers da DecisionsPage (Q.60.AE).
import { type DecisionRun } from '../../lib/api';

export type DecisionStatus = 'PROPOSED' | 'APPROVED' | 'EXECUTED' | 'ROLLED_BACK' | 'REJECTED';

// ─── Sprint Q.9 Onda 3.4 — severity buckets + anti-fatigue ───────────────
//
// Plan v4 §8 calls out three behaviours we owed the manager:
//   1. Bulk approve (WG04)  — multi-select + a single round trip
//   2. Severity grouping (WG04) — red / amber / green badges so a quick
//      scan tells you which decisions need attention now.
//   3. Anti-fatigue (WG05) — when there are >ANTIFATIGUE_THRESHOLD
//      pending decisions, default to showing the top N by impact so
//      the operator isn't drowning. Toggle off to see all.
export const ANTIFATIGUE_THRESHOLD = 20;
export const ANTIFATIGUE_TOP_N = 5;

export type Severity = 'critical' | 'warning' | 'normal';

export function deriveSeverity(d: DecisionRun): Severity {
  // Heuristic from action_type + status, with a safe default of "normal".
  // Real severity should land via a dedicated `severity` field on the
  // payload (Sprint Q.9 backend follow-up); until then we infer.
  const t = (d.action_type || '').toLowerCase();
  if (t.includes('emergency') || t.includes('critical') || t.includes('rollback')) {
    return 'critical';
  }
  if (
    d.status === 'PROPOSED' &&
    (t.includes('reschedule') || t.includes('mold') || t.includes('rework'))
  ) {
    return 'warning';
  }
  return 'normal';
}

export const SEVERITY_TONE: Record<Severity, { dot: string; label: string }> = {
  critical: { dot: 'bg-rose-400', label: 'Crítico' },
  warning: { dot: 'bg-amber-400', label: 'Atenção' },
  normal: { dot: 'bg-emerald-400', label: 'Optimização' },
};


