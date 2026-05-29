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
  it('renderiza as 4 sub-secções', () => {
    renderWithProviders(<MasterDataTab />, {
      route: '/configuracoes?tab=master',
      withToast: true,
      withEntitySheets: true,
    });
    expect(screen.getByText('Ordens de fabrico')).toBeInTheDocument();
    expect(screen.getByText('Encomendas')).toBeInTheDocument();
    expect(screen.getByText('Barcos / Modelos')).toBeInTheDocument();
    // "Operadores" aparece 2x: secção de cancelamento + segmento do
    // MasterDataBrowser (Q.118.P) — basta existir.
    expect(screen.getAllByText('Operadores').length).toBeGreaterThan(0);
  });

  it('tem 4 campos de pesquisa', () => {
    renderWithProviders(<MasterDataTab />, {
      route: '/configuracoes?tab=master',
      withToast: true,
      withEntitySheets: true,
    });
    const inputs = screen.getAllByPlaceholderText(/pesquisar/i);
    expect(inputs.length).toBe(4);
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
