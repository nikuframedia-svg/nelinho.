/**
 * selection.test.ts — testa opMatchesSelection (C2).
 */

import { describe, it, expect } from 'vitest';
import { opMatchesSelection } from './selection';
import type { ScheduledOp } from './types';
import type { PlanSelection } from './selection';

const op: ScheduledOp = {
  id: 'op-1',
  phase_id: 'LAMINAGEM',
  phase_name: 'Laminagem',
  order_id: 'OF-100',
  operator_id: 'op-id-42',
  operator_name: 'João Silva',
  cliente: 'cliente-xyz',
};

describe('opMatchesSelection', () => {
  it('retorna false quando sel é null', () => {
    expect(opMatchesSelection(op, null)).toBe(false);
  });

  it('kind=op: true se id coincide', () => {
    const sel: PlanSelection = { kind: 'op', id: 'op-1' };
    expect(opMatchesSelection(op, sel)).toBe(true);
  });

  it('kind=op: false se id diferente', () => {
    const sel: PlanSelection = { kind: 'op', id: 'op-2' };
    expect(opMatchesSelection(op, sel)).toBe(false);
  });

  it('kind=phase: true se phase_id coincide', () => {
    const sel: PlanSelection = { kind: 'phase', id: 'LAMINAGEM' };
    expect(opMatchesSelection(op, sel)).toBe(true);
  });

  it('kind=phase: false se phase_id diferente', () => {
    const sel: PlanSelection = { kind: 'phase', id: 'MONTAGEM' };
    expect(opMatchesSelection(op, sel)).toBe(false);
  });

  it('kind=boat: true se order_id coincide', () => {
    const sel: PlanSelection = { kind: 'boat', id: 'OF-100' };
    expect(opMatchesSelection(op, sel)).toBe(true);
  });

  it('kind=boat: usa op.id quando order_id ausente', () => {
    const opSemOrder: ScheduledOp = { ...op, order_id: undefined };
    const sel: PlanSelection = { kind: 'boat', id: 'op-1' };
    expect(opMatchesSelection(opSemOrder, sel)).toBe(true);
  });

  it('kind=operator: true se operator_id coincide', () => {
    const sel: PlanSelection = { kind: 'operator', id: 'op-id-42' };
    expect(opMatchesSelection(op, sel)).toBe(true);
  });

  it('kind=operator: usa operator_name quando operator_id ausente', () => {
    const opSemId: ScheduledOp = { ...op, operator_id: undefined };
    const sel: PlanSelection = { kind: 'operator', id: 'João Silva' };
    expect(opMatchesSelection(opSemId, sel)).toBe(true);
  });

  it('kind=cliente: true se cliente coincide', () => {
    const sel: PlanSelection = { kind: 'cliente', id: 'cliente-xyz' };
    expect(opMatchesSelection(op, sel)).toBe(true);
  });

  it('kind=cliente: false se cliente diferente', () => {
    const sel: PlanSelection = { kind: 'cliente', id: 'outro-cliente' };
    expect(opMatchesSelection(op, sel)).toBe(false);
  });
});
