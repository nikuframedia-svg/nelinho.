// Testes do ErrorBoundary global (Q.68.5.D).
//
// O ErrorBoundary é o net de segurança que substitui o anti-padrão
// `data ?? []` para mascarar erros: em vez de renderizar uma página
// "vazia" silenciosamente quando uma query lança, mostramos um
// fallback explícito (default ou custom) e registamos com a `label`
// do contexto. Os testes cobrem children OK, captura de erro,
// fallback custom e propagação da label nos logs.

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from './ErrorBoundary';

function Bomb({ message = 'kaboom' }: { message?: string }): never {
  throw new Error(message);
}

describe('ErrorBoundary', () => {
  // Silenciar o React error overlay nos logs do teste.
  const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

  afterEach(() => {
    errorSpy.mockClear();
  });

  it('renderiza os children quando não há erro', () => {
    render(
      <ErrorBoundary>
        <div>conteudo ok</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText('conteudo ok')).toBeInTheDocument();
  });

  it('renderiza o fallback default quando um filho lança', () => {
    render(
      <ErrorBoundary>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Algo correu mal')).toBeInTheDocument();
    expect(screen.getByText('kaboom')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Recarregar/i }),
    ).toBeInTheDocument();
  });

  it('inclui o label no título quando fornecido', () => {
    render(
      <ErrorBoundary label="CopilotPage">
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText('Erro em CopilotPage')).toBeInTheDocument();
  });

  it('renderiza o fallback custom quando fornecido', () => {
    render(
      <ErrorBoundary fallback={<div>fallback custom</div>}>
        <Bomb />
      </ErrorBoundary>,
    );
    expect(screen.getByText('fallback custom')).toBeInTheDocument();
    expect(screen.queryByText('Algo correu mal')).toBeNull();
  });

  it('propaga o label nos logs do componentDidCatch', () => {
    render(
      <ErrorBoundary label="TestLabel">
        <Bomb message="explosao-teste" />
      </ErrorBoundary>,
    );
    // Procurar entre todas as chamadas (React também loga o próprio erro).
    const matched = errorSpy.mock.calls.some((call) => {
      const first = call[0];
      return typeof first === 'string' && first.includes('[TestLabel] caught:');
    });
    expect(matched).toBe(true);
  });
});
