// Testes do SqlAccordion (Q.67.4.F).
//
// Componente puro de apresentação: recebe `toolCalls` por props, sem rede.
// Cobre o contrato do sub-sprint:
//   - colapsado por defeito (não mostra SQL nem tabela)
//   - click no header abre e mostra SQL + tabela
//   - linhas ≤ 20: tabela completa, sem aviso de overflow
//   - linhas > 20: trunca às primeiras 20 e mostra "+X mais"
//   - ignora tool_calls que não são `run_sql`
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { SqlAccordion, type ToolCall } from './SqlAccordion';

function makeRows(n: number): Array<Record<string, unknown>> {
  return Array.from({ length: n }, (_, i) => ({ id: i + 1, name: `row-${i + 1}` }));
}

function makeCall(rows: number, overrides: Partial<ToolCall> = {}): ToolCall {
  return {
    tool_name: 'run_sql',
    args: { query: 'SELECT id, name FROM plan.production_orders LIMIT 5' },
    result: {
      sql: 'SELECT id, name FROM plan.production_orders LIMIT 5',
      rows: makeRows(rows),
      rows_returned: rows,
      elapsed_ms: 12.4,
    },
    ...overrides,
  };
}

describe('SqlAccordion', () => {
  it('renderiza o accordion colapsado por defeito', () => {
    render(<SqlAccordion toolCalls={[makeCall(3)]} />);

    // Cabeçalho visível...
    const trigger = screen.getByRole('button', { name: /Dados consultados/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveTextContent('1 query');

    // ...mas o corpo (SQL + tabela) ainda não.
    expect(screen.queryByText(/SELECT id, name/)).not.toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('click no header expande e mostra SQL + tabela', () => {
    render(<SqlAccordion toolCalls={[makeCall(3)]} />);

    const trigger = screen.getByRole('button', { name: /Dados consultados/i });
    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(
      screen.getByText('SELECT id, name FROM plan.production_orders LIMIT 5'),
    ).toBeInTheDocument();

    const table = screen.getByRole('table');
    const rows = within(table).getAllByRole('row');
    // 1 header + 3 data rows
    expect(rows).toHaveLength(1 + 3);
    expect(within(table).getByText('row-1')).toBeInTheDocument();
    expect(within(table).getByText('row-3')).toBeInTheDocument();
  });

  it('rows ≤ 20: tabela completa sem aviso de overflow', () => {
    render(<SqlAccordion toolCalls={[makeCall(20)]} />);
    fireEvent.click(screen.getByRole('button', { name: /Dados consultados/i }));

    const table = screen.getByRole('table');
    const dataRows = within(table).getAllByRole('row').slice(1);
    expect(dataRows).toHaveLength(20);
    expect(screen.queryByTestId('sql-rows-overflow')).not.toBeInTheDocument();
  });

  it('rows > 20: trunca a 20 e mostra "+X linhas não mostradas"', () => {
    render(<SqlAccordion toolCalls={[makeCall(42)]} />);
    fireEvent.click(screen.getByRole('button', { name: /Dados consultados/i }));

    const table = screen.getByRole('table');
    const dataRows = within(table).getAllByRole('row').slice(1);
    expect(dataRows).toHaveLength(20);
    expect(within(table).getByText('row-20')).toBeInTheDocument();
    expect(within(table).queryByText('row-21')).not.toBeInTheDocument();

    const overflow = screen.getByTestId('sql-rows-overflow');
    expect(overflow).toHaveTextContent('+ 22 linhas');
  });

  it('ignora tool_calls que não são `run_sql`', () => {
    const calls: ToolCall[] = [
      { tool_name: 'open_runbook', args: { id: 'rb-1' }, result: {} },
      makeCall(2),
    ];
    render(<SqlAccordion toolCalls={calls} />);

    // Só conta a única `run_sql` — "1 query", não "2".
    expect(
      screen.getByRole('button', { name: /Dados consultados \(1 query\)/i }),
    ).toBeInTheDocument();
  });

  it('lista vazia ou sem run_sql não renderiza nada', () => {
    const { container, rerender } = render(<SqlAccordion toolCalls={[]} />);
    expect(container).toBeEmptyDOMElement();

    rerender(
      <SqlAccordion
        toolCalls={[{ tool_name: 'open_runbook', args: {}, result: {} }]}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
