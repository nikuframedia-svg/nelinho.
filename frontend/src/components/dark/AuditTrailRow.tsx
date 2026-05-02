/**
 * AuditTrailRow — Plan v4 §11.2 contract.
 *
 * Renders the "who / when / why" provenance metadata for any
 * configurable value. Plan §11.2 mandates that EVERY config key
 * shows: current value, who set it, when, why, default value, reset
 * button. This component is the row-level dialect — embed it under
 * a key/value pair in `ConfigKeysPanel`.
 *
 * The value-vs-default tooltip is rendered as the title attribute so
 * keyboard navigation surfaces it without an extra portal. Hover on
 * the dot to see the default; click "↺ default" to reset.
 *
 * Sprint Q.9 Onda 3.1.
 */

import type { ReactNode } from 'react';
import { Clock, RotateCcw, User2 } from 'lucide-react';

export interface AuditTrailRowProps {
  lastChangedBy?: string | null;
  lastChangedAt?: string | Date | null;
  reason?: string | null;
  /** The default value as the codebase ships it (for reset + tooltip). */
  defaultValue?: ReactNode;
  /** True when the current value differs from the default. */
  isOverridden?: boolean;
  /** Reset-to-default handler. When omitted, no button renders. */
  onReset?: () => void;
  className?: string;
}

function _formatTime(value: string | Date | null | undefined): string | null {
  if (!value) return null;
  const d = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(d.getTime())) return null;
  // pt-PT short form: "26/04 às 14:32" — terse enough for a row, easy
  // to extend later with `Intl.RelativeTimeFormat` if requested.
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const min = String(d.getMinutes()).padStart(2, '0');
  return `${dd}/${mm} às ${hh}:${min}`;
}

export function AuditTrailRow({
  lastChangedBy,
  lastChangedAt,
  reason,
  defaultValue,
  isOverridden,
  onReset,
  className = '',
}: AuditTrailRowProps) {
  const formatted = _formatTime(lastChangedAt);
  const showProvenance = lastChangedBy || formatted || reason;

  return (
    <div
      className={`flex items-center justify-between gap-3 text-[11px] text-slate-400 ${className}`}
    >
      <div className="flex items-center gap-3 flex-wrap">
        {showProvenance ? (
          <>
            {lastChangedBy ? (
              <span className="inline-flex items-center gap-1">
                <User2 className="w-3 h-3 opacity-80" />
                <span className="text-slate-300">{lastChangedBy}</span>
              </span>
            ) : null}
            {formatted ? (
              <span className="inline-flex items-center gap-1">
                <Clock className="w-3 h-3 opacity-80" />
                <span>{formatted}</span>
              </span>
            ) : null}
            {reason ? (
              <span
                className="italic max-w-[26ch] truncate"
                title={reason}
              >
                "{reason}"
              </span>
            ) : null}
          </>
        ) : (
          <span className="italic opacity-70">por definir · sem alterações</span>
        )}
      </div>

      <div className="flex items-center gap-2 shrink-0">
        {defaultValue !== undefined && defaultValue !== null ? (
          <span
            className={`inline-flex items-center gap-1 ${
              isOverridden ? 'text-amber-300' : 'opacity-70'
            }`}
            title={
              isOverridden
                ? `Default: ${String(defaultValue)} (override activo)`
                : `Default: ${String(defaultValue)}`
            }
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isOverridden ? 'bg-amber-400' : 'bg-slate-500'
              }`}
            />
            <span>default {String(defaultValue)}</span>
          </span>
        ) : null}

        {onReset ? (
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded border border-slate-700/60 hover:border-slate-500 hover:text-slate-200 transition-colors"
            title="Repor default"
          >
            <RotateCcw className="w-3 h-3" />
            default
          </button>
        ) : null}
      </div>
    </div>
  );
}
