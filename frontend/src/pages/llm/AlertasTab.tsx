/**
 * AlertasTab — alertas proativos do copiloto (Q.118.J).
 * ======================================================
 *
 * O copiloto deteta anomalias (moldes, faltas de material, risco de qualidade,
 * atrasos) e emite alertas. Esta aba surface-os de forma proativa, com
 * confirmar/resolver. GET /v1/copilot/alerts + POST .../acknowledge|resolve.
 *
 * ZERO MOCKS — empty/error/loading explícitos.
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BellRing, AlertTriangle, RefreshCw, Check, Eye } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkBadge, DarkButton, EmptyState, Segmented } from '../../components/dark';
import { copilotAlertsApi } from '../../lib/api';

type AlertFilter = 'open' | 'all';

const SEV_VARIANT: Record<string, 'danger' | 'warning' | 'info' | 'neutral'> = {
  CRITICAL: 'danger',
  WARN: 'warning',
  INFO: 'info',
};

export function AlertasTab() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<AlertFilter>('open');

  const query = useQuery({
    queryKey: ['copilot', 'alerts', filter],
    queryFn: () => copilotAlertsApi.list(filter === 'open' ? { status: 'open' } : {}),
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ['copilot', 'alerts'] });

  const ackM = useMutation({
    mutationFn: (id: string) => copilotAlertsApi.acknowledge(id),
    onSuccess: invalidate,
  });
  const resolveM = useMutation({
    mutationFn: (id: string) => copilotAlertsApi.resolve(id),
    onSuccess: invalidate,
  });

  const alerts = query.data ?? [];

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'LLM' }, { label: 'Alertas' }]}
      title="Alertas proativos"
      subtitle="Anomalias detectadas pelo copiloto · actualização a cada 30s"
      icon={<BellRing className="h-6 w-6" />}
    >
      <div className="mb-4">
        <Segmented<AlertFilter>
          options={[
            { value: 'open', label: 'Abertos' },
            { value: 'all', label: 'Todos' },
          ]}
          value={filter}
          onChange={setFilter}
          ariaLabel="Filtrar alertas"
        />
      </div>

      {query.isError ? (
        <DarkCard className="border-danger/30 bg-danger/5">
          <div className="flex items-center gap-3">
            <AlertTriangle size={18} className="text-danger shrink-0" />
            <p className="text-sm text-fg-1 flex-1">
              Falha ao carregar alertas: {(query.error as Error)?.message ?? 'erro'}
            </p>
            <DarkButton variant="ghost" icon={<RefreshCw size={13} />} onClick={() => query.refetch()}>
              Tentar novamente
            </DarkButton>
          </div>
        </DarkCard>
      ) : query.isLoading ? (
        <DarkCard className="text-center py-10">
          <p className="text-sm text-fg-3">A carregar alertas…</p>
        </DarkCard>
      ) : alerts.length === 0 ? (
        <EmptyState
          mascot={false}
          icon={<BellRing size={28} />}
          title={filter === 'open' ? 'Sem alertas abertos' : 'Sem alertas'}
          hint="O copiloto avisa-te aqui quando detectar uma anomalia."
        />
      ) : (
        <div className="flex flex-col gap-2">
          {alerts.map((a) => (
            <DarkCard key={a.id} className="flex items-start justify-between gap-3 py-3">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <DarkBadge variant={SEV_VARIANT[a.severity] ?? 'neutral'}>{a.severity}</DarkBadge>
                  <span className="text-sm font-medium text-fg-1">{a.title}</span>
                  <span className="text-[10px] text-fg-3 font-mono">{a.code}</span>
                </div>
                <p className="text-xs text-fg-2 mt-1">{a.message_pt}</p>
              </div>
              {a.status !== 'resolved' ? (
                <div className="flex items-center gap-1.5 shrink-0">
                  {a.status === 'open' ? (
                    <DarkButton
                      variant="ghost"
                      icon={<Eye size={13} />}
                      onClick={() => ackM.mutate(a.id)}
                      disabled={ackM.isPending}
                    >
                      Vi
                    </DarkButton>
                  ) : null}
                  <DarkButton
                    variant="ghost"
                    icon={<Check size={13} />}
                    onClick={() => resolveM.mutate(a.id)}
                    disabled={resolveM.isPending}
                  >
                    Resolver
                  </DarkButton>
                </div>
              ) : (
                <DarkBadge variant="success">Resolvido</DarkBadge>
              )}
            </DarkCard>
          ))}
        </div>
      )}
    </DarkPageLayout>
  );
}
