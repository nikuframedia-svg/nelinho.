import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { GitBranch, Clock, TrendingUp, AlertTriangle, ArrowRight, Info } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkBadge } from '../../components/dark';
import { LiveBadge } from '../../components/dashboard/LiveBadge';
import { useRealtime } from '../../providers/RealtimeProvider';
import { cpoCommitsApi, type CpoAlternativeEnriched, type CpoAlternativesResponse } from '../../lib/api';
import { fmtKpi, KpiTile, AlternativeCard, DecideModal, CommitsList, type RejectionCategory } from './timelineBits';

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
