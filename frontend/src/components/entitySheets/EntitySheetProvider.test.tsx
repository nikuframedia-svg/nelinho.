/**
 * EntitySheetProvider + Clickable — testes (Q.118.C).
 *
 * Fecha a lacuna "zero testes" das entity sheets. Prova o fix do operador:
 * clicar abre o sheet (?sheet=&id=) para os 5 kinds, incluindo operador
 * (antes excluído do VALID_KINDS → nunca abria).
 */
import { describe, it, expect } from 'vitest';
import { screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '../../test/renderWithProviders';
import { Clickable, useEntitySheet, type EntityKind } from './index';

const KINDS: EntityKind[] = ['modelo', 'fase', 'cliente', 'encomenda', 'operador'];

function Probe() {
  const { current } = useEntitySheet();
  return (
    <div data-testid="current">
      {current ? `${current.kind}:${current.id}` : 'none'}
    </div>
  );
}

describe('EntitySheetProvider + Clickable', () => {
  it.each(KINDS)('clicar num %s abre o sheet (fix operador)', (kind) => {
    renderWithProviders(
      <>
        <Clickable kind={kind} id={`X-${kind}`}>
          {kind}
        </Clickable>
        <Probe />
      </>,
      { withEntitySheets: true },
    );

    expect(screen.getByTestId('current')).toHaveTextContent('none');
    fireEvent.click(screen.getByText(kind));
    expect(screen.getByTestId('current')).toHaveTextContent(`${kind}:X-${kind}`);
  });
});
