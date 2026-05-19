// QualidadePage — teste de presença pós-decomposição (Q.60.Q).
//
// Guarda a decomposição: a shell tem de continuar a montar as 10 tabs e a
// respeitar o `?tab=` do URL. As tabs disparam queries reais (ZERO MOCKS) —
// em teste resolvem para estado de erro/vazio; o teste afirma só a shell.
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import QualidadePage from './QualidadePage';

describe('QualidadePage (shell decomposto)', () => {
  it('renderiza as 10 tabs da página', () => {
    renderWithProviders(<QualidadePage />, { route: '/qualidade' });
    expect(screen.getAllByRole('tab')).toHaveLength(10);
  });

  it('a tab activa segue o ?tab= do URL', () => {
    renderWithProviders(<QualidadePage />, { route: '/qualidade?tab=moldes' });
    expect(screen.getByRole('tab', { name: /Moldes/ })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });
});
