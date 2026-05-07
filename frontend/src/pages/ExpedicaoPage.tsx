/**
 * ExpedicaoPage — Plan v4 §4.4 (Despacho) shipment-list view.
 *
 * Mostra cada batch de transporte agrupado por data, com:
 *   - data + destino + estado (OPEN / FROZEN / DISPATCHED)
 *   - barra de carga (assigned vs capacidade do camião)
 *   - sugestões do CPO/transport_suggestions, renderizadas via
 *     SuggestionCard (5-block: O QUE / PORQUÊ / SE ACEITAR / SE REJEITAR
 *     / ALTERNATIVA — Plan v4 §8 contract). Sem aceite ou rejeição
 *     persistente neste passo (a write API ainda não existe); o botão
 *     "Aceitar" no batch dá freeze.
 *
 * ZERO MOCKS — empty/loading/error states explícitos. Frontend-only;
 * nada de fake data.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Loader2,
  Lock,
  Package,
  RefreshCw,
  ServerCrash,
  Snowflake,
  Truck,
} from 'lucide-react';
import {
  transportApi,
  type TransportBatch,
  type TransportBatchStatus,
  type TransportSuggestion,
} from '../lib/api';
import { DarkPageLayout } from '../layouts';
import {
  DarkBadge,
  DarkButton,
  DarkCard,
} from '../components/dark';
import { SuggestionCard } from '../components/decision';
import type { Suggestion } from '../types/decision';

const STATUS_VARIANT: Record<
  TransportBatchStatus,
  { label: string; variant: 'success' | 'warning' | 'info' | 'neutral' }
> = {
  OPEN: { label: 'Aberto', variant: 'info' },
  FROZEN: { label: 'Congelado', variant: 'warning' },
  DISPATCHED: { label: 'Expedido', variant: 'success' },
};

function fmtDate(iso: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('pt-PT', {
      weekday: 'short',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

function transportSuggestionToDecision(
  s: TransportSuggestion,
  idx: number,
  batchId: string,
): Suggestion {
  return {
    id: `${batchId}:${idx}`,
    priority: s.type === 'complete_truck' ? 'high' : 'medium',
    title: s.what,
    what_changed: s.what,
    why: s.why,
    if_accept: s.if_accept,
    if_reject: s.if_reject,
    alternative: s.alternative
      ? { label: s.alternative }
      : null,
    confidence: 0.7,
    source: `transport:${s.type}`,
    created_at: new Date().toISOString(),
    status: 'pending',
  };
}

function BatchCard({ batch }: { batch: TransportBatch }) {
  const queryClient = useQueryClient();
  const [showSuggestions, setShowSuggestions] = useState(false);

  const suggestionsQuery = useQuery({
    queryKey: ['expedicao', batch.id, 'suggestions'],
    queryFn: () => transportApi.suggestions(batch.id),
    enabled: showSuggestions && batch.status !== 'DISPATCHED',
    staleTime: 30_000,
  });

  const freezeMutation = useMutation({
    mutationFn: () => transportApi.freeze(batch.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expedicao'] });
    },
  });
  const dispatchMutation = useMutation({
    mutationFn: () => transportApi.dispatch(batch.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expedicao'] });
    },
  });

  const statusInfo = STATUS_VARIANT[batch.status];
  const assigned = batch.assigned_orders_count ?? 0;
  const capacity = batch.truck_capacity_units || 1;
  const pct = Math.min(100, Math.round((assigned / capacity) * 100));
  const tone = pct >= 90 ? 'bg-emerald-500' : pct >= 50 ? 'bg-sky-500' : 'bg-slate-600';
  const isOpen = batch.status === 'OPEN';
  const isFrozen = batch.status === 'FROZEN';
  const isDispatched = batch.status === 'DISPATCHED';

  return (
    <DarkCard className="p-4 flex flex-col gap-3">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <Package className="w-5 h-5 text-sky-300 shrink-0" />
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-slate-100 text-base">
                {batch.code}
              </span>
              <DarkBadge variant={statusInfo.variant}>{statusInfo.label}</DarkBadge>
            </div>
            <span className="text-sm text-slate-400">
              {fmtDate(batch.transport_date)} · {batch.destination ?? 'destino por definir'}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isOpen ? (
            <DarkButton
              variant="secondary"
              disabled={freezeMutation.isPending}
              onClick={() => freezeMutation.mutate()}
            >
              {freezeMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Snowflake className="w-3.5 h-3.5" />
              )}
              Congelar
            </DarkButton>
          ) : null}
          {isFrozen ? (
            <DarkButton
              variant="primary"
              disabled={dispatchMutation.isPending}
              onClick={() => dispatchMutation.mutate()}
            >
              {dispatchMutation.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Truck className="w-3.5 h-3.5" />
              )}
              Expedir
            </DarkButton>
          ) : null}
          {isDispatched ? (
            <span className="inline-flex items-center gap-1 text-xs text-emerald-300">
              <Lock className="w-3.5 h-3.5" /> Selado
            </span>
          ) : null}
        </div>
      </header>

      <div>
        <div className="flex justify-between text-xs text-slate-400 mb-1.5">
          <span>
            {assigned} de {capacity} barcos · {pct}%
          </span>
          {pct < 50 && isOpen ? (
            <span className="text-amber-300">Camião sub-utilizado</span>
          ) : null}
        </div>
        <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
          <div
            className={`h-full ${tone} transition-all`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {isDispatched ? null : (
        <div className="flex flex-col gap-2 pt-2 border-t border-slate-800">
          <button
            type="button"
            onClick={() => setShowSuggestions((v) => !v)}
            className="text-xs uppercase tracking-wider text-sky-300 hover:text-sky-200 self-start"
          >
            {showSuggestions ? 'Esconder sugestões' : 'Ver sugestões do CPO'}
          </button>
          {showSuggestions ? (
            suggestionsQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-300 py-2">
                <Loader2 className="w-4 h-4 animate-spin" /> A calcular sugestões...
              </div>
            ) : suggestionsQuery.error ? (
              <div className="text-sm text-rose-300">
                Não consegui ler sugestões:{' '}
                {suggestionsQuery.error instanceof Error
                  ? suggestionsQuery.error.message
                  : String(suggestionsQuery.error)}
              </div>
            ) : (suggestionsQuery.data ?? []).length === 0 ? (
              <div className="text-sm text-slate-400">
                Sem sugestões — o batch está bem como está.
              </div>
            ) : (
              <ol className="flex flex-col gap-2 list-none p-0 m-0">
                {(suggestionsQuery.data ?? []).map((s, idx) => (
                  <li key={`${batch.id}-sug-${idx}`}>
                    <SuggestionCard
                      suggestion={transportSuggestionToDecision(s, idx, batch.id)}
                      onAccept={() => {
                        // Sem write path persistente para sugestões de transporte
                        // ainda — para já só fechamos visualmente. O backend
                        // /v1/plan/transport/batches/:id/suggestions/:idx/accept
                        // entra num sprint posterior.
                        setShowSuggestions(false);
                      }}
                      onReject={() => {
                        setShowSuggestions(false);
                      }}
                    />
                  </li>
                ))}
              </ol>
            )
          ) : null}
        </div>
      )}
    </DarkCard>
  );
}

export default function ExpedicaoPage() {
  const [statusFilter, setStatusFilter] = useState<TransportBatchStatus | 'ALL'>('ALL');

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['expedicao', statusFilter],
    queryFn: () =>
      transportApi.listBatches({
        status: statusFilter === 'ALL' ? undefined : statusFilter,
      }),
    staleTime: 15_000,
  });

  const grouped = useMemo(() => {
    const out: Record<string, TransportBatch[]> = {};
    for (const b of data ?? []) {
      const key = b.transport_date.slice(0, 10);
      if (!out[key]) out[key] = [];
      out[key].push(b);
    }
    return Object.entries(out).sort(([a], [b]) => a.localeCompare(b));
  }, [data]);

  return (
    <DarkPageLayout
      title="Expedição"
      subtitle="Cada camião é uma decisão. Vê carga, sugestões e expede com um clique."
      icon={<Truck className="w-6 h-6 text-sky-300" />}
      actions={
        <DarkButton
          onClick={() => refetch()}
          variant="secondary"
          disabled={isFetching}
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          Actualizar
        </DarkButton>
      }
    >
      <div className="flex flex-col gap-4">
        <DarkCard className="p-3 flex flex-wrap items-center gap-2">
          <span className="text-[11px] uppercase tracking-wider text-slate-400">
            Estado:
          </span>
          {(['ALL', 'OPEN', 'FROZEN', 'DISPATCHED'] as const).map((s) => (
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
              {s === 'ALL'
                ? 'Todos'
                : s === 'OPEN'
                ? 'Abertos'
                : s === 'FROZEN'
                ? 'Congelados'
                : 'Expedidos'}
            </button>
          ))}
        </DarkCard>

        {isLoading ? (
          <DarkCard className="p-10 flex items-center justify-center gap-2 text-slate-300">
            <Loader2 className="w-5 h-5 animate-spin text-sky-300" /> A carregar
            expedições...
          </DarkCard>
        ) : error ? (
          <DarkCard className="p-10 flex flex-col items-center gap-3 border-rose-500/30 bg-rose-500/5 text-rose-200">
            <ServerCrash className="w-8 h-8" />
            <div className="text-base font-semibold">
              Não consegui ler as expedições.
            </div>
            <div className="text-sm text-rose-200/80 max-w-lg text-center">
              {error instanceof Error ? error.message : String(error)}
            </div>
            <DarkButton onClick={() => refetch()} variant="primary">
              Tentar de novo
            </DarkButton>
          </DarkCard>
        ) : grouped.length === 0 ? (
          <DarkCard className="p-10 flex flex-col items-center gap-2 text-slate-400">
            <Truck className="w-10 h-10 text-slate-600" />
            <div className="text-base text-slate-200">Sem expedições neste filtro.</div>
            <div className="text-sm">Cria um batch novo no Planeamento.</div>
          </DarkCard>
        ) : (
          grouped.map(([date, batches]) => (
            <section key={date} className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
                {fmtDate(date)} ·{' '}
                <span className="text-slate-500 normal-case">
                  {batches.length} expedição{batches.length === 1 ? '' : 'es'}
                </span>
              </h3>
              {batches.map((b) => (
                <BatchCard key={b.id} batch={b} />
              ))}
            </section>
          ))
        )}
      </div>
    </DarkPageLayout>
  );
}
