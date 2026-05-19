// Testes do hook useTabRouting (Q.60.H).
//
// Guarda de regressão ANTES de a Fase 3 migrar as páginas gigantes para
// este hook. O hook é exercido através de um componente-sonda + router
// real (MemoryRouter via renderWithProviders).
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useSearchParams } from 'react-router-dom';
import { renderWithProviders } from '../test/renderWithProviders';
import { useTabRouting } from './useTabRouting';

const TAB_IDS = ['resumo', 'erros', 'moldes'] as const;

function TabProbe() {
  const { activeTab, setTab } = useTabRouting(TAB_IDS, 'resumo');
  const [params] = useSearchParams();
  return (
    <div>
      <span data-testid="active">{activeTab}</span>
      <span data-testid="url-tab">{params.get('tab') ?? '(none)'}</span>
      {TAB_IDS.map((id) => (
        <button key={id} type="button" onClick={() => setTab(id)}>
          ir-{id}
        </button>
      ))}
    </div>
  );
}

describe('useTabRouting', () => {
  it('sem ?tab= usa o fallback', () => {
    renderWithProviders(<TabProbe />, { route: '/qualidade' });
    expect(screen.getByTestId('active')).toHaveTextContent('resumo');
  });

  it('lê uma tab válida do ?tab=', () => {
    renderWithProviders(<TabProbe />, { route: '/qualidade?tab=erros' });
    expect(screen.getByTestId('active')).toHaveTextContent('erros');
  });

  it('?tab= com valor fora do conjunto cai no fallback', () => {
    renderWithProviders(<TabProbe />, { route: '/qualidade?tab=lixo' });
    expect(screen.getByTestId('active')).toHaveTextContent('resumo');
  });

  it('setTab muda a tab activa', async () => {
    renderWithProviders(<TabProbe />, { route: '/qualidade' });
    await userEvent.click(screen.getByRole('button', { name: 'ir-moldes' }));
    expect(screen.getByTestId('active')).toHaveTextContent('moldes');
  });

  it('setTab escreve o ?tab= no URL', async () => {
    renderWithProviders(<TabProbe />, { route: '/qualidade' });
    expect(screen.getByTestId('url-tab')).toHaveTextContent('(none)');
    await userEvent.click(screen.getByRole('button', { name: 'ir-erros' }));
    expect(screen.getByTestId('url-tab')).toHaveTextContent('erros');
  });
});
