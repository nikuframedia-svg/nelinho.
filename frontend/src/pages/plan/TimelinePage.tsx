/**
 * TimelinePage (Sprint E.1)
 * ===========================
 *
 * ``/plan/timeline`` — the moat made visible. Lists every
 * ``ScheduleCommit`` the CPO engine has published and lets the operator
 * inspect up to eight MAP-Elites alternatives side-by-side for a given
 * commit. Picking one alternative records the decision through
 * ``POST /v1/plan/cpo/commits/{sha}/decide``; the rejected siblings
 * feed Camada 1 on the next nightly detector run, closing the loop.
 *
 * Realtime: the shared ``RealtimeProvider`` streams
 * ``SCHEDULE_CREATED`` / ``SCHEDULE_UPDATED`` events and we invalidate
 * the commit list (debounced) so a new commit shows up without a
 * manual refresh.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  GitBranch,
  CheckCircle2,
  Clock,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  Info,
  X,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { pt } from 'date-fns/locale';
import { DarkPageLayout } from '../../layouts';
import {
  DarkCard,
  DarkButton,
  DarkBadge,
} from '../../components/dark';
import { LiveBadge } from '../../components/dashboard/LiveBadge';
import { useRealtime } from '../../providers/RealtimeProvider';
import {
  cpoCommitsApi,
  type CpoAlternativeEnriched,
  type CpoAlternativesResponse,
  type CpoCommit,
} from '../../lib/api';

// ─── Helpers ──────────────────────────────────────────────────────────────

/** Format a KPI numeric value for the hero card. Falls back to string. */
function fmtKpi(v: any): string {
  if (typeof v === 'number') {
    if (Math.abs(v) >= 1000) return v.toFixed(0);
    if (Math.abs(v) >= 10) return v.toFixed(1);
    return v.toFixed(2);
  }
  if (v === null || v === undefined) return '—';
  return String(v);
}

