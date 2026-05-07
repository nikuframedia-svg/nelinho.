/**
 * SuggestionCard — Plan v4 §4 + §8 canonical suggestion shell.
 *
 * One card per pending suggestion in any list (Inbox, Scheduling
 * timeline, Dispatch sugestões, Expedição, Operadores). It binds:
 *   - title + priority chip + ConfidenceBadge
 *   - WHY block (PORQUÊ visible at all times — never collapsed)
 *   - SuggestionExplainer (5 blocks: O QUE / PORQUÊ / SE ACEITAR /
 *     SE REJEITAR / ALTERNATIVA)
 *   - Optional ConsequenceBlock for KPI-shaped impact lines
 *   - Aceitar / Rejeitar / Modificar buttons
 *   - Mandatory RejectionReasonInput when the user picks Rejeitar
 *
 * Accept fires immediately (with optional reason). Reject is a two-step
 * flow: clicking the button reveals the textarea and the second click
 * is gated until ≥8 chars are typed.
 */

import { useState } from 'react';
import { Check, Pencil, X, ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  ConsequenceBlock,
  type ConsequenceLine,
  SuggestionExplainer,
} from '../dark';
import type { Suggestion, SuggestionPriority } from '../../types/decision';
import { ConfidenceBadge } from './ConfidenceBadge';
import { RejectionReasonInput } from './RejectionReasonInput';

export interface SuggestionCardProps {
  suggestion: Suggestion;
  /** Optional KPI-shaped consequence rows (€/h/etc). Renders below explainer. */
  consequenceLines?: ConsequenceLine[];
  onAccept: (reason?: string) => void | Promise<void>;
  onReject: (reason: string) => void | Promise<void>;
  onModify?: () => void;
  /** Disable buttons (e.g. mutation in flight). */
  busy?: boolean;
  className?: string;
}

const PRIORITY_CHIP: Record<SuggestionPriority, { label: string; cls: string }> = {
  critical: { label: 'CRÍTICA', cls: 'bg-rose-500/20 text-rose-100 border-rose-500/40' },
  high: { label: 'ALTA', cls: 'bg-amber-500/20 text-amber-100 border-amber-500/40' },
  medium: { label: 'MÉDIA', cls: 'bg-sky-500/20 text-sky-100 border-sky-500/40' },
  low: { label: 'BAIXA', cls: 'bg-slate-700/40 text-slate-200 border-slate-600/60' },
};

function joinLines(value: string | string[] | undefined): string {
  if (!value) return '';
  return Array.isArray(value) ? value.join('\n') : value;
}

export function SuggestionCard({
  suggestion,
  consequenceLines,
  onAccept,
  onReject,
  onModify,
  busy = false,
  className = '',
}: SuggestionCardProps) {
  const [acceptReason, setAcceptReason] = useState('');
  const [rejectMode, setRejectMode] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [rejectValid, setRejectValid] = useState(false);

  const chip = PRIORITY_CHIP[suggestion.priority] ?? PRIORITY_CHIP.medium;
  const ifAccept = joinLines(suggestion.if_accept);
  const ifReject = joinLines(suggestion.if_reject);
  const what = suggestion.what_changed ?? suggestion.title;
  const altText = suggestion.alternative
    ? [suggestion.alternative.label, ...(suggestion.alternative.consequences ?? [])]
        .filter(Boolean)
        .join(' — ')
    : null;

  return (
    <article
      data-suggestion-id={suggestion.id}
      className={`rounded-xl border border-slate-700/60 bg-slate-900/70 p-4 shadow-sm flex flex-col gap-4 ${className}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${chip.cls}`}
            >
              {chip.label}
            </span>
            <span className="text-[11px] text-slate-400 font-mono">
              #{suggestion.id.slice(0, 8)}
            </span>
            <span className="text-[11px] text-slate-500 uppercase tracking-wider">
              {suggestion.source}
            </span>
          </div>
          <h3 className="text-base font-semibold text-slate-100 leading-tight">
            {suggestion.title}
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <ConfidenceBadge value={suggestion.confidence} />
          {suggestion.context_url ? (
            <Link
              to={suggestion.context_url}
              className="inline-flex items-center gap-1 text-xs text-sky-300 hover:text-sky-200"
            >
              Ver contexto <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          ) : null}
        </div>
      </header>

      <SuggestionExplainer
        what={what}
        why={suggestion.why}
        ifAccept={ifAccept || '—'}
        ifReject={ifReject || '—'}
        alternative={altText}
      />

      {consequenceLines && consequenceLines.length > 0 ? (
        <ConsequenceBlock lines={consequenceLines} />
      ) : null}

      {!rejectMode ? (
        <div className="flex flex-col gap-2">
          <label className="text-[11px] uppercase tracking-wider text-slate-400">
            Porquê esta decisão? <span className="text-slate-600">(opcional ao aceitar)</span>
          </label>
          <textarea
            value={acceptReason}
            onChange={(e) => setAcceptReason(e.target.value)}
            placeholder="Razão para aceitar (opcional, ajuda o sistema a aprender)"
            rows={2}
            disabled={busy}
            className="w-full rounded-md border border-slate-700/70 bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:opacity-60"
          />
        </div>
      ) : (
        <RejectionReasonInput
          value={rejectReason}
          onChange={setRejectReason}
          onValidChange={setRejectValid}
          disabled={busy}
        />
      )}

      <footer className="flex flex-wrap items-center justify-end gap-2 pt-1 border-t border-slate-800">
        {!rejectMode ? (
          <>
            {onModify ? (
              <button
                type="button"
                onClick={onModify}
                disabled={busy}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
              >
                <Pencil className="w-3.5 h-3.5" /> Modificar
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => setRejectMode(true)}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/40 bg-rose-500/10 px-3 py-1.5 text-sm text-rose-100 hover:bg-rose-500/20 disabled:opacity-50"
            >
              <X className="w-3.5 h-3.5" /> Rejeitar
            </button>
            <button
              type="button"
              onClick={() => onAccept(acceptReason.trim() || undefined)}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/40 bg-emerald-500/15 px-3 py-1.5 text-sm font-semibold text-emerald-100 hover:bg-emerald-500/25 disabled:opacity-50"
            >
              <Check className="w-3.5 h-3.5" /> Aceitar
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => {
                setRejectMode(false);
                setRejectReason('');
              }}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => onReject(rejectReason.trim())}
              disabled={busy || !rejectValid}
              className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/40 bg-rose-500/20 px-3 py-1.5 text-sm font-semibold text-rose-100 hover:bg-rose-500/30 disabled:opacity-40"
            >
              <X className="w-3.5 h-3.5" /> Confirmar rejeição
            </button>
          </>
        )}
      </footer>
    </article>
  );
}
