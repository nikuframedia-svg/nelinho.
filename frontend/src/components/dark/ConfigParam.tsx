/**
 * ConfigParam — Plan v4 §4.7 (CONFIGURAÇÃO) editable parameter row.
 *
 * Cada parâmetro de configuração editável renderiza-se com este
 * componente. Mostra valor actual + default + proveniência (badge
 * source: default/manual/learned_rule), permite editar inline com
 * razão obrigatória (≥10 chars), e dois botões cirúrgicos:
 *
 *   - "Reset para default"     → POST /v1/config/{cat}/{key}/reset-to-default
 *   - "Aceitar regra aprendida" → opcional; só aparece se houver
 *                                  `learnedRuleHint` (regra Camada 1
 *                                  detectada que sugere outro valor)
 *
 * O valor preferido é mostrado como ConsequenceBlock (reuso do dark/)
 * com 3 linhas: actual / default / hint, cada uma com a sua severity
 * tone para o gestor ver de relance se está em default ou desviado.
 *
 * Props alinhados com FRONTEND_DESIGN_PROMPT §4.7. Sprint X.2.
 */

import { useId, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Pencil,
  RotateCcw,
  Save,
  Sparkles,
  X,
} from 'lucide-react';
import { ConsequenceBlock, type ConsequenceLine } from './ConsequenceBlock';
import { DarkBadge } from './DarkBadge';
import { DarkButton } from './DarkButton';
import { DarkInput } from './DarkInput';
import { DarkSelect } from './DarkSelect';
import type { ConfigSource } from '../../lib/api';

const REASON_MIN = 10;

export type ConfigParamType = 'number' | 'text' | 'boolean' | 'select';

export interface ConfigParamProps {
  /** Fully qualified config key, e.g. "scheduling.fitness.w_tardiness". */
  configKey: string;
  /** Human-readable label in pt-PT, e.g. "Peso do atraso de transporte". */
  label: string;
  /** Short description shown under the label. */
  description: string;
  /** Current persisted value. */
  value: number | string | boolean;
  /** Seeded default — used by ConsequenceBlock and the Reset button. */
  defaultValue: number | string | boolean;
  /** Renders as appropriate input. */
  type: ConfigParamType;
  /** Numeric range (only when type === 'number'). */
  range?: { min: number; max: number; step: number };
  /** Options (only when type === 'select'). */
  options?: { value: string; label: string }[];
  /** Provenance badge source. From ConfigEntry.source. */
  source: ConfigSource;
  /** Optional last-modified-by display label (already resolved name). */
  lastChangedBy?: string;
  /** ISO timestamp of last write. */
  lastChangedAt?: string;
  /** When set, renders the "Aceitar regra aprendida" button. */
  learnedRuleHint?: {
    suggestedValue: number | string | boolean;
    confidence: number;
    description: string;
  };
  /** Persist a new value with a ≥10-char reason. */
  onSave: (
    nextValue: number | string | boolean,
    reason: string,
  ) => Promise<void>;
  /** Restore the seeded default (server-side reset-to-default endpoint). */
  onReset: () => Promise<void>;
  /** Apply the suggested value from the learned rule. */
  onAcceptLearnedRule?: (reason: string) => Promise<void>;
  className?: string;
}

const SOURCE_BADGE: Record<ConfigSource, { label: string; tone: 'success' | 'warning' | 'info' | 'neutral' }> = {
  default: { label: 'System default', tone: 'neutral' },
  manual: { label: 'Override manual', tone: 'warning' },
  learned_rule: { label: 'Regra aprendida', tone: 'info' },
};

function fmtValue(v: number | string | boolean): string {
  if (typeof v === 'boolean') return v ? 'sim' : 'não';
  if (typeof v === 'number') return v.toFixed(3).replace(/\.?0+$/, '');
  return String(v);
}

