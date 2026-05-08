/**
 * TimelineSuggestion — o componente mais importante de toda a aplicação
 * (FRONTEND_DESIGN_PROMPT §4.1).
 *
 * Renderiza uma sugestão da timeline com 5 caixas:
 *   O QUE muda (delta)
 *   PORQUÊ o sistema propõe
 *   SE ACEITAR (consequências positivas/neutras)
 *   SE REJEITAR (consequências negativas)
 *   ALTERNATIVA (se existir)
 *
 * O utilizador pode Aceitar / Rejeitar / Modificar com campo "Porquê?".
 * O texto da razão alimenta `ScheduleCommit.user_reason` — Camada 3 DPO.
 *
 * Plan v4 §4.1 / FRONTEND_DESIGN_PROMPT §4.1 §5.2.
 * Sprint Q.18.UI.A.
 */

import type { ReactNode } from 'react';
import { Lightbulb, ArrowRight, AlertOctagon, ArrowDown } from 'lucide-react';
import { ConsequenceBlock, type ConsequenceLine } from './ConsequenceBlock';
import { ApprovalButtons } from './ApprovalButtons';

export type SuggestionPriority = 'critical' | 'high' | 'medium' | 'low';

export interface TimelineSuggestionAlternative {
  label: string;
  description: string;
  /** KPI deltas curtos: "tempo +2h", "throughput neutro". */
  trade_offs?: string[];
  onSelect?: (reason?: string) => void;
}

export interface TimelineSuggestionProps {
  id: number | string;
  priority: SuggestionPriority;
  title: string;
  /** O QUE muda — frase curta, ex: "Mover 3 K2 de terça para quarta". */
  what_changed?: string;
  /** PORQUÊ — frase curta, causa-efeito. */
  why: string;
  /** SE ACEITAR — lista de consequências (ConsequenceBlock format). */
  if_accept: ConsequenceLine[];
  /** SE REJEITAR — lista de consequências. */
  if_reject: ConsequenceLine[];
  alternatives?: TimelineSuggestionAlternative[];
  onAccept: (reason?: string) => void | Promise<void>;
  onReject: (reason: string) => void | Promise<void>;
  onModify?: () => void;
  /** Tag temporal — "há 2 min", "há 1h". */
  age_label?: string;
  className?: string;
}

const PRIORITY_BADGE: Record<SuggestionPriority, string> = {
  critical: 'bg-danger/20 text-danger border-danger/40',
  high: 'bg-orange-500/20 text-orange-300 border-orange-500/40',
  medium: 'bg-warning/20 text-warning border-warning/40',
  low: 'bg-primary-500/20 text-primary-300 border-primary-500/40',
};

const PRIORITY_LABEL: Record<SuggestionPriority, string> = {
  critical: 'Crítica',
  high: 'Alta',
  medium: 'Média',
  low: 'Baixa',
};

export function TimelineSuggestion({
  id,
  priority,
  title,
  what_changed,
  why,
  if_accept,
  if_reject,
  alternatives,
  onAccept,
  onReject,
  onModify,
  age_label,
  className = '',
}: TimelineSuggestionProps): ReactNode {
  return (
    <article
      className={`
        flex flex-col gap-4 p-5 rounded-xl
        bg-gradient-to-br from-dark-800 to-dark-700
        border border-white/[0.06] shadow-card
        ${className}
      `}
      aria-labelledby={`suggestion-title-${id}`}
    >
      {/* Header — id + priority + age */}
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-mono text-text-dark-tertiary tabular-nums">
            #{id}
          </span>
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide border ${PRIORITY_BADGE[priority]}`}
          >
            {PRIORITY_LABEL[priority]}
          </span>
        </div>
        {age_label ? (
          <span className="text-xs text-text-dark-tertiary tabular-nums">
            {age_label}
          </span>
        ) : null}
      </div>

      {/* Title */}
      <h3
        id={`suggestion-title-${id}`}
        className="text-base font-semibold text-text-dark-primary leading-snug"
      >
        {title}
      </h3>

      {/* O QUE — delta */}
      {what_changed ? (
        <div className="flex items-start gap-2 px-3 py-2 rounded-md bg-dark-900/40 border border-white/5">
          <ArrowRight className="w-4 h-4 shrink-0 mt-0.5 text-accent-400" />
          <p className="text-sm text-text-dark-primary">{what_changed}</p>
        </div>
      ) : null}

      {/* PORQUÊ */}
      <div className="flex items-start gap-2">
        <Lightbulb className="w-4 h-4 shrink-0 mt-0.5 text-warning" />
        <div className="min-w-0">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-text-dark-tertiary">
            Porquê
          </span>
          <p className="text-sm text-text-dark-secondary leading-snug">{why}</p>
        </div>
      </div>

      {/* SE ACEITAR / SE REJEITAR — duas colunas em desktop, stack em mobile */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <ConsequenceBlock title="Se aceitar" lines={if_accept} />
        <ConsequenceBlock title="Se rejeitar" lines={if_reject} />
      </div>

      {/* ALTERNATIVAS */}
      {alternatives && alternatives.length > 0 ? (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <ArrowDown className="w-4 h-4 text-primary-400" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-text-dark-tertiary">
              Alternativas ({alternatives.length})
            </span>
          </div>
          <div className="flex flex-col gap-2">
            {alternatives.map((alt, idx) => (
              <div
                key={`alt-${idx}`}
                className="px-3 py-2 rounded-md bg-dark-900/40 border border-primary-500/20"
              >
                <div className="flex items-start justify-between gap-2 flex-wrap">
                  <div className="flex flex-col gap-1 min-w-0 flex-1">
                    <span className="text-sm font-medium text-text-dark-primary">
                      {alt.label}
                    </span>
                    <span className="text-xs text-text-dark-secondary">
                      {alt.description}
                    </span>
                    {alt.trade_offs && alt.trade_offs.length > 0 ? (
                      <span className="text-xs text-text-dark-tertiary tabular-nums">
                        {alt.trade_offs.join(' · ')}
                      </span>
                    ) : null}
                  </div>
                  {alt.onSelect ? (
                    <button
                      type="button"
                      onClick={() => alt.onSelect?.()}
                      className="
                        shrink-0 px-3 py-1 rounded-md text-xs font-medium
                        bg-primary-500 text-white hover:bg-primary-400
                        transition-colors
                      "
                    >
                      Aceitar alternativa
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Critical alert */}
      {priority === 'critical' ? (
        <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-danger/10 border border-danger/30">
          <AlertOctagon className="w-4 h-4 text-danger shrink-0" />
          <span className="text-xs text-danger font-medium">
            Decisão crítica — escolha não pode ser adiada.
          </span>
        </div>
      ) : null}

      {/* Approval buttons */}
      <ApprovalButtons
        onAccept={onAccept}
        onReject={onReject}
        onModify={onModify}
        requireReason="on_reject"
      />
    </article>
  );
}
