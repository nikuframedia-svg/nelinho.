/**
 * HistoricoTab — decisões já tomadas (Q.118.F base; enriquecido em Q.118.F).
 * ===========================================================================
 *
 * Lista as decisões não-pendentes (aprovadas/rejeitadas/executadas) com filtro
 * por estado, via decisionsApi.list({status_filter}). Cada linha mostra título,
 * estado (DarkBadge), data e origem. Detalhe + audit + loop de aprendizagem
 * entram no Q.118.F.
 *
 * ZERO MOCKS — empty/error/loading explícitos.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { History, AlertTriangle, RefreshCw } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkBadge, DarkButton, EmptyState } from '../../components/dark';
import { Segmented } from '../../components/dark';
import { decisionsApi } from '../../lib/api';
import { decisionKeys } from '../../lib/api/keys';
import type { DecisionRun } from '../../lib/api';

type StatusFilter = 'all' | 'APPROVED' | 'REJECTED' | 'EXECUTED';

const FILTER_OPTIONS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'Todas' },
  { value: 'APPROVED', label: 'Aprovadas' },
  { value: 'REJECTED', label: 'Rejeitadas' },
  { value: 'EXECUTED', label: 'Executadas' },
];

const STATUS_VARIANT: Record<string, 'success' | 'danger' | 'info' | 'neutral' | 'warning'> = {
  APPROVED: 'success',
  EXECUTED: 'info',
  REJECTED: 'danger',
  ROLLED_BACK: 'warning',
  PROPOSED: 'neutral',
};

const STATUS_LABEL: Record<string, string> = {
  APPROVED: 'Aprovada',
  EXECUTED: 'Executada',
  REJECTED: 'Rejeitada',
  ROLLED_BACK: 'Revertida',
  PROPOSED: 'Pendente',
};

export default function HistoricoTab() {
  const [filter, setFilter] = useState<StatusFilter>('all');

  const query = useQuery({
    queryKey: decisionKeys.list({ status: `historico:${filter}` }),
    queryFn: () =>
      decisionsApi.list({
        ...(filter === 'all' ? {} : { status: filter }),
        page_size: 100,
      }),
    refetchOnWindowFocus: false,
  });

  // Sem filtro de estado, escondemos as ainda-pendentes (essas vivem em Decidir).
  const items: DecisionRun[] = (query.data?.items ?? []).filter((d) =>
    filter === 'all' ? d.status !== 'PROPOSED' : true,
  );

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Decisões' }, { label: 'Histórico' }]}
      title="Histórico de decisões"
      subtitle="Decisões já tomadas — aprovadas, rejeitadas e executadas"
      icon={<History className="h-6 w-6" />}
    >
      <div className="mb-4">
        <Segmented<StatusFilter>
          options={FILTER_OPTIONS}
          value={filter}
          onChange={setFilter}
          ariaLabel="Filtrar por estado"
        />
      </div>

      {query.isError ? (
        <DarkCard className="border-danger/30 bg-danger/5">
          <div className="flex items-center gap-3">
            <AlertTriangle size={18} className="text-danger shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-fg-1">Falha ao carregar o histórico</p>
              <p className="text-xs text-fg-3 mt-0.5">
                {(query.error as Error)?.message ?? 'Erro desconhecido'}
              </p>
            </div>
            <DarkButton variant="ghost" icon={<RefreshCw size={13} />} onClick={() => query.refetch()}>
              Tentar novamente
            </DarkButton>
          </div>
        </DarkCard>
      ) : query.isLoading ? (
        <DarkCard className="text-center py-10">
          <p className="text-sm text-fg-3">A carregar histórico…</p>
        </DarkCard>
      ) : items.length === 0 ? (
        <EmptyState
          mascot={false}
          icon={<History size={28} />}
          title="Sem decisões neste filtro"
          hint="As decisões aparecem aqui depois de aprovadas, rejeitadas ou executadas."
        />
      ) : (
        <div className="flex flex-col gap-2">
          {items.map((d) => (
            <DarkCard key={d.id} className="flex items-center justify-between gap-3 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <DarkBadge variant={STATUS_VARIANT[d.status] ?? 'neutral'}>
                    {STATUS_LABEL[d.status] ?? d.status}
                  </DarkBadge>
                  <span className="text-sm font-medium text-fg-1 truncate">{d.title}</span>
                </div>
                <p className="text-xs text-fg-3 mt-1">
                  {d.action_type}
                  {d.proposed_at
                    ? ` · ${new Date(d.proposed_at).toLocaleString('pt-PT')}`
                    : ''}
                </p>
              </div>
            </DarkCard>
          ))}
        </div>
      )}
    </DarkPageLayout>
  );
}