function KpiTile({
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

interface AlternativeCardProps {
  alt: CpoAlternativeEnriched;
  onChoose: () => void;
  submitting: boolean;
}

function AlternativeCard({ alt, onChoose, submitting }: AlternativeCardProps) {
  const mainDeltas = useMemo(() => {
    return Object.entries(alt.vs_primary)
      .filter(([, v]) => v !== null)
      .slice(0, 3) as Array<[string, string]>;
  }, [alt.vs_primary]);

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
      </div>

      <p className="text-sm text-text-secondary mb-3 leading-snug">
        {alt.trade_off_narrative}
      </p>

      {mainDeltas.length > 0 && (
        <div className="space-y-1 mb-4">
          {mainDeltas.map(([key, delta]) => {
            const positive = delta.startsWith('+');
            const neutral = delta.startsWith('+0.0') || delta === '0.0%';
            const colour = neutral
              ? 'text-text-tertiary'
              : positive
              ? 'text-amber-300'
              : 'text-emerald-300';
            return (
              <div
                key={key}
                className="flex items-center justify-between text-xs"
              >
                <span className="text-text-tertiary">{key}</span>
                <span className={`tabular-nums ${colour}`}>{delta}</span>
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

type RejectionCategory =
  | 'COST'
  | 'QUALITY'
  | 'CUSTOMER'
  | 'CAPACITY'
  | 'MOLD'
  | 'WORKFORCE'
  | 'OTHER';

const REJECTION_CATEGORIES: Array<{ value: RejectionCategory; label: string }> = [
  { value: 'COST', label: 'Custo' },
  { value: 'QUALITY', label: 'Qualidade' },
  { value: 'CUSTOMER', label: 'Cliente' },
  { value: 'CAPACITY', label: 'Capacidade' },
  { value: 'MOLD', label: 'Molde' },
  { value: 'WORKFORCE', label: 'Operadores' },
  { value: 'OTHER', label: 'Outro' },
];

interface DecideModalProps {
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

function DecideModal({
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

interface CommitsListProps {
  commits: CpoCommit[];
  selectedSha: string | null;
  onSelect: (sha: string) => void;
  loading: boolean;
}

function CommitsList({
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

export function TimelinePage() {
  const queryClient = useQueryClient();
  const realtime = useRealtime();
  const [selectedSha, setSelectedSha] = useState<string | null>(null);
  const [pendingChoice, setPendingChoice] =
    useState<CpoAlternativeEnriched | null>(null);
  const [lastEventAt, setLastEventAt] = useState<Date | null>(null);

  const commitsQuery = useQuery({
    queryKey: ['cpo-commits'],
    queryFn: () => cpoCommitsApi.list({ limit: 50 }),
  });

  const altsQuery = useQuery({
    queryKey: ['cpo-alternatives', selectedSha],
    queryFn: () =>
      selectedSha ? cpoCommitsApi.alternatives(selectedSha, { n: 8 }) : null,
    enabled: !!selectedSha,
  });

  // Auto-select the latest commit once the list lands.
  useEffect(() => {
    if (
      !selectedSha &&
      commitsQuery.data &&
      commitsQuery.data.length > 0
    ) {
      setSelectedSha(commitsQuery.data[0].commit_sha256);
    }
  }, [commitsQuery.data, selectedSha]);

  // SSE → invalidate commits list (debounced). A new commit bubbles up
  // without the operator needing to click refresh.
  const processedLen = useRef(0);
  const debounceTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!realtime) return;
    const total = realtime.events.length;
    if (total === processedLen.current) return;
    const fresh = realtime.events.slice(processedLen.current, total);
    processedLen.current = total;

    let sawCommitEvent = false;
    let latestAt: Date | null = null;
    for (const ev of fresh) {
      if (
        ev.event_type === 'SCHEDULE_CREATED' ||
        ev.event_type === 'SCHEDULE_UPDATED'
      ) {
        sawCommitEvent = true;
        latestAt = ev.timestamp ? new Date(ev.timestamp) : new Date();
      }
    }
    if (!sawCommitEvent) return;
    setLastEventAt(latestAt);

    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => {
      queryClient.invalidateQueries({ queryKey: ['cpo-commits'] });
      debounceTimer.current = null;
    }, 1_500);
  }, [realtime?.events.length, realtime, queryClient]);

  useEffect(
    () => () => {
      if (debounceTimer.current) clearTimeout(debounceTimer.current);
    },
    [],
  );

  const decideMut = useMutation({
    mutationFn: (body: {
      sha: string;
      chosen_alt_idx: number;
      rejected_alt_idxs: number[];
      reason?: string;
      rejection_category?: RejectionCategory;
    }) =>
      cpoCommitsApi.decide(body.sha, {
        chosen_alt_idx: body.chosen_alt_idx,
        rejected_alt_idxs: body.rejected_alt_idxs,
        reason: body.reason,
        rejection_category: body.rejection_category ?? null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cpo-commits'] });
      if (selectedSha) {
        queryClient.invalidateQueries({
          queryKey: ['cpo-alternatives', selectedSha],
        });
      }
    },
  });

  function handleConfirm(payload: {
    chosen_alt_idx: number;
    rejected_alt_idxs: number[];
    reason?: string;
    rejection_category?: RejectionCategory;
  }) {
    if (!selectedSha) return;
    decideMut.mutate(
      { sha: selectedSha, ...payload },
      {
        onSuccess: () => setPendingChoice(null),
      },
    );
  }

  const primaryKpiTiles: Array<[string, string, React.ReactNode]> =
    useMemo(() => {
      const k = altsQuery.data?.primary_kpis ?? {};
      return [
        ['Makespan', fmtKpi(k.makespan_hours) + ' h', <Clock key="c" size={14} />],
        [
          'Tardiness',
          fmtKpi(k.total_tardiness_hours) + ' h',
          <AlertTriangle key="a" size={14} />,
        ],
        ['Setups', fmtKpi(k.setups), <TrendingUp key="t" size={14} />],
        [
          '€/dia',
          fmtKpi(k.throughput_eur_day),
          <TrendingUp key="e" size={14} />,
        ],
      ];
    }, [altsQuery.data?.primary_kpis]);

  return (
    <DarkPageLayout
      title="Timeline"
      subtitle="Commits + alternativas MAP-Elites — fecha o ciclo de aprendizagem"
      icon={<GitBranch size={20} />}
      actions={<LiveBadge lastEventAt={lastEventAt} />}
    >
      <DarkCard className="mb-6 bg-accent/10 border-accent/20">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-accent/20 rounded-lg flex-shrink-0">
            <Info size={18} className="text-accent" />
          </div>
          <div>
            <h4 className="text-sm font-medium text-accent">
              Cada escolha alimenta a Camada 1
            </h4>
            <p className="text-xs text-text-tertiary mt-1">
              Ao escolher uma alternativa, as restantes ficam marcadas como
              rejeitadas (com KPIs e deltas). O{' '}
              <code className="text-accent">PreferenceRuleDetector</code>{' '}
              analisa-as à noite e propõe regras em{' '}
              <a href="/admin/learned-rules" className="underline">
                /admin/learned-rules
              </a>
              .
            </p>
          </div>
        </div>
      </DarkCard>

      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4">
        {/* Commits list */}
        <DarkCard padding="none" className="max-h-[calc(100vh-220px)] overflow-y-auto">
          <div className="px-4 py-3 border-b border-border-subtle bg-bg-secondary/40">
            <h2 className="text-sm font-semibold text-text-white">
              Commits recentes
            </h2>
            <p className="text-xs text-text-tertiary mt-0.5">
              {commitsQuery.data?.length ?? 0} publicados
            </p>
          </div>
          <CommitsList
            commits={commitsQuery.data ?? []}
            selectedSha={selectedSha}
            onSelect={setSelectedSha}
            loading={commitsQuery.isLoading}
          />
        </DarkCard>

        {/* Alternatives detail */}
        <div className="min-w-0">
          {!selectedSha ? (
            <DarkCard>
              <p className="text-sm text-text-tertiary text-center py-8">
                Escolhe um commit na lista à esquerda.
              </p>
            </DarkCard>
          ) : altsQuery.isLoading ? (
            <DarkCard>
              <p className="text-sm text-text-tertiary text-center py-8">
                A carregar alternativas…
              </p>
            </DarkCard>
          ) : !altsQuery.data ? (
            <DarkCard>
              <p className="text-sm text-text-tertiary text-center py-8">
                Não consegui ler as alternativas para este commit.
              </p>
            </DarkCard>
          ) : (
            <TimelineDetail
              data={altsQuery.data}
              kpiTiles={primaryKpiTiles}
              onChoose={setPendingChoice}
              submitting={decideMut.isPending}
            />
          )}
        </div>
      </div>

      {pendingChoice && selectedSha && altsQuery.data && (
        <DecideModal
          commitSha={selectedSha}
          chosen={pendingChoice}
          alternatives={altsQuery.data.alternatives}
          onClose={() => setPendingChoice(null)}
          onConfirm={handleConfirm}
          submitting={decideMut.isPending}
        />
      )}
    </DarkPageLayout>
  );
}

interface TimelineDetailProps {
  data: CpoAlternativesResponse;
  kpiTiles: Array<[string, string, React.ReactNode]>;
  onChoose: (alt: CpoAlternativeEnriched) => void;
  submitting: boolean;
}

function TimelineDetail({
  data,
  kpiTiles,
  onChoose,
  submitting,
}: TimelineDetailProps) {
  return (
    <div className="space-y-4">
      {/* Primary hero */}
      <DarkCard>
        <div className="flex items-start justify-between mb-4">
          <div>
            <DarkBadge variant="success">Primary</DarkBadge>
            <code className="text-xs text-text-tertiary ml-2">
              {data.commit_sha256.slice(0, 12)}
            </code>
          </div>
          <ArrowRight size={16} className="text-text-tertiary" />
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {kpiTiles.map(([label, value, icon]) => (
            <KpiTile key={label} label={label} value={value} icon={icon} />
          ))}
        </div>
      </DarkCard>

      {/* Alternatives grid */}
      {data.alternatives.length === 0 ? (
        <DarkCard>
          <p className="text-sm text-text-tertiary text-center py-6">
            Este commit não tem alternativas MAP-Elites arquivadas.
          </p>
        </DarkCard>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
          {data.alternatives.map((alt) => (
            <AlternativeCard
              key={alt.rank}
              alt={alt}
              onChoose={() => onChoose(alt)}
              submitting={submitting}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default TimelinePage;
