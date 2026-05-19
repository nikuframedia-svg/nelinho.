/**
 * CopilotContextRail — coluna direita do /copilot (Q.52.N).
 *
 * Port do "rail de contexto" do protótipo NELO. ZERO MOCKS: as fontes
 * e as acções derivam da ÚLTIMA resposta real do copiloto
 * (CopilotResponse) — citações agrupadas por `source_type`/`ref`,
 * acções de `response.actions`. Sem resposta ainda → empty state
 * honesto que explica porquê.
 */

import type { ReactNode } from 'react';
import { Database, Sparkles, Check, Play, ExternalLink } from 'lucide-react';
import type { CopilotResponse } from '../../lib/copilot-types';

const SOURCE_TYPE_LABEL: Record<string, string> = {
  db: 'base de dados',
  rag: 'documento',
  event: 'evento',
  calculation: 'cálculo',
};

const ACTION_ICON: Record<string, ReactNode> = {
  CREATE_DECISION_PR: <Check size={11} />,
  DRY_RUN: <Play size={11} />,
  OPEN_ENTITY: <ExternalLink size={11} />,
  RUN_RUNBOOK: <Play size={11} />,
};

const labelSm = {
  fontSize: 10.5,
  color: 'var(--fg-3)',
  textTransform: 'uppercase' as const,
  letterSpacing: 0.4,
  fontWeight: 600,
};

export interface CopilotContextRailProps {
  /** Última resposta do copiloto na conversa activa (ou null). */
  lastResponse: CopilotResponse | null;
  onAction: (action: CopilotResponse['actions'][number]) => void;
  actionPending: boolean;
}

export function CopilotContextRail({
  lastResponse,
  onAction,
  actionPending,
}: CopilotContextRailProps): ReactNode {
  // Fontes distintas consultadas na última resposta.
  const sources = lastResponse
    ? Array.from(
        new Map(
          lastResponse.facts
            .flatMap((f) => f.citations)
            .map((c) => [`${c.source_type}:${c.ref}`, c]),
        ).values(),
      )
    : [];

  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        minHeight: 0,
      }}
    >
      <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--bd-1)' }}>
        <div style={labelSm}>Contexto da resposta</div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 12 }}>
        {!lastResponse ? (
          <div className="text-center py-10 px-2">
            <Database className="h-7 w-7 text-fg-3 mx-auto mb-2" />
            <p className="text-xs text-fg-2 leading-relaxed">
              Ainda sem resposta nesta conversa. Faz uma pergunta — as fontes
              consultadas e as acções disponíveis aparecem aqui.
            </p>
          </div>
        ) : (
          <>
            {/* Resumo */}
            <div style={{ ...labelSm, marginBottom: 6 }}>Resumo</div>
            <p className="text-xs text-fg-1 leading-relaxed mb-3.5">
              {lastResponse.summary}
            </p>

            {/* Fontes consultadas */}
            <div style={{ ...labelSm, margin: '14px 0 6px' }}>
              Fontes consultadas ({sources.length})
            </div>
            {sources.length === 0 ? (
              <p className="text-xs text-fg-3">
                Esta resposta não citou fontes — vê os avisos no chat.
              </p>
            ) : (
              sources.map((c, i) => (
                <div
                  key={i}
                  className="rounded bg-bg-2 mb-1"
                  style={{ padding: '4px 8px' }}
                >
                  <div
                    className="font-mono text-fg-2"
                    style={{ fontSize: 10.5 }}
                    title={c.ref}
                  >
                    {c.label}
                  </div>
                  <div className="text-fg-4" style={{ fontSize: 9 }}>
                    {SOURCE_TYPE_LABEL[c.source_type] ?? c.source_type} · confiança{' '}
                    {(c.confidence * 100).toFixed(0)}%
                  </div>
                </div>
              ))
            )}

            {/* Acções disponíveis */}
            <div style={{ ...labelSm, margin: '14px 0 6px' }}>
              Acções disponíveis ({lastResponse.actions.length})
            </div>
            {lastResponse.actions.length === 0 ? (
              <p className="text-xs text-fg-3">
                Esta resposta não propôs acções.
              </p>
            ) : (
              lastResponse.actions.map((a, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => onAction(a)}
                  disabled={actionPending}
                  className="w-full flex items-center gap-2 rounded-md border border-bd-1 bg-bg-2 text-fg-1 text-xs mb-1 text-left hover:border-accent disabled:opacity-50"
                  style={{ padding: '7px 10px' }}
                >
                  {ACTION_ICON[a.action_type] ?? <Sparkles size={11} />}
                  <span className="flex-1 min-w-0 truncate">{a.label}</span>
                </button>
              ))
            )}

            {/* Meta do modelo */}
            <div style={{ ...labelSm, margin: '14px 0 6px' }}>Modelo</div>
            <div className="text-xs text-fg-2 leading-relaxed">
              {lastResponse.meta.model} · {lastResponse.meta.tokens} tokens ·{' '}
              {lastResponse.meta.validation_passed ? 'validado' : 'sem validação'}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
