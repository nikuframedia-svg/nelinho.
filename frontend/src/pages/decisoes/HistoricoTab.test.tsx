/**
 * HistoricoTab — DecisionDetail não rebenta com resposta real de /audit (FE-1 / Q.130.D).
 *
 * Bug: getAuditTrail devolve {decision, approvals, state_changes} mas o código
 * anterior fazia `(data ?? []).map(...)` → TypeError: trail.map is not a function.
 */
import { describe, it, expect, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '../../test/renderWithProviders';
import type { DecisionRun } from '../../lib/api';

// Mock apenas do módulo de API (não do contrato do wrapper).
vi.mock('../../lib/api', async (importOriginal) => {
  const real = await importOriginal<typeof import('../../lib/api')>();
  return {
    ...real,
    decisionsApi: {
      ...real.decisionsApi,
      list: vi.fn().mockResolvedValue({
        total: 1,
        page: 1,
        page_size: 100,
        decisions: [
          {
            id: 'd-test-1',
            title: 'Replaneamento OF-42',
            action_type: 'AUTO_PROPOSE_SCHEDULE',
            target: 'OF-42',
            status: 'APPROVED',
            before_state: {},
            proposed_by: 'operador-1',
            proposed_at: '2026-05-29T10:00:00Z',
            approvals: [],
          } satisfies DecisionRun,
        ],
      }),
      // Resposta REAL do endpoint /v1/decisions/{id}/audit
      getAuditTrail: vi.fn().mockResolvedValue({
        decision: {
          id: 'd-test-1',
          title: 'Replaneamento OF-42',
          action_type: 'AUTO_PROPOSE_SCHEDULE',
          target: 'OF-42',
          status: 'APPROVED',
          before_state: { fase: 'PROPOSTA' },
          proposed_by: 'operador-1',
          proposed_at: '2026-05-29T10:00:00Z',
          approvals: [],
        } satisfies DecisionRun,
        approvals: [
          {
            approver_id: 'supervisor-1',
            status: 'APPROVED',
            comment: 'OK',
            approved_at: '2026-05-29T11:00:00Z',
          },
        ],
        state_changes: {
          before_state: { fase: 'PROPOSTA' },
          after_state: { fase: 'APROVADA' },
        },
      }),
    },
    preferenceRulesApi: {
      ...real.preferenceRulesApi,
      list: vi.fn().mockResolvedValue([]),
    },
  };
});

// Import após o mock para apanhar a versão mockada.
const { default: HistoricoTab } = await import('./HistoricoTab');

describe('HistoricoTab — DecisionDetail (FE-1 Q.130.D)', () => {
  it('renderiza sem crash com resposta {decision, approvals, state_changes}', async () => {
    renderWithProviders(<HistoricoTab />, { route: '/decisoes' });

    // Lista carrega
    await waitFor(() => {
      expect(screen.getByText('Replaneamento OF-42')).toBeInTheDocument();
    });

    // Clicar na decisão expande o detalhe
    await userEvent.click(screen.getByText('Replaneamento OF-42'));

    // Deve mostrar evento de Proposta e Aprovação — sem TypeError
    await waitFor(() => {
      expect(screen.getByText('Proposta')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByText('Aprovação')).toBeInTheDocument();
    });

    // Deve mostrar o approver
    expect(screen.getByText(/supervisor-1/)).toBeInTheDocument();

    // Não deve ter crashed (sem mensagem de erro genérica)
    expect(screen.queryByText(/TypeError/)).toBeNull();
  });

  it('não rebenta se approvals estiver ausente', async () => {
    const { decisionsApi } = await import('../../lib/api');
    vi.mocked(decisionsApi.getAuditTrail).mockResolvedValueOnce({
      decision: {
        id: 'd-test-1',
        title: 'Replaneamento OF-42',
        action_type: 'AUTO_PROPOSE_SCHEDULE',
        target: 'OF-42',
        status: 'APPROVED',
        before_state: {},
        proposed_by: 'sys',
        proposed_at: '2026-05-29T10:00:00Z',
        approvals: [],
      },
      // approvals intencionalmente ausente (cast para testar defensividade)
      approvals: undefined as unknown as [],
      state_changes: null,
    });

    renderWithProviders(<HistoricoTab />, { route: '/decisoes' });

    await waitFor(() => {
      expect(screen.getByText('Replaneamento OF-42')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Replaneamento OF-42'));

    // Deve mostrar a proposta sem crash
    await waitFor(() => {
      expect(screen.getByText('Proposta')).toBeInTheDocument();
    });
  });
});