function fmtDate(iso?: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('pt-PT', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function valuesEqual(a: number | string | boolean, b: number | string | boolean): boolean {
  if (typeof a === 'number' && typeof b === 'number') {
    return Math.abs(a - b) < 1e-9;
  }
  return String(a) === String(b);
}

export function ConfigParam({
  configKey,
  label,
  description,
  value,
  defaultValue,
  type,
  range,
  options,
  source,
  lastChangedBy,
  lastChangedAt,
  learnedRuleHint,
  onSave,
  onReset,
  onAcceptLearnedRule,
  className = '',
}: ConfigParamProps) {
  const reasonId = useId();
  const valueId = useId();
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState<string>(String(value));
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hintReason, setHintReason] = useState('');
  const [hintMode, setHintMode] = useState(false);

  const sourceBadge = SOURCE_BADGE[source];
  const isDeviated = !valuesEqual(value, defaultValue);
  const reasonValid = reason.trim().length >= REASON_MIN;
  const hintReasonValid = hintReason.trim().length >= REASON_MIN;

  const consequenceLines: ConsequenceLine[] = [
    {
      label: 'Actual',
      value: fmtValue(value),
      severity: source === 'manual' ? 'warning' : source === 'learned_rule' ? 'info' : 'info',
    },
    {
      label: 'Default',
      value: fmtValue(defaultValue),
      severity: 'info',
      detail: isDeviated ? 'Valor seedado pelo sistema' : '✓ Igual ao actual',
    },
  ];
  if (learnedRuleHint) {
    consequenceLines.push({
      label: 'Regra aprendida',
      value: fmtValue(learnedRuleHint.suggestedValue),
      severity: 'positive',
      detail: `${learnedRuleHint.description} · confiança ${(
        learnedRuleHint.confidence * 100
      ).toFixed(0)}%`,
    });
  }

  function parseEditValue(): number | string | boolean | null {
    if (type === 'number') {
      const n = Number(editValue);
      if (!Number.isFinite(n)) return null;
      if (range && (n < range.min || n > range.max)) return null;
      return n;
    }
    if (type === 'boolean') {
      return editValue === 'true' || editValue === 'sim';
    }
    return editValue;
  }

  async function handleSave() {
    const next = parseEditValue();
    if (next === null) {
      setError('Valor inválido para este parâmetro.');
      return;
    }
    if (!reasonValid) {
      setError(`Razão precisa de pelo menos ${REASON_MIN} caracteres.`);
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await onSave(next, reason.trim());
      setEditing(false);
      setReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleReset() {
    setBusy(true);
    setError(null);
    try {
      await onReset();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleAcceptHint() {
    if (!onAcceptLearnedRule || !hintReasonValid) return;
    setBusy(true);
    setError(null);
    try {
      await onAcceptLearnedRule(hintReason.trim());
      setHintMode(false);
      setHintReason('');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      data-config-key={configKey}
      className={`rounded-xl border border-slate-700/60 bg-slate-900/60 p-4 flex flex-col gap-3 ${className}`}
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="font-semibold text-slate-100">{label}</h4>
            <DarkBadge variant={sourceBadge.tone}>{sourceBadge.label}</DarkBadge>
            {isDeviated ? (
              <span className="text-[11px] text-amber-300 inline-flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> diverge do default
              </span>
            ) : (
              <span className="text-[11px] text-emerald-300 inline-flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> em default
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400">{description}</p>
          <p className="text-[10px] font-mono text-slate-600">{configKey}</p>
        </div>
      </header>

      <ConsequenceBlock title="" lines={consequenceLines} />

      <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-500">
        <span>
          Última alteração: <span className="text-slate-300">{fmtDate(lastChangedAt)}</span>
          {lastChangedBy ? (
            <span className="text-slate-300"> · por {lastChangedBy}</span>
          ) : null}
        </span>
      </div>

      {!editing && !hintMode ? (
        <div className="flex flex-wrap items-center justify-end gap-2 pt-1 border-t border-slate-800">
          {learnedRuleHint && onAcceptLearnedRule ? (
            <DarkButton variant="secondary" onClick={() => setHintMode(true)}>
              <Sparkles className="w-3.5 h-3.5" /> Aceitar regra aprendida
            </DarkButton>
          ) : null}
          {isDeviated ? (
            <DarkButton variant="secondary" onClick={handleReset} disabled={busy}>
              {busy ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <RotateCcw className="w-3.5 h-3.5" />
              )}
              Reset para default
            </DarkButton>
          ) : null}
          <DarkButton variant="primary" onClick={() => setEditing(true)} disabled={busy}>
            <Pencil className="w-3.5 h-3.5" /> Editar
          </DarkButton>
        </div>
      ) : null}

      {editing ? (
        <div className="flex flex-col gap-2 pt-2 border-t border-slate-800">
          <label
            htmlFor={valueId}
            className="text-[11px] uppercase tracking-wider text-slate-400"
          >
            Novo valor
          </label>
          {type === 'number' ? (
            <DarkInput
              id={valueId}
              type="number"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              min={range?.min}
              max={range?.max}
              step={range?.step}
              disabled={busy}
            />
          ) : type === 'boolean' ? (
            <DarkSelect
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              options={[
                { value: 'true', label: 'Sim (true)' },
                { value: 'false', label: 'Não (false)' },
              ]}
            />
          ) : type === 'select' ? (
            <DarkSelect
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              options={options ?? []}
            />
          ) : (
            <DarkInput
              id={valueId}
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              disabled={busy}
            />
          )}
          <label
            htmlFor={reasonId}
            className="text-[11px] uppercase tracking-wider text-slate-400 mt-2"
          >
            Razão (mín. {REASON_MIN} chars · alimenta a aprendizagem)
          </label>
          <textarea
            id={reasonId}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={busy}
            rows={2}
            placeholder="Ex: novo equipamento mudou tempos médios, validado pela equipa"
            className={`w-full rounded-md border bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 disabled:opacity-60 ${
              reason.length === 0 || reasonValid
                ? 'border-slate-700/70'
                : 'border-amber-500/60'
            }`}
          />
          {error ? <div className="text-xs text-rose-300">{error}</div> : null}
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-slate-400">
              {reasonValid
                ? '✓ Razão suficiente'
                : `Faltam ${Math.max(
                    0,
                    REASON_MIN - reason.trim().length,
                  )} caracteres`}
            </span>
            <div className="flex gap-2">
              <DarkButton
                variant="secondary"
                onClick={() => {
                  setEditing(false);
                  setReason('');
                  setError(null);
                  setEditValue(String(value));
                }}
                disabled={busy}
              >
                <X className="w-3.5 h-3.5" /> Cancelar
              </DarkButton>
              <DarkButton variant="primary" onClick={handleSave} disabled={busy || !reasonValid}>
                {busy ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Save className="w-3.5 h-3.5" />
                )}
                Guardar
              </DarkButton>
            </div>
          </div>
        </div>
      ) : null}

      {hintMode && learnedRuleHint ? (
        <div className="flex flex-col gap-2 pt-2 border-t border-slate-800">
          <label className="text-[11px] uppercase tracking-wider text-violet-300 inline-flex items-center gap-1">
            <Sparkles className="w-3.5 h-3.5" />
            Aceitar regra aprendida → {fmtValue(learnedRuleHint.suggestedValue)}
          </label>
          <textarea
            value={hintReason}
            onChange={(e) => setHintReason(e.target.value)}
            disabled={busy}
            rows={2}
            placeholder="Ex: confirmo o padrão observado nas últimas 4 semanas"
            className={`w-full rounded-md border bg-slate-900 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/40 disabled:opacity-60 ${
              hintReason.length === 0 || hintReasonValid
                ? 'border-slate-700/70'
                : 'border-amber-500/60'
            }`}
          />
          {error ? <div className="text-xs text-rose-300">{error}</div> : null}
          <div className="flex items-center justify-end gap-2">
            <DarkButton
              variant="secondary"
              onClick={() => {
                setHintMode(false);
                setHintReason('');
                setError(null);
              }}
              disabled={busy}
            >
              <X className="w-3.5 h-3.5" /> Cancelar
            </DarkButton>
            <DarkButton
              variant="primary"
              onClick={handleAcceptHint}
              disabled={busy || !hintReasonValid}
            >
              {busy ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="w-3.5 h-3.5" />
              )}
              Aplicar regra
            </DarkButton>
          </div>
        </div>
      ) : null}
    </div>
  );
}
