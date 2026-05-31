/**
 * decisionEntities — testes do mapeamento decisão → entidades clicáveis (Q.118.C).
 */
import { describe, it, expect } from 'vitest';
import { decisionEntities } from './decisionEntities';
import type { DecisionRun } from '../../lib/api';

function mk(over: Partial<DecisionRun>): DecisionRun {
  return {
    id: 'd1',
    title: 't',
    action_type: 'AUTO_PROPOSE_SCHEDULE',
    target: 'OF-9',
    status: 'PROPOSED',
    before_state: {},
    proposed_by: 'sys',
    proposed_at: '2026-05-29T10:00:00Z',
    approvals: [],
    ...over,
  };
}

describe('decisionEntities', () => {
  it('extrai encomenda do work_order_id', () => {
    const e = decisionEntities(mk({ action_data: { work_order_id: 123 } }));
    expect(e).toContainEqual({ kind: 'encomenda', id: '123', label: '#123' });
  });

  it('extrai encomenda/fase/operador das operations (distinct)', () => {
    const e = decisionEntities(
      mk({
        sandbox_result: {
          operations: [
            { order_id: 'OF-9', phase_id: 'LAMINAGEM', workers: ['op-aaaaaaaa', 'op-bbbbbbbb'] },
            { order_id: 'OF-9', phase_id: 'LAMINAGEM', workers: ['op-aaaaaaaa'] },
          ],
        },
      }),
    );
    const kinds = e.map((x) => x.kind);
    expect(e.filter((x) => x.kind === 'encomenda').length).toBe(1); // distinct
    expect(e.filter((x) => x.kind === 'fase').length).toBe(1);
    expect(e.filter((x) => x.kind === 'operador').length).toBe(2);
    expect(kinds).toContain('operador');
  });

  it('omite quando não há entidades (sem texto falso)', () => {
    const e = decisionEntities(mk({ action_data: {}, sandbox_result: {} }));
    expect(e).toEqual([]);
  });
});
