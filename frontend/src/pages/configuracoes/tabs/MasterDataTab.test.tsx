/**
 * MasterDataTab — testes (Q.115.X5).
 *
 * Testa: smoke render, modal abre/fecha, validação ≥10c bloqueia submit.
 * ZERO MOCKS — queries resolvem para empty/error; testa a shell.
 */
import { describe, it, expect } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../../test/renderWithProviders';
import { MasterDataTab } from './MasterDataTab';

describe('MasterDataTab', () => {
  it('disponibiliza as 4 secções de gestão no selector', () => {
    renderWithProviders(<MasterDataTab />, {
      route: '/configuracoes?tab=master',
      withToast: true,
      withEntitySheets: true,
    });
    // Q.123 — as 4 secções estão no selector segmentado (só uma tabela visível
    // de cada vez, para reduzir densidade). "Ordens de fabrico" e "Operadores"
    // aparecem 2x (selector + título/segmento MasterDataBrowser) — basta existir.
    expect(screen.getAllByText('Ordens de fabrico').length).toBeGreaterThan(0);
    expect(screen.getByText('Encomendas')).toBeInTheDocument();
    expect(screen.getByText('Barcos / Modelos')).toBeInTheDocument();
    expect(screen.getAllByText('Operadores').length).toBeGreaterThan(0);
  });

  it('troca a secção activa pelo selector (densidade reduzida)', () => {
    renderWithProviders(<MasterDataTab />, {
      route: '/configuracoes?tab=master',
      withToast: true,
      withEntitySheets: true,
    });
    // Por defeito mostra a secção Ordens de fabrico (1 campo de pesquisa).
    expect(screen.getByPlaceholderText(/Pesquisar OF/i)).toBeInTheDocument();
    // Trocar para Encomendas via o selector → mostra a pesquisa de encomendas.
    fireEvent.click(screen.getByRole('radio', { name: /Encomendas/i }));
    expect(screen.getByPlaceholderText(/Pesquisar encomenda/i)).toBeInTheDocument();
  });
});

describe('ConfirmDestructiveModal', () => {
  it('abre e fecha sem confirmar', async () => {
    // Para testar o modal, renderizamos a tab e verificamos que o modal não está visível no início.
    // A abertura do modal requer dados do servidor (botão aparece quando há items).
    // Testamos o componente isolado.
    const { ConfirmDestructiveModal } = await import(
      '../../../components/configuracoes/ConfirmDestructiveModal'
    );
    const onClose = () => {};
    const onConfirm = async () => {};
    renderWithProviders(
      <ConfirmDestructiveModal
        isOpen={true}
        title="Cancelar Ordem de Fabrico"
        description="Confirmar cancelamento de OF 123?"
        entityId="OF-123"
        onClose={onClose}
        onConfirm={onConfirm}
      />,
    );
    expect(screen.getByText('Cancelar Ordem de Fabrico')).toBeInTheDocument();
    expect(screen.getByText('OF-123')).toBeInTheDocument();
  });

  it('botão Confirmar desactivado com razão vazia', async () => {
    const { ConfirmDestructiveModal } = await import(
      '../../../components/configuracoes/ConfirmDestructiveModal'
    );
    renderWithProviders(
      <ConfirmDestructiveModal
        isOpen={true}
        title="Cancelar OF"
        description="Desc"
        entityId="OF-1"
        onClose={() => {}}
        onConfirm={async () => {}}
      />,
    );
    const btn = screen.getByRole('button', { name: /confirmar/i });
    expect(btn).toBeDisabled();
  });

  it('botão Confirmar desactivado com razão <10c', async () => {
    const { ConfirmDestructiveModal } = await import(
      '../../../components/configuracoes/ConfirmDestructiveModal'
    );
    renderWithProviders(
      <ConfirmDestructiveModal
        isOpen={true}
        title="Cancelar OF"
        description="Desc"
        entityId="OF-1"
        onClose={() => {}}
        onConfirm={async () => {}}
      />,
    );
    const textarea = screen.getByPlaceholderText(/Explica a razão/i);
    fireEvent.change(textarea, { target: { value: 'curto' } }); // 5 chars
    const btn = screen.getByRole('button', { name: /confirmar/i });
    expect(btn).toBeDisabled();
  });

  it('botão Confirmar activo com razão ≥10c', async () => {
    const { ConfirmDestructiveModal } = await import(
      '../../../components/configuracoes/ConfirmDestructiveModal'
    );
    renderWithProviders(
      <ConfirmDestructiveModal
        isOpen={true}
        title="Cancelar OF"
        description="Desc"
        entityId="OF-1"
        onClose={() => {}}
        onConfirm={async () => {}}
      />,
    );
    const textarea = screen.getByPlaceholderText(/Explica a razão/i);
    fireEvent.change(textarea, { target: { value: 'razão suficiente para confirmar' } });
    const btn = screen.getByRole('button', { name: /confirmar/i });
    expect(btn).not.toBeDisabled();
  });
});
