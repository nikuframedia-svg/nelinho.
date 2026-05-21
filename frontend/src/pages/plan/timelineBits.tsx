// Decomposto de TimelinePage.tsx (Q.60.AB).
import { useMemo, useState } from 'react';
import { CheckCircle2, X } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { pt } from 'date-fns/locale';
import { DarkCard, DarkButton, DarkBadge } from '../../components/dark';
import { type CpoAlternativeEnriched, type CpoCommit } from '../../lib/api';

// ─── Helpers ──────────────────────────────────────────────────────────────

/** Format a KPI numeric value for the hero card. Falls back to string. */
export function fmtKpi(v: unknown): string {
  if (typeof v === 'number') {
    if (Math.abs(v) >= 1000) return v.toFixed(0);
    if (Math.abs(v) >= 10) return v.toFixed(1);
    return v.toFixed(2);
  }
  if (v === null || v === undefined) return '—';
  return String(v);
}

export function KpiTile({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="bg-bg-elevated border border-border-subtle rounded-lg p-3">
      <div className="flex items-center gap-1.5 text-xs text-text-tertiary mb-1">
        {icon}
        <span>{label}</span>
      </div>
      <div className="text-lg font-semibold text-text-white tabular-nums">
        {value}
      </div>
    </div>
  );
}

// ─── Alternative card ─────────────────────────────────────────────────────

export interface AlternativeCardProps {
  alt: CpoAlternativeEnriched;
  onChoose: () => void;
  submitting: boolean;
}

// Sprint Q.13.C C.3.3 — KPIs where a positive Δ% is BAD news (the
// candidate did MORE of an unwanted thing). The default assumption is
// "+ = bad" (e.g. tardiness up = bad, setup_time up = bad), but a few
// metrics invert: throughput_eur_day, otd_delivery, makespan_savings,
// idle_avoided. We render those in green when positive, amber/rose
// when negative — opposite of the default direction.
export const _LOWER_IS_BETTER: ReadonlySet<string> = new Set([
  'makespan_hours',
  'total_tardiness_hours',
  'num_late_orders',
  'avg_quality_risk',
  'total_setup_time_h',
  'idle_operators_h',
  'tardiness_transport',
]);
export const _HIGHER_IS_BETTER: ReadonlySet<string> = new Set([
  'throughput_eur_day',
  'otd_delivery',
  'avg_utilization',
  'lam_utilization',
]);

export function _classifyDelta(
  key: string,
  delta: string,
): 'improvement' | 'regression' | 'neutral' {
  // Parse "+12.3%" / "-5.1%" / "0.0%" / "+0.0%" → numeric and sign.
  const trimmed = delta.replace('%', '').trim();
  if (!trimmed || trimmed === '0.0' || trimmed === '+0.0' || trimmed === '-0.0') {
    return 'neutral';
  }
  const value = parseFloat(trimmed);
  if (Number.isNaN(value)) return 'neutral';
  if (Math.abs(value) < 0.1) return 'neutral';
  const positive = value > 0;
  if (_LOWER_IS_BETTER.has(key)) return positive ? 'regression' : 'improvement';
  if (_HIGHER_IS_BETTER.has(key)) return positive ? 'improvement' : 'regression';
  // Unknown key — fall back to "+ = regression" pessimistic default.
  return positive ? 'regression' : 'improvement';
}

export function _deltaMagnitude(delta: string): number {
  const value = parseFloat(delta.replace('%', '').replace('+', '').trim());
  return Number.isNaN(value) ? 0 : Math.abs(value);
}

