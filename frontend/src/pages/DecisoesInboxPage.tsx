/**
 * DecisoesInboxPage — Plan v4 §4 (advisory mode) + §11 (learning loop).
 *
 * The "inbox" of pending system suggestions for the gestor de produção.
 * Each suggestion renders as a SuggestionCard (5-block explainer +
 * accept/reject with required ≥8-char rejection reason). Aceitar fires
 * /v1/improve/suggestions/:id/approve. Rejeitar fires /reject with the
 * reason (Plan v4 §11: rejection-with-why is the most valuable
 * learning signal).
 *
 * Filtros: status (pendente / decidido / todas), domínio (oee /
 * quality / supply / hr / safety). Real backend, ZERO MOCKS — empty
 * and error states explicit.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Inbox, Loader2, RefreshCw, ServerCrash } from 'lucide-react';
import { suggestionsApi } from '../lib/api';
import { SuggestionCard } from '../components/decision';
import type { Suggestion } from '../types/decision';
import { DarkPageLayout } from '../layouts';
import { DarkButton, DarkCard } from '../components/dark';

type StatusFilter = 'pending' | 'decided' | 'all';
type DomainFilter = 'all' | 'oee' | 'quality' | 'supply' | 'hr' | 'safety';

const DOMAIN_LABEL: Record<DomainFilter, string> = {
  all: 'Todos',
  oee: 'OEE',
  quality: 'Qualidade',
  supply: 'Cadeia',
  hr: 'Pessoas',
  safety: 'Segurança',
};

function statusToBackend(filter: StatusFilter): string | undefined {
  if (filter === 'pending') return 'pending';
  if (filter === 'decided') return undefined;
  return undefined;
}

export default function DecisoesInboxPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('pending');
  const [domainFilter, setDomainFilter] = useState<DomainFilter>('all');
  const queryClient = useQueryClient();

  const queryKey = useMemo(
    () => ['decisions', 'inbox', statusFilter, domainFilter] as const,
    [statusFilter, domainFilter],
  );

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey,
    queryFn: () =>
      suggestionsApi.list({
        status: statusToBackend(statusFilter),
        domain: domainFilter === 'all' ? undefined : domainFilter,
        limit: 50,
      }),
    staleTime: 15_000,
  });

  const suggestions: Suggestion[] = useMemo(() => {
    if (!data) return [];
    if (statusFilter === 'decided') {
      return data.filter((s) => s.status && s.status !== 'pending');
    }
    if (statusFilter === 'all') {
      return data;
    }
    return data.filter((s) => !s.status || s.status === 'pending');
  }, [data, statusFilter]);

  const acceptMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      suggestionsApi.accept(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decisions'] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      suggestionsApi.reject(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decisions'] });
    },
  });

  const busyId =
    acceptMutation.isPending
      ? acceptMutation.variables?.id
      : rejectMutation.isPending
      ? rejectMutation.variables?.id
      : null;

  return (
    <DarkPageLayout
      title="Inbox de Decisões"
      subtitle="Sugestões do sistema à espera do gestor. Aceitar ou rejeitar — com porquê."
      icon={<Inbox className="w-6 h-6 text-sky-300" />}
      actions={
        <DarkButton
          onClick={() => refetch()}
          variant="secondary"
          disabled={isFetching}
        >
          <RefreshCw
            className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`}
          />
          Actualizar
        </DarkButton>
      }
    >
      <div className="flex flex-col gap-4">
        <DarkCard className="p-3 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs uppercase tracking-wider text-slate-400">
            Estado:
          </div>
          {(['pending', 'decided', 'all'] as StatusFilter[]).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-md text-sm border ${
                statusFilter === s
                  ? 'bg-sky-500/20 border-sky-500/50 text-sky-100'
                  : 'border-slate-700/60 text-slate-300 hover:bg-slate-800'
              }`}
            >
              {s === 'pending' ? 'Pendentes' : s === 'decided' ? 'Decididas' : 'Todas'}
            </button>
          ))}
          <div className="w-px h-5 bg-slate-700 mx-1" />
          <div className="flex items-center gap-1.5 text-xs uppercase tracking-wider text-slate-400">
            Domínio:
          </div>
          {(Object.keys(DOMAIN_LABEL) as DomainFilter[]).map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDomainFilter(d)}
              className={`px-3 py-1.5 rounded-md text-sm border ${
                domainFilter === d
                  ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-100'
                  : 'border-slate-700/60 text-slate-300 hover:bg-slate-800'
              }`}
            >
              {DOMAIN_LABEL[d]}
            </button>
          ))}
        </DarkCard>

        {isLoading ? (
          <DarkCard className="p-10 flex flex-col items-center justify-center gap-3 text-slate-300">
            <Loader2 className="w-6 h-6 animate-spin text-sky-300" />
            A carregar sugestões pendentes...
          </DarkCard>
        ) : error ? (
          <DarkCard className="p-10 flex flex-col items-center justify-center gap-3 text-rose-200 border-rose-500/30 bg-rose-500/5">
            <ServerCrash className="w-8 h-8" />
            <div className="text-base font-semibold">Não consegui ler a inbox.</div>
            <div className="text-sm text-rose-200/80 max-w-lg text-center">
              {error instanceof Error ? error.message : String(error)}
            </div>
            <DarkButton onClick={() => refetch()} variant="primary">
              Tentar de novo
            </DarkButton>
          </DarkCard>
        ) : suggestions.length === 0 ? (
          <DarkCard className="p-10 flex flex-col items-center justify-center gap-3 text-slate-300">
            <Inbox className="w-10 h-10 text-slate-500" />
            <div className="text-base font-semibold text-slate-200">
              Inbox vazia.
            </div>
            <div className="text-sm text-slate-400 text-center max-w-md">
              {statusFilter === 'pending'
                ? 'Sem sugestões pendentes neste filtro. O sistema só propõe quando há sinal — silêncio é bom.'
                : 'Nada para mostrar com este filtro.'}
            </div>
          </DarkCard>
        ) : (
          <ol className="flex flex-col gap-3 list-none p-0 m-0">
            {suggestions.map((s) => (
              <li key={s.id}>
                <SuggestionCard
                  suggestion={s}
                  busy={busyId === s.id}
                  onAccept={async (reason) => {
                    await acceptMutation.mutateAsync({ id: s.id, reason });
                  }}
                  onReject={async (reason) => {
                    await rejectMutation.mutateAsync({ id: s.id, reason });
                  }}
                />
              </li>
            ))}
          </ol>
        )}
      </div>
    </DarkPageLayout>
  );
}
