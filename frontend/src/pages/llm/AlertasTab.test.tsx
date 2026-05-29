/**
 * AlertasTab — testes (Q.118.J).
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { AlertasTab } from './AlertasTab';
import { copilotAlertsApi, type CopilotAlertItem } from '../../lib/api';

afterEach(() => vi.restoreAllMocks());

function alert(over: Partial<CopilotAlertItem>): CopilotAlertItem {
  return {
    id: 'a1',
    severity: 'WARN',
    code: 'AL08',
    title: 'Molde a precisar de manutenção',
    message_pt: 'O molde X passou o limite de ciclos.',
    context: {},
    entity_refs: [],
    status: 'open',
    created_at: null,
    acknowledged_at: null,
    acknowledged_by: null,
    resolved_at: null,
    ...over,
  };
}

describe('AlertasTab', () => {
  it('lista alertas com severidade + acções', async () => {
    vi.spyOn(copilotAlertsApi, 'list').mockResolvedValue([alert({})]);
    renderWithProviders(<AlertasTab />, { withToast: true });
    await waitFor(() =>
      expect(screen.getByText('Molde a precisar de manutenção')).toBeInTheDocument(),
    );
    expect(screen.getByText('WARN')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /resolver/i })).toBeInTheDocument();
  });

  it('empty state honesto sem alertas', async () => {
    vi.spyOn(copilotAlertsApi, 'list').mockResolvedValue([]);
    renderWithProviders(<AlertasTab />, { withToast: true });
    await waitFor(() => expect(screen.getByText('Sem alertas abertos')).toBeInTheDocument());
  });
});