export function AlternativeCard({ alt, onChoose, submitting }: AlternativeCardProps) {
  // Sprint Q.13.C C.3.3 — rich trade-off rendering. Plan v4 §8 promises
  // the manager sees alternatives with their full KPI delta vector
  // sorted by impact, with each delta classified (improvement / neutral
  // / regression) so a 30-second scan immediately conveys "what does
  // this trade".
  const sortedDeltas = useMemo(() => {
    const entries = Object.entries(alt.vs_primary).filter(
      ([, v]) => v !== null && v !== undefined,
    ) as Array<[string, string]>;
    return entries
      .map(([key, delta]) => ({
        key,
        delta,
        kind: _classifyDelta(key, delta),
        magnitude: _deltaMagnitude(delta),
      }))
      .sort((a, b) => b.magnitude - a.magnitude);
  }, [alt.vs_primary]);

  const improvements = sortedDeltas.filter((d) => d.kind === 'improvement');
  const regressions = sortedDeltas.filter((d) => d.kind === 'regression');

  return (
    <DarkCard className="flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div>
          <DarkBadge variant="info" size="sm">
            Alt #{alt.rank}
          </DarkBadge>
          <div className="text-xs text-text-tertiary mt-1">
            Gen {alt.generation} · fit {alt.fitness.toFixed(2)}
          </div>
        </div>
        {/* Trade-off summary chips: at-a-glance count of improvements
            and regressions so manager doesn't have to count rows. */}
        <div className="flex items-center gap-1 text-[10px] font-semibold">
          {improvements.length > 0 ? (
            <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
              ↑{improvements.length}
            </span>
          ) : null}
          {regressions.length > 0 ? (
            <span className="px-1.5 py-0.5 rounded bg-rose-500/15 text-rose-300">
              ↓{regressions.length}
            </span>
          ) : null}
        </div>
      </div>

      <p className="text-sm text-text-secondary mb-3 leading-snug">
        {alt.trade_off_narrative}
      </p>

      {sortedDeltas.length > 0 && (
        <div className="space-y-1 mb-4">
          {sortedDeltas.map(({ key, delta, kind, magnitude }) => {
            const tone =
              kind === 'improvement'
                ? 'text-emerald-300'
                : kind === 'regression'
                ? 'text-rose-300'
                : 'text-text-tertiary';
            // Visual mini-bar: width proportional to magnitude (clamped
            // at 30% of the row to keep large outliers from breaking
            // layout). Shows "this delta is bigger than that one"
            // without forcing operator to compare numbers mentally.
            const widthPct = Math.min(30, Math.max(2, magnitude));
            const barTone =
              kind === 'improvement'
                ? 'bg-emerald-500/40'
                : kind === 'regression'
                ? 'bg-rose-500/40'
                : 'bg-slate-600/40';
            return (
              <div
                key={key}
                className="grid grid-cols-[1fr_auto_auto] gap-2 items-center text-xs"
              >
                <span className="text-text-tertiary truncate" title={key}>
                  {key}
                </span>
                <div
                  className={`h-1.5 rounded-full ${barTone}`}
                  style={{ width: `${widthPct * 4}px` }}
                  aria-hidden
                />
                <span className={`tabular-nums font-medium ${tone}`}>
                  {delta}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-auto">
        <DarkButton
          variant="primary"
          size="sm"
          fullWidth
          onClick={onChoose}
          disabled={submitting}
        >
          <CheckCircle2 size={14} className="mr-1.5" />
          Escolher este
        </DarkButton>
      </div>
    </DarkCard>
  );
}

// ─── Decide modal ────────────────────────────────────────────────────────

export type RejectionCategory =
  | 'COST'
  | 'QUALITY'
  | 'CUSTOMER'
  | 'CAPACITY'
  | 'MOLD'
  | 'WORKFORCE'
  | 'OTHER';

export const REJECTION_CATEGORIES: Array<{ value: RejectionCategory; label: string }> = [
  { value: 'COST', label: 'Custo' },
  { value: 'QUALITY', label: 'Qualidade' },
  { value: 'CUSTOMER', label: 'Cliente' },
  { value: 'CAPACITY', label: 'Capacidade' },
  { value: 'MOLD', label: 'Molde' },
  { value: 'WORKFORCE', label: 'Operadores' },
  { value: 'OTHER', label: 'Outro' },
];

export interface DecideModalProps {
  commitSha: string;
  chosen: CpoAlternativeEnriched;
  alternatives: CpoAlternativeEnriched[];
  onClose: () => void;
  onConfirm: (payload: {
    chosen_alt_idx: number;
    rejected_alt_idxs: number[];
    reason?: string;
    rejection_category?: RejectionCategory;
  }) => void;
  submitting: boolean;
}

export function DecideModal({
  commitSha,
  chosen,
  alternatives,
  onClose,
  onConfirm,
  submitting,
}: DecideModalProps) {
  const [reason, setReason] = useState('');
  const [rejectOthers, setRejectOthers] = useState(true);
  const [category, setCategory] = useState<RejectionCategory | ''>('');

  // Every non-chosen alternative ends up as `rejected_alt_idx` so the
  // PreferenceRuleDetector has a full pair dataset. Operator can opt
  // out via the checkbox (e.g. when they want to keep exploring).
  const rejectedIdxs = useMemo(() => {
    if (!rejectOthers) return [];
    return alternatives
      .map((a) => a.rank)
      .filter((rank) => rank !== chosen.rank);
  }, [alternatives, chosen.rank, rejectOthers]);

  // Sprint Q.5 — when alternatives are being rejected, the category
  // becomes mandatory so the detector has a tagged feature to learn from.
  const requiresCategory = rejectedIdxs.length > 0;
  const canSubmit = !requiresCategory || category !== '';

  function handleSubmit() {
    onConfirm({
      chosen_alt_idx: chosen.rank,
      rejected_alt_idxs: rejectedIdxs,
      reason: reason.trim() || undefined,
      rejection_category:
        requiresCategory && category !== '' ? category : undefined,
    });
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/60 z-[200]" onClick={onClose} />
      <div className="fixed inset-0 z-[201] flex items-center justify-center p-4">
        <div className="bg-bg-card border border-border-subtle rounded-xl shadow-2xl w-full max-w-lg p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold text-text-white">
                Confirmar escolha
              </h2>
              <p className="text-sm text-text-tertiary mt-1">
                Commit{' '}
                <code className="text-accent">{commitSha.slice(0, 12)}</code>
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-bg-secondary rounded-lg text-text-tertiary hover:text-text-white transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          <div className="bg-accent/10 border border-accent/20 rounded-lg p-3 mb-4">
            <div className="flex items-center gap-2 mb-1">
              <CheckCircle2 size={16} className="text-accent" />
              <span className="text-sm font-medium text-accent">
                Alt #{chosen.rank}
              </span>
            </div>
            <p className="text-xs text-text-secondary">
              {chosen.trade_off_narrative}
            </p>
          </div>

          <label className="flex items-start gap-2 mb-4 cursor-pointer">
            <input
              type="checkbox"
              checked={rejectOthers}
              onChange={(e) => setRejectOthers(e.target.checked)}
              className="mt-1 accent-accent"
            />
            <span className="text-sm text-text-secondary">
              Marcar as outras {alternatives.length - 1} alternativas como
              rejeitadas
              <span className="block text-xs text-text-tertiary mt-0.5">
                Alimenta o detector Camada 1 — recomendado na decisão final.
              </span>
            </span>
          </label>

          {requiresCategory && (
            <label className="block mb-3">
              <span className="text-sm text-text-secondary">
                Categoria de rejeição{' '}
                <span className="text-red-400">*</span>
                <span className="block text-xs text-text-tertiary mt-0.5">
                  Obrigatória — alimenta a Camada 1 com um sinal categorial.
                </span>
              </span>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value as RejectionCategory | '')}
                className="mt-1 w-full rounded-lg bg-bg-elevated border border-border-subtle px-3 py-2 text-sm text-text-white focus:outline-none focus:border-accent"
              >
                <option value="">— escolher —</option>
                {REJECTION_CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="block mb-4">
            <span className="text-sm text-text-secondary">
              Razão (opcional)
            </span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="Ex: menos setups, prazo folgado — priorizar qualidade"
              className="mt-1 w-full rounded-lg bg-bg-elevated border border-border-subtle px-3 py-2 text-sm text-text-white focus:outline-none focus:border-accent"
            />
          </label>

          <div className="flex items-center justify-end gap-2">
            <DarkButton variant="ghost" size="sm" onClick={onClose}>
              Cancelar
            </DarkButton>
            <DarkButton
              variant="primary"
              size="sm"
              onClick={handleSubmit}
              disabled={submitting || !canSubmit}
              title={!canSubmit ? 'Escolhe a categoria de rejeição primeiro' : undefined}
            >
              {submitting ? 'A gravar…' : 'Confirmar'}
            </DarkButton>
          </div>
        </div>
      </div>
    </>
  );
}

// ─── Commits list (left pane) ────────────────────────────────────────────

export interface CommitsListProps {
  commits: CpoCommit[];
  selectedSha: string | null;
  onSelect: (sha: string) => void;
  loading: boolean;
}

export function CommitsList({
  commits,
  selectedSha,
  onSelect,
  loading,
}: CommitsListProps) {
  if (loading) {
    return (
      <div className="p-8 text-center text-text-tertiary text-sm">
        A carregar commits…
      </div>
    );
  }
  if (commits.length === 0) {
    return (
      <div className="p-8 text-center text-text-tertiary text-sm">
        Ainda não há commits publicados.
      </div>
    );
  }
  return (
    <div className="divide-y divide-border-subtle">
      {commits.map((commit) => {
        const active = commit.commit_sha256 === selectedSha;
        const when = commit.created_at
          ? formatDistanceToNow(new Date(commit.created_at), {
              addSuffix: true,
              locale: pt,
            })
          : '—';
        return (
          <button
            key={commit.commit_sha256}
            onClick={() => onSelect(commit.commit_sha256)}
            className={`w-full text-left p-3 transition-colors ${
              active
                ? 'bg-accent/10 border-l-2 border-l-accent'
                : 'hover:bg-bg-elevated'
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <code className="text-xs text-accent">{commit.short_sha}</code>
              <span className="text-xs text-text-tertiary">{when}</span>
            </div>
            <div className="text-sm text-text-white truncate">
              {commit.message || '(sem mensagem)'}
            </div>
            <div className="flex items-center gap-3 mt-1 text-xs text-text-tertiary">
              <span>TI {commit.trust_index.toFixed(2)}</span>
              <span>{commit.operations_count} ops</span>
              <span>{commit.alternatives.length} alt</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────
