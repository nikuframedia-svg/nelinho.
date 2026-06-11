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

import { useState } from 'react';
import type { ReactNode } from 'react';
import { FileText, AlertTriangle, Check, Play, ExternalLink, ThumbsUp, ThumbsDown, Info, ChevronDown, ChevronRight } from 'lucide-react';
import { copilotApi } from '../../lib/api/copilotApi';
import { DarkBadge } from '../dark';
import { Clickable } from '../entitySheets';
import type { CopilotResponse, CubeExplicacao } from '../../lib/copilot-types';
import { CopilotChart } from './CopilotChart';
import type { ChatMessage, CopilotResponseWithCharts } from './copilotPageHelpers';
import { WARNING_LABELS } from './copilotPageHelpers';

// ─── Parser: converte "[kind:id]" em Clickable ─────────────────────────────────

function renderWithClickables(text: string): ReactNode[] {
  const re = /\[(modelo|fase|cliente|encomenda):([^\]]+)\]/g;
  const out: ReactNode[] = [];
  let lastIndex = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIndex) out.push(text.slice(lastIndex, m.index));
    const kind = m[1] as 'modelo' | 'fase' | 'cliente' | 'encomenda';
    const id = m[2];
    out.push(<Clickable key={`c-${key++}`} kind={kind} id={id}>{id}</Clickable>);
    lastIndex = re.lastIndex;
  }
  if (lastIndex < text.length) out.push(text.slice(lastIndex));
  return out;
}

// ── Q.173.AL — "Como cheguei a isto" (só para respostas Cube) ─────────────────

