/**
 * CellOpsSheet + OperationEditSheet — nomes de barco (Q.154.B).
 *
 * Ambas mostravam só `#order_id`. O `ScheduledOp` já traz `op.cliente` (nome do
 * barco/cliente, de client_name no plano e barco_nome nos actuals). Agora é esse
 * o rótulo principal, com o código pequeno ao lado / entre parêntesis.
 */
import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { CellOpsSheet } from './CellOpsSheet';
import { OperationEditSheet } from './OperationEditSheet';
import type { ScheduledOp } from './types';

const op = (over: Partial<ScheduledOp>): ScheduledOp => ({
  id: 'op-1',
  phase_id: 'LAM',
  phase_name: 'Laminagem',
  source: 'plan',
  ...over,
});

describe('CellOpsSheet — nome do barco (Q.154.B)', () => {
  it('mostra o nome do barco com o código pequeno ao lado', () => {
    renderWithProviders(
      <CellOpsSheet
        ops={[op({ cliente: 'K1 Vanquish', order_id: '21564' })]}
        onPick={() => {}}
        onClose={() => {}}
      />,
    );
    expect(screen.getByText(/K1 Vanquish/)).toBeInTheDocument();
    expect(screen.getByText('#21564', { exact: false })).toBeInTheDocument();
  });

  it('sem cliente cai no código do barco', () => {
    renderWithProviders(
      <CellOpsSheet ops={[op({ order_id: '30000' })]} onPick={() => {}} onClose={() => {}} />,
    );
    expect(screen.getByText('#30000', { exact: false })).toBeInTheDocument();
  });
});

describe('OperationEditSheet — nome do barco (Q.154.B)', () => {
  it('subtítulo prefere o nome do barco (código entre parêntesis)', () => {
    renderWithProviders(
      <OperationEditSheet
        op={op({ cliente: 'K1 Vanquish', order_id: '21564', operator_name: 'Maria Silva' })}
        operators={[]}
        phases={[]}
        isPending={false}
        onSave={vi.fn()}
        onClose={() => {}}
      />,
    );
    expect(screen.getByText(/K1 Vanquish \(#21564\)/)).toBeInTheDocument();
  });
});
