// Testes da primitiva EmptyState (Q.60.G).
//
// EmptyState é a forma canónica de mostrar "sem dados" — central ao
// invariante ZERO MOCKS (o ramo vazio renderiza isto, nunca um placeholder
// com dados). Os testes usam `mascot={false}` para isolar a lógica do
// EmptyState do componente CopilotMascot.
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmptyState } from './EmptyState';

describe('EmptyState', () => {
  it('renderiza o título', () => {
    render(<EmptyState title="Sem barcos em produção" mascot={false} />);
    expect(screen.getByText('Sem barcos em produção')).toBeInTheDocument();
  });

  it('renderiza o hint quando fornecido', () => {
    render(
      <EmptyState
        title="Vazio"
        hint="Importa ordens do ERP primeiro"
        mascot={false}
      />,
    );
    expect(
      screen.getByText('Importa ordens do ERP primeiro'),
    ).toBeInTheDocument();
  });

  it('sem hint não renderiza texto secundário', () => {
    const { container } = render(<EmptyState title="Vazio" mascot={false} />);
    expect(container.querySelector('p')).toBeNull();
  });

  it('renderiza a acção quando fornecida', () => {
    render(
      <EmptyState
        title="Vazio"
        mascot={false}
        action={<button>Importar do ERP</button>}
      />,
    );
    expect(
      screen.getByRole('button', { name: 'Importar do ERP' }),
    ).toBeInTheDocument();
  });

  it('renderiza com o mascote por defeito sem rebentar', () => {
    render(<EmptyState title="Sem dados" />);
    expect(screen.getByText('Sem dados')).toBeInTheDocument();
  });
});