function CubeExplicacaoPanel({ exp }: { exp: CubeExplicacao }): ReactNode {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-md border border-bd-1 bg-bg-2 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-bg-3 transition-colors"
      >
        <Info size={11} className="text-fg-3 shrink-0" />
        <span className="flex-1 text-xs text-fg-2 font-medium">Como cheguei a isto</span>
        {open ? (
          <ChevronDown size={11} className="text-fg-3" />
        ) : (
          <ChevronRight size={11} className="text-fg-3" />
        )}
      </button>
      {open && (
        <div className="px-3 pb-3 flex flex-col gap-2 border-t border-bd-1 pt-2">
          {/* Tabela de origem */}
          {exp.tabela && (
            <div>
              <span className="text-[10px] uppercase tracking-wide text-fg-3 font-semibold">Tabela</span>
              <p className="font-mono text-xs text-fg-1 mt-0.5">{exp.tabela}</p>
            </div>
          )}

          {/* Measures com fórmula SQL */}
          {exp.measures.length > 0 && (
            <div>
              <span className="text-[10px] uppercase tracking-wide text-fg-3 font-semibold">
                Medida{exp.measures.length > 1 ? 's' : ''} ({exp.measures.length})
              </span>
              <div className="flex flex-col gap-1 mt-0.5">
                {exp.measures.map((m) => (
                  <div key={m.nome} className="rounded bg-bg-3 border border-bd-1 px-2 py-1.5">
                    <p className="text-[10px] text-fg-3 mb-0.5">{m.nome}</p>
                    <button
                      type="button"
                      title="Copiar fórmula"
                      onClick={() => navigator.clipboard.writeText(m.formula_sql).catch(() => {})}
                      className="w-full text-left font-mono text-xs text-fg-1 hover:text-accent transition-colors"
                    >
                      {m.formula_sql}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Filtros */}
          {exp.filtros.length > 0 && (
            <div>
              <span className="text-[10px] uppercase tracking-wide text-fg-3 font-semibold">Filtros</span>
              <div className="flex flex-wrap gap-1 mt-0.5">
                {exp.filtros.map((f, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center rounded px-1.5 py-0.5 bg-bg-3 border border-bd-1 font-mono text-fg-2"
                    style={{ fontSize: 9.5 }}
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Período */}
          {exp.periodo && (
            <div>
              <span className="text-[10px] uppercase tracking-wide text-fg-3 font-semibold">Período</span>
              <p className="text-xs text-fg-1 mt-0.5">{exp.periodo}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

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
  response: CopilotResponseWithCharts;
  onAction: (action: CopilotResponse['actions'][number]) => void;
  actionPending: boolean;
}): ReactNode {
  const charts = response?.charts ?? [];
  const facts = response?.facts ?? [];
  const actions = response?.actions ?? [];
  const warnings = response?.warnings ?? [];
  return (
    <div className="mt-2 flex flex-col gap-3">
      {/* Factos com citações */}
      {facts.length > 0 && (
        <div className="flex flex-col gap-2">
          {facts.map((fact, i) => (
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

      {/* Gráficos gerados pelo copiloto (Q.53.L) */}
      {charts.length > 0 && (
        <div className="flex flex-col gap-2">
          {charts.map((chart, i) => (
            <CopilotChart key={i} spec={chart} />
          ))}
        </div>
      )}

      {/* Cartões de acção */}
      {actions.length > 0 && (
        <div className="flex flex-col gap-2">
          {actions.map((a, i) => (
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
      {warnings.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {warnings.map((w, i) => (
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

      {/* Q.173.AL — "Como cheguei a isto": só para respostas Cube com explicacao */}
      {response.explicacao && (
        <CubeExplicacaoPanel exp={response.explicacao} />
      )}
    </div>
  );
}

export interface CopilotChatMessageProps {
  message: ChatMessage;
  onAction: (action: CopilotResponse['actions'][number]) => void;
  actionPending: boolean;
}

// ─── 👍/👎 — fecha o loop de aprendizagem (Q.172.E; backend Q.31.H/Q.171.F) ────

function FeedbackThumbs({ response }: { response: CopilotResponseWithCharts }): ReactNode {
  const [sent, setSent] = useState<'up' | 'down' | null>(null);
  const send = (thumb: 'up' | 'down') => {
    if (sent) return;
    setSent(thumb);
    // best-effort: o feedback nunca pode partir o chat; falha fica no log.
    copilotApi
      .sendUserFeedback(thumb, {
        suggestion_id: response.suggestion_id,
        type: response.type,
        model: response.meta?.model ?? null,
      })
      .catch((err) => console.error('feedback do copiloto falhou', err));
  };
  return (
    <span className="inline-flex items-center gap-1">
      <button
        type="button"
        aria-label="Resposta útil"
        title="Resposta útil"
        onClick={() => send('up')}
        disabled={sent !== null}
        style={{
          color: sent === 'up' ? 'var(--ok)' : 'var(--fg-3)',
          opacity: sent && sent !== 'up' ? 0.35 : 1,
          cursor: sent ? 'default' : 'pointer',
        }}
      >
        <ThumbsUp size={11} />
      </button>
      <button
        type="button"
        aria-label="Resposta não ajudou"
        title="Resposta não ajudou"
        onClick={() => send('down')}
        disabled={sent !== null}
        style={{
          color: sent === 'down' ? 'var(--danger)' : 'var(--fg-3)',
          opacity: sent && sent !== 'down' ? 0.35 : 1,
          cursor: sent ? 'default' : 'pointer',
        }}
      >
        <ThumbsDown size={11} />
      </button>
      {sent && <span style={{ fontSize: 10 }}>obrigado</span>}
    </span>
  );
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
          renderWithClickables(message.text)
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
              <span>{r.meta?.model}</span>
              {(r.meta?.latency_ms ?? 0) > 0 && (
                <>
                  <span>·</span>
                  <span>{(r.meta.latency_ms / 1000).toFixed(1)}s</span>
                </>
              )}
              {r.type === 'ERROR' && <DarkBadge variant="danger">erro</DarkBadge>}
              {r.type !== 'ERROR' && r.suggestion_id && (
                <>
                  <span>·</span>
                  <FeedbackThumbs response={r} />
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
