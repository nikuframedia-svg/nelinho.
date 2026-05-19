/**
 * CopilotChatMessage — uma mensagem do chat fullscreen (Q.52.N).
 *
 * Port do bloco de mensagem do protótipo NELO (page-copilot.jsx),
 * ligado à resposta REAL do `POST /api/copilot/ask` (CopilotResponse):
 *   - bolha do utilizador (accent, alinhada à direita)
 *   - bolha do copiloto: sumário + factos com citações + cartões de
 *     acção + avisos honestos (modelo offline, baixa confiança…)
 *
 * As acções vêm de `response.actions` — cada uma com `requires_approval`
 * e `payload`. "Aplicar" invoca o callback `onAction` (que chama
 * `POST /api/copilot/action`).
 */

import type { ReactNode } from 'react';
import { FileText, AlertTriangle, Check, Play, ExternalLink } from 'lucide-react';
import { DarkBadge } from '../dark';
import type { CopilotResponse } from '../../lib/copilot-types';
import type { ChatMessage } from './copilotPageHelpers';
import { WARNING_LABELS } from './copilotPageHelpers';

const ACTION_ICON: Record<string, ReactNode> = {
  CREATE_DECISION_PR: <Check size={12} />,
  DRY_RUN: <Play size={12} />,
  OPEN_ENTITY: <ExternalLink size={12} />,
  RUN_RUNBOOK: <Play size={12} />,
};

function ResponseBody({
  response,
  onAction,
  actionPending,
}: {
  response: CopilotResponse;
  onAction: (action: CopilotResponse['actions'][number]) => void;
  actionPending: boolean;
}): ReactNode {
  return (
    <div className="mt-2 flex flex-col gap-3">
      {/* Factos com citações */}
      {response.facts.length > 0 && (
        <div className="flex flex-col gap-2">
          {response.facts.map((fact, i) => (
            <div
              key={i}
              className="rounded-md border border-bd-1 bg-bg-2 px-3 py-2"
            >
              <p className="text-xs text-fg-1 leading-relaxed">{fact.text}</p>
              {fact.citations.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {fact.citations.map((c, j) => (
                    <span
                      key={j}
                      className="inline-flex items-center gap-1 font-mono text-fg-3 bg-bg-3 border border-bd-1 rounded px-1.5 py-0.5"
                      style={{ fontSize: 9.5 }}
                      title={`${c.source_type} · confiança ${(c.confidence * 100).toFixed(0)}% · trust ${(c.trust_index * 100).toFixed(0)}%`}
                    >
                      <FileText size={9} />
                      {c.label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Cartões de acção */}
      {response.actions.length > 0 && (
        <div className="flex flex-col gap-2">
          {response.actions.map((a, i) => (
            <div
              key={i}
              className="rounded-md border border-bd-2 bg-bg-2 px-3 py-2.5 flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <p className="text-xs font-medium text-fg-0">{a.label}</p>
                <p className="text-[10px] text-fg-3 mt-0.5">
                  {a.requires_approval
                    ? 'Requer aprovação humana antes de executar'
                    : 'Pode correr directamente'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onAction(a)}
                disabled={actionPending}
                className="shrink-0 inline-flex items-center gap-1.5 rounded-md border border-bd-2 bg-bg-3 px-2.5 py-1.5 text-xs text-fg-1 hover:border-accent disabled:opacity-50"
              >
                {ACTION_ICON[a.action_type] ?? <Play size={12} />}
                {a.requires_approval ? 'Propor' : 'Correr'}
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Avisos honestos */}
      {response.warnings.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {response.warnings.map((w, i) => (
            <div
              key={i}
              className="rounded-md border border-yellow-bd bg-yellow-bg px-3 py-2 flex items-start gap-2"
            >
              <AlertTriangle size={12} className="text-yellow mt-0.5 shrink-0" />
              <div className="text-xs text-fg-1">
                <span className="font-medium text-yellow">
                  {WARNING_LABELS[w.code] ?? w.code}
                </span>
                {' — '}
                {w.message}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export interface CopilotChatMessageProps {
  message: ChatMessage;
  onAction: (action: CopilotResponse['actions'][number]) => void;
  actionPending: boolean;
}

export function CopilotChatMessage({
  message,
  onAction,
  actionPending,
}: CopilotChatMessageProps): ReactNode {
  const isUser = message.role === 'user';
  const r = message.response;

  return (
    <div
      className="anim-up"
      style={{
        alignSelf: isUser ? 'flex-end' : 'flex-start',
        maxWidth: '82%',
      }}
    >
      {/* Bolha de texto */}
      <div
        style={{
          padding: '10px 14px',
          background: isUser ? 'var(--accent)' : 'var(--bg-2)',
          color: isUser ? '#fff' : 'var(--fg-0)',
          border: isUser ? 'none' : '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          borderBottomRightRadius: isUser ? 4 : 'var(--r-lg)',
          borderBottomLeftRadius: isUser ? 'var(--r-lg)' : 4,
          fontSize: 13,
          lineHeight: 1.55,
        }}
      >
        {message.typing ? (
          <span className="pulse-dot" style={{ letterSpacing: 2 }}>
            ● ● ●
          </span>
        ) : (
          message.text
        )}
      </div>

      {/* Resposta rica do copiloto */}
      {r && !message.typing && (
        <ResponseBody response={r} onAction={onAction} actionPending={actionPending} />
      )}

      {/* Meta */}
      {!message.typing && (
        <div
          className="flex items-center gap-2 mt-1"
          style={{
            fontSize: 10,
            color: 'var(--fg-3)',
            justifyContent: isUser ? 'flex-end' : 'flex-start',
          }}
        >
          <span>{message.when}</span>
          {r && (
            <>
              <span>·</span>
              <span>{r.meta.model}</span>
              {r.meta.latency_ms > 0 && (
                <>
                  <span>·</span>
                  <span>{(r.meta.latency_ms / 1000).toFixed(1)}s</span>
                </>
              )}
              {r.type === 'ERROR' && <DarkBadge variant="danger">erro</DarkBadge>}
            </>
          )}
        </div>
      )}
    </div>
  );
}
