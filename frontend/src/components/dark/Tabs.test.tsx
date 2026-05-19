// Testes da primitiva Tabs (Q.60.G).
//
// Tabs é o componente de navegação que todas as páginas-mãe usam. Guarda o
// contrato: labels, aria-selected na tab activa, count badge, onChange no
// clique, e tab disabled não navega. É a rede de segurança da Fase 3, onde
// as páginas gigantes vão ser decompostas em tabs.
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Tabs, type TabItem } from './Tabs';

const TABS: TabItem[] = [
  { id: 'resumo', label: 'Resumo' },
  { id: 'erros', label: 'Erros', count: 3 },
  { id: 'moldes', label: 'Moldes', disabled: true },
];

describe('Tabs', () => {
  it('renderiza todas as labels como role="tab"', () => {
    render(<Tabs tabs={TABS} value="resumo" onChange={() => {}} />);
    expect(screen.getByRole('tab', { name: /Resumo/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Erros/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Moldes/ })).toBeInTheDocument();
  });

  it('marca aria-selected só na tab activa', () => {
    render(<Tabs tabs={TABS} value="erros" onChange={() => {}} />);
    expect(screen.getByRole('tab', { name: /Erros/ })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByRole('tab', { name: /Resumo/ })).toHaveAttribute(
      'aria-selected',
      'false',
    );
  });

  it('mostra o count badge da tab', () => {
    render(<Tabs tabs={TABS} value="resumo" onChange={() => {}} />);
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('clicar numa tab chama onChange com o respectivo id', async () => {
    const onChange = vi.fn();
    render(<Tabs tabs={TABS} value="resumo" onChange={onChange} />);
    await userEvent.click(screen.getByRole('tab', { name: /Erros/ }));
    expect(onChange).toHaveBeenCalledWith('erros');
  });

  it('clicar numa tab disabled não chama onChange', async () => {
    const onChange = vi.fn();
    render(<Tabs tabs={TABS} value="resumo" onChange={onChange} />);
    await userEvent.click(screen.getByRole('tab', { name: /Moldes/ }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it('variante "pills" renderiza igualmente o tablist e as tabs', () => {
    render(
      <Tabs tabs={TABS} value="resumo" onChange={() => {}} variant="pills" />,
    );
    expect(screen.getByRole('tablist')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Resumo/ })).toBeInTheDocument();
  });
});
