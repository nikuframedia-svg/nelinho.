/**
 * DecisionCard — Q.130.K: canWrite desativa botões Aprovar/Rejeitar no modo CEO.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { DecisionCard } from './DecisionCard';
import type { DecisionRun } from '../../lib/api';

const STUB_DECISION: DecisionRun = {
  id: 'dec-001',
  title: 'Testar botões',
  action_type: 'REASSIGN_WORKER',
  target: 'op-1',
  status: 'PROPOSED',
  before_state: {},
  proposed_by: 'system',
  proposed_at: '2026-05-30T00:00:00Z',
  approvals: [],
};

describe('DecisionCard — canWrite', () => {
  const onApprove = vi.fn();
  const onReject = vi.fn();

  beforeEach(() => {
    onApprove.mockClear();
    onReject.mockClear();
  });

  it('com canWrite=false (CEO) os botões Aprovar e Rejeitar ficam desativados', () => {
    renderWithProviders(
      <DecisionCard
        decision={STUB_DECISION}
        onApprove={onApprove}
        onReject={onReject}
        isPending={false}
        canWrite={false}
      />,
    );

    const btnRejeitar = screen.getByRole('button', { name: /rejeitar decisão/i });
    const btnAprovar = screen.getByRole('button', { name: /aprovar decisão/i });

    expect(btnRejeitar).toBeDisabled();
    expect(btnAprovar).toBeDisabled();
  });

  it('com canWrite=true (Gestor) os botões Aprovar e Rejeitar ficam ativos', () => {
    renderWithProviders(
      <DecisionCard
        decision={STUB_DECISION}
        onApprove={onApprove}
        onReject={onReject}
        isPending={false}
        canWrite={true}
      />,
    );

    const btnRejeitar = screen.getByRole('button', { name: /rejeitar decisão/i });
    const btnAprovar = screen.getByRole('button', { name: /aprovar decisão/i });

    expect(btnRejeitar).not.toBeDisabled();
    expect(btnAprovar).not.toBeDisabled();
  });

  it('com canWrite=true (default), os botões ficam ativos', () => {
    renderWithProviders(
      <DecisionCard
        decision={STUB_DECISION}
        onApprove={onApprove}
        onReject={onReject}
        isPending={false}
      />,
    );

    const btnAprovar = screen.getByRole('button', { name: /aprovar decisão/i });
    expect(btnAprovar).not.toBeDisabled();
  });
});
