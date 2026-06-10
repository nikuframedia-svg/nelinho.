/**
 * ApprovalButtons — Aceitar / Rejeitar / Modificar + campo "Porquê?".
 *
 * O campo "Porquê?" é o data point mais valioso do sistema (Plan v4 §4.1):
 * texto livre do gestor a explicar a decisão, gravado em
 * ScheduleCommit.user_reason, alimenta a Camada 1/2/3 de aprendizagem.
 *
 * `requireReason`:
 *   - 'always'    — campo SEMPRE visível, obrigatório aceitar/rejeitar com
 *   - 'on_reject' — campo aparece após clicar Rejeitar; obrigatório
 *   - 'never'     — campo opcional, visível mas não bloqueia
 *
 * Plan v4 §4.1 §7.3 / FRONTEND_DESIGN_PROMPT §5.2.
 * Sprint Q.18.UI.A.
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { Check, X, Edit3 } from 'lucide-react';

export type ReasonRequirement = 'always' | 'on_reject' | 'never';

export interface ApprovalButtonsProps {
  onAccept: (reason?: string) => void | Promise<void>;
  onReject: (reason: string) => void | Promise<void>;
  onModify?: () => void;
  requireReason?: ReasonRequirement;
  reasonPlaceholder?: string;
  acceptLabel?: string;
  rejectLabel?: string;
  modifyLabel?: string;
  /** Disabled while an action is in flight. */
  loading?: boolean;
  className?: string;
}

export function ApprovalButtons({
  onAccept,
  onReject,
  onModify,
  requireReason = 'on_reject',
  reasonPlaceholder = 'Porquê esta decisão? (ajuda o sistema a aprender)',
  acceptLabel = 'Aceitar',
  rejectLabel = 'Rejeitar',
  modifyLabel = 'Modificar',
  loading = false,
  className = '',
}: ApprovalButtonsProps): ReactNode {
  const [reason, setReason] = useState('');
  const [showRejectField, setShowRejectField] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reasonAlwaysVisible = requireReason === 'always';
  const reasonVisible = reasonAlwaysVisible || showRejectField;

  const handleAccept = async () => {
    if (loading) return;
    setError(null);
    if (reasonAlwaysVisible && reason.trim().length === 0) {
      setError('Indica a razão — é como o sistema aprende.');
      return;
    }
    await onAccept(reason.trim() || undefined);
    setReason('');
    setShowRejectField(false);
  };

  const handleReject = async () => {
    if (loading) return;
    setError(null);
    // Reject sempre exige razão (ou pelo menos 'on_reject' / 'always')
    if (requireReason !== 'never' && !showRejectField) {
      setShowRejectField(true);
      return;
    }
    if (requireReason !== 'never' && reason.trim().length < 3) {
      setError('Indica a razão (mínimo 3 caracteres) — é como o sistema aprende.');
      return;
    }
    await onReject(reason.trim());
    setReason('');
    setShowRejectField(false);
  };

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {reasonVisible ? (
        <div className="flex flex-col gap-1">
          <textarea
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              setError(null);
            }}
            placeholder={reasonPlaceholder}
            rows={2}
            className="
              w-full px-3 py-2 rounded-md
              bg-dark-700 border border-white/10
              text-sm text-text-dark-primary placeholder:text-text-dark-tertiary
              focus:outline-none focus:ring-2 focus:ring-accent-500/40 focus:border-accent-500/60
              resize-none
            "
            aria-label="Razão da decisão"
            disabled={loading}
          />
          {error ? (
            <span className="text-xs text-danger" role="alert">
              {error}
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="flex items-center gap-2 flex-wrap">
        <button
          type="button"
          onClick={handleAccept}
          disabled={loading}
          className="
            inline-flex items-center gap-1.5 px-4 py-2 rounded-md
            bg-success text-white text-sm font-semibold
            hover:bg-success-light disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors duration-150
            focus:outline-none focus:ring-2 focus:ring-success/40
          "
        >
          <Check className="w-4 h-4" />
          {acceptLabel}
        </button>

        <button
          type="button"
          onClick={handleReject}
          disabled={loading}
          className="
            inline-flex items-center gap-1.5 px-4 py-2 rounded-md
            bg-dark-700 text-text-dark-primary text-sm font-medium
            border border-danger/40 hover:bg-danger/10 hover:border-danger/60
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors duration-150
            focus:outline-none focus:ring-2 focus:ring-danger/40
          "
        >
          <X className="w-4 h-4 text-danger" />
          {rejectLabel}
        </button>

        {onModify ? (
          <button
            type="button"
            onClick={onModify}
            disabled={loading}
            className="
              inline-flex items-center gap-1.5 px-4 py-2 rounded-md
              bg-transparent text-text-dark-secondary text-sm font-medium
              border border-white/10 hover:bg-white/5 hover:text-text-dark-primary
              disabled:opacity-50 disabled:cursor-not-allowed
              transition-colors duration-150
              focus:outline-none focus:ring-2 focus:ring-white/20
            "
          >
            <Edit3 className="w-4 h-4" />
            {modifyLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}
