// Testes de regressão FE-7/FE-8 (Q.130.E).
//
// Garante que o componente NÃO rebenta quando:
//   - content_structured é {causal_audit: {...}} — sem "summary" nem "meta"
//   - response é null/undefined
//
// Antes do fix, a hidratação fazia cast directo e ResponseBody acedia
// a response.facts.length sem guarda → crash.
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CopilotChatMessage } from './CopilotChatMessage';
import type { ChatMessage } from './copilotPageHelpers';

// CopilotChart usa ResizeObserver; faz mock mínimo para não crashar em jsdom
vi.mock('./CopilotChart', () => ({
  CopilotChart: () => null,
}));

const noopAction = vi.fn();

describe('CopilotChatMessage — guarda defensiva FE-7/FE-8', () => {
  it('renderiza mensagem de utilizador sem crash', () => {
    const msg: ChatMessage = {
      id: '1',
      role: 'user',
      text: 'Quantas OFs estão abertas?',
      when: '10:00',
    };
    render(
      <CopilotChatMessage message={msg} onAction={noopAction} actionPending={false} />,
    );
    expect(screen.getByText('Quantas OFs estão abertas?')).toBeTruthy();
  });

  it('renderiza mensagem copiloto com causal_audit (sem summary) sem crash', () => {
    // Simula o que chega da API quando content_structured = {causal_audit:{...}}
    // Após FE-7, a hidratação em CopilotPage.tsx já limpa response=undefined.
    // Este teste verifica que mesmo que response seja undefined, o componente não rebenta.
    const msg: ChatMessage = {
      id: '2',
      role: 'copilot',
      text: 'pergunta de causalidade',
      when: '10:01',
      response: undefined, // hidratação FE-7 pôs undefined para causal_audit
    };
    render(
      <CopilotChatMessage message={msg} onAction={noopAction} actionPending={false} />,
    );
    expect(screen.getByText('pergunta de causalidade')).toBeTruthy();
  });

  it('renderiza mensagem copiloto com CopilotResponse válida sem crash', () => {
    const msg: ChatMessage = {
      id: '3',
      role: 'copilot',
      text: 'Há 12 OFs abertas.',
      when: '10:02',
      response: {
        suggestion_id: 'sg-1',
        correlation_id: 'cr-1',
        type: 'ANSWER',
        intent: 'generic',
        summary: 'Há 12 OFs abertas.',
        facts: [
          { text: 'Fonte: production_orders', citations: [] },
        ],
        actions: [],
        warnings: [],
        meta: { model: 'gemma4:e4b', tokens: 50, latency_ms: 800, validation_passed: true },
      },
    };
    render(
      <CopilotChatMessage message={msg} onAction={noopAction} actionPending={false} />,
    );
    expect(screen.getByText('Fonte: production_orders')).toBeTruthy();
    expect(screen.getByText('gemma4:e4b')).toBeTruthy();
  });
});
