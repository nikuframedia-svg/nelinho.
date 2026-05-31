/**
 * renderWithProviders — testes do harness (Q.118.A1).
 *
 * Confirma que `withToast`/`withEntitySheets` embrulham os providers certos,
 * para componentes que usam useToast()/useEntitySheet() montarem sem rebentar.
 */
import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from './renderWithProviders';
import { useToastContext } from '../components/ToastProvider';
import { useEntitySheet } from '../components/entitySheets';

function ToastConsumer() {
  const toast = useToastContext();
  return <div data-testid="toast-ok">{typeof toast.success === 'function' ? 'ok' : 'no'}</div>;
}

function EntitySheetConsumer() {
  const { openSheet } = useEntitySheet();
  return <div data-testid="sheet-ok">{typeof openSheet === 'function' ? 'ok' : 'no'}</div>;
}

describe('renderWithProviders', () => {
  it('withToast embrulha ToastProvider (useToast não rebenta)', () => {
    renderWithProviders(<ToastConsumer />, { withToast: true });
    expect(screen.getByTestId('toast-ok')).toHaveTextContent('ok');
  });

  it('withEntitySheets embrulha EntitySheetProvider (useEntitySheet não rebenta)', () => {
    renderWithProviders(<EntitySheetConsumer />, { withEntitySheets: true });
    expect(screen.getByTestId('sheet-ok')).toHaveTextContent('ok');
  });

  it('sem flags, render simples continua a funcionar', () => {
    renderWithProviders(<div data-testid="plain">olá</div>);
    expect(screen.getByTestId('plain')).toHaveTextContent('olá');
  });
});
