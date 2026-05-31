/**
 * selection.ts — estado de seleção partilhado entre as 4 vistas (C2).
 *
 * Uma seleção destaca operações que correspondem ao critério em todas as
 * vistas ao mesmo tempo. Clicar de novo na mesma seleção limpa.
 */

import type { ScheduledOp } from './types';

// ─── Tipos ────────────────────────────────────────────────────────────────────

export type SelectionKind = 'op' | 'phase' | 'boat' | 'operator' | 'cliente';

export interface PlanSelection {
  kind: SelectionKind;
  id: string;
}

// ─── Matcher ──────────────────────────────────────────────────────────────────

/**
 * Devolve true se a operação corresponde à seleção activa.
 *
 * - op      → identidade directa
 * - phase   → op.phase_id
 * - boat    → op.order_id ?? op.id
 * - operator→ op.operator_id ?? op.operator_name
 * - cliente → op.cliente
 */
export function opMatchesSelection(
  op: ScheduledOp,
  sel: PlanSelection | null,
): boolean {
  if (!sel) return false;
  switch (sel.kind) {
    case 'op':
      return op.id === sel.id;
    case 'phase':
      return op.phase_id === sel.id;
    case 'boat':
      return (op.order_id ?? op.id) === sel.id;
    case 'operator':
      return (op.operator_id ?? op.operator_name) === sel.id;
    case 'cliente':
      return op.cliente === sel.id;
    default:
      return false;
  }
}
