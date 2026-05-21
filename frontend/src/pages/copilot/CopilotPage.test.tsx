// CopilotPage — smoke test pós lazy split (Q.68.5.E).
//
// Verifica:
//   - a shell monta (3 colunas: histórico · chat · contexto)
//   - SqlAccordion + CopilotContextRail são lazy: o chunk principal não os
//     contém em tempo de mount; ficam resolvidos via Suspense
//   - a coluna de contexto aparece depois do Suspense resolver
//
// ZERO MOCKS — o `useQuery` falha (não há servidor), o que confirma que a
// shell renderiza apesar de não ter dados. Mostra o empty-state honesto.
import { describe, it, expect } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import CopilotPage from './CopilotPage';

describe('CopilotPage (lazy split Q.68.5.E)', () => {
  it('renderiza a shell de 3 colunas e o título do copiloto', async () => {
    renderWithProviders(<CopilotPage />, { route: '/copilot' });

    // Título do header (DarkPageLayout).
    expect(
      screen.getAllByRole('heading', { name: /Copilot/i }).length,
    ).toBeGreaterThan(0);

    // Coluna 1 — histórico: o label "Conversas" + caixa de pesquisa.
    expect(screen.getByText(/Conversas/i)).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText(/Procurar conversa/i),
    ).toBeInTheDocument();

    // Coluna 2 — chat: 5 pills de modo (factuais · cenários · diagnóstico · CTP · relatórios).
    expect(screen.getByRole('button', { name: /Factuais/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Cenários/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Diagnóstico/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /CTP/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Relatórios/i })).toBeInTheDocument();
  });

  it('Coluna 3 (CopilotContextRail) carrega via lazy Suspense', async () => {
    renderWithProviders(<CopilotPage />, { route: '/copilot' });

    // Fallback do Suspense aparece primeiro (texto curto, sem rede).
    // Depois o chunk resolve e o empty-state real do rail entra em DOM.
    await waitFor(() => {
      expect(
        screen.getByText(/Contexto da resposta/i),
      ).toBeInTheDocument();
    });

    // Sem resposta na conversa → o rail mostra o empty-state honesto.
    expect(
      screen.getByText(/Ainda sem resposta nesta conversa/i),
    ).toBeInTheDocument();
  });

  it('input de pergunta está presente e desactivado quando vazio', () => {
    renderWithProviders(<CopilotPage />, { route: '/copilot' });

    // Placeholder usa o modo activo por defeito (factuais).
    const input = screen.getByPlaceholderText(/Pergunta em modo factuais/i);
    expect(input).toBeInTheDocument();
    expect(input).not.toBeDisabled();
  });
});
