/**
 * DecisionHubActions — testes (Q.118.D).
 *
 * Confirma a teia de ligações: Ver plano só com commit_sha, Explicar sempre,
 * ícone/label do action_type. O € depende do servidor (margin preview) →
 * escondido sem dados (ZERO MOCKS).
 */
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { DecisionHubActions } from './DecisionHubActions';
import type { DecisionRun } from '../../lib/api';

function mk(over: Partial<DecisionRun>): DecisionRun {
  return {
    id: 'd1',
    title: 'Replaneamento automático',
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

describe('DecisionHubActions', () => {
  it('mostra Ver plano quando há commit_sha + Explicar + action_type', () => {
    renderWithProviders(
      <DecisionHubActions decision={mk({ sandbox_result: { commit_sha: 'abc123' } })} />,
      { route: '/decisoes' },
    );
    expect(screen.getByText('Ver plano')).toBeInTheDocument();
    expect(screen.getByText('Explicar')).toBeInTheDocument();
    expect(screen.getByText('AUTO_PROPOSE_SCHEDULE')).toBeInTheDocument();
  });

  it('esconde Ver plano sem commit_sha (degradação honesta)', () => {
    renderWithProviders(<DecisionHubActions decision={mk({ sandbox_result: {} })} />, {
      route: '/decisoes',
    });
    expect(screen.queryByText('Ver plano')).not.toBeInTheDocument();
    expect(screen.getByText('Explicar')).toBeInTheDocument();
  });
});
