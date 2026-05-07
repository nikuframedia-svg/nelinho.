/**
 * RejectionReasonInput — Plan v4 §4 (advisory mode) + §11 (learning loop).
 *
 * When the user rejects a suggestion we REQUIRE a reason of at least
 * `REJECTION_REASON_MIN_LENGTH` characters. Plan v4 §11 explicitly
 * names this as the highest-value learning signal in the whole system:
 * a rejection without "porquê" is wasted data. The component owns the
 * validation visually so consumers can disable their submit button via
 * `onValidChange`.
 *
 * Acceptance reasons stay free-form (optional) — users shouldn't be
 * gated when they agree with the system.
 */

import { useEffect, useId, useMemo, useState } from 'react';
import { MessageSquareWarning } from 'lucide-react';
import { REJECTION_REASON_MIN_LENGTH } from '../../types/decision';

export interface RejectionReasonInputProps {
  value: string;
  onChange: (value: string) => void;
  /** Fires whenever `value.trim().length >= minLength` toggles. */
  onValidChange?: (isValid: boolean) => void;
  /** Override the minimum-length gate. Defaults to 8 chars (Plan v4). */
  minLength?: number;
  placeholder?: string;
  /** Visually mark validation errors only after the user has interacted. */
  showErrorOnBlurOnly?: boolean;
  disabled?: boolean;
  className?: string;
}

export function RejectionReasonInput({
  value,
  onChange,
  onValidChange,
  minLength = REJECTION_REASON_MIN_LENGTH,
  placeholder = 'Porquê esta rejeição? (ajuda o sistema a aprender)',
  showErrorOnBlurOnly = true,
  disabled = false,
  className = '',
}: RejectionReasonInputProps) {
  const id = useId();
  const [touched, setTouched] = useState(false);

  const trimmedLength = value.trim().length;
  const isValid = trimmedLength >= minLength;
  const remaining = Math.max(0, minLength - trimmedLength);
  const showError = !isValid && (touched || !showErrorOnBlurOnly);

  useEffect(() => {
    onValidChange?.(isValid);
  }, [isValid, onValidChange]);

  const helper = useMemo(() => {
    if (isValid) {
      return (
        <span className="text-emerald-300">
          Razão registada — vai alimentar a aprendizagem do sistema.
        </span>
      );
    }
    if (trimmedLength === 0) {
      return (
        <span className="text-slate-400">
          Mínimo {minLength} caracteres. A razão é obrigatória para rejeitar.
        </span>
      );
    }
    return (
      <span className={showError ? 'text-rose-300' : 'text-slate-400'}>
        Faltam {remaining} {remaining === 1 ? 'carácter' : 'caracteres'}.
      </span>
    );
  }, [isValid, trimmedLength, minLength, remaining, showError]);

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <label
        htmlFor={id}
        className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-rose-200"
      >
        <MessageSquareWarning className="w-3.5 h-3.5" />
        Razão da rejeição
      </label>
      <textarea
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onBlur={() => setTouched(true)}
        placeholder={placeholder}
        disabled={disabled}
        rows={3}
        className={`w-full rounded-md border bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-rose-500/40 disabled:opacity-60 ${
          showError ? 'border-rose-500/60' : 'border-slate-700/70'
        }`}
        aria-invalid={showError}
        aria-describedby={`${id}-helper`}
      />
      <p id={`${id}-helper`} className="text-[11px]">
        {helper}
      </p>
    </div>
  );
}
