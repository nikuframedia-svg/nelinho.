/**
 * DecisoesPage — smoke test das 3 sub-abas (Q.118.B).
 *
 * Confirma que a shell mostra as 3 abas (Decidir/Simulações/Histórico) e que
 * a aba default é Decidir. Queries resolvem para erro/empty sem servidor —
 * testa a shell, não os dados. ZERO MOCKS.
 */
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import DecisoesPage from './DecisoesPage';

describe('DecisoesPage — 3 sub-abas', () => {
  it('mostra as 3 abas Decidir/Simulações/Histórico', () => {
    renderWithProviders(<DecisoesPage />, {
      route: '/decisoes',
      withToast: true,
      withEntitySheets: true,
    });
    const tabs = screen.getAllByRole('tab');
    const labels = tabs.map((t) => t.textContent ?? '');
    expect(labels.some((l) => l.includes('Decidir'))).toBe(true);
    expect(labels.some((l) => l.includes('Simulações'))).toBe(true);
    expect(labels.some((l) => l.includes('Histórico'))).toBe(true);
  });

  it('aba Histórico abre via ?tab=historico', () => {
    renderWithProviders(<DecisoesPage />, {
      route: '/decisoes?tab=historico',
      withToast: true,
      withEntitySheets: true,
    });
    // O cabeçalho do HistoricoTab aparece.
    expect(screen.getByText('Histórico de decisões')).toBeInTheDocument();
  });
});
