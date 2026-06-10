// ExpedicaoPage · ListaTab (Q.60.S). ZERO MOCKS — endpoints reais.
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Truck, Check, DownloadCloud, Loader2 } from 'lucide-react';
import { KPIBig, EmptyState } from '../../../components/dark';
import { transportApi, ceoDashboardApi, type TransportBatch, type TransportManifest, type TransportManifestBoat } from '../../../lib/api';
import { transportKeys } from '../../../lib/api/keys';
import { shortDate, type BatchCounts, countManifest } from '../expedicaoShared';
import { ShipmentRow, ShipmentDetail, MoveBoatConfirm } from './listaComponents';

export function ListaTab({
  batches,
  isLoading,
  isError,
  onSync,
  isSyncing,
}: {
  batches: TransportBatch[];
  isLoading: boolean;
  isError: boolean;
  onSync?: () => void;
  isSyncing?: boolean;
}) {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingMove, setPendingMove] = useState<{
    boat: TransportManifestBoat;
    from: TransportBatch;
    to: TransportBatch;
  } | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const sortedBatches = useMemo(
    () =>
      [...batches].sort(
        (a, b) =>
          new Date(a.transport_date).getTime() -
          new Date(b.transport_date).getTime(),
      ),
    [batches],
  );

  const effectiveSelected =
    selectedId ?? (sortedBatches.length > 0 ? sortedBatches[0].id : null);
  const selectedBatch = sortedBatches.find((b) => b.id === effectiveSelected) ?? null;

  // OTD da semana — KPI real.
  const otdQuery = useQuery({
    queryKey: ['expedicao', 'otd'],
    queryFn: () => ceoDashboardApi.otd({ window_days: 7 }),
    staleTime: 120_000,
    retry: 0,
  });

  // Manifesto de cada batch — necessário para os counts da grelha.
  const manifestsQuery = useQuery({
    queryKey: ['expedicao', 'manifests', batches.map((b) => b.id).join(',')],
    queryFn: async () => {
      const entries = await Promise.all(
        batches.map(async (b) => {
          try {
            return [b.id, await transportApi.manifest(b.id)] as const;
          } catch {
            return [b.id, null] as const;
          }
        }),
      );
      return new Map<string, TransportManifest | null>(entries);
    },
    enabled: batches.length > 0,
    staleTime: 60_000,
    retry: 0,
  });

  const countsByBatch = useMemo(() => {
    const map = new Map<string, BatchCounts>();
    const data = manifestsQuery.data;
    if (!data) return map;
    for (const [id, manifest] of data) {
      map.set(id, manifest ? countManifest(manifest.boats) : { ready: 0, inProd: 0, atRisk: 0 });
    }
    return map;
  }, [manifestsQuery.data]);

  const moveMutation = useMutation({
    mutationFn: async (move: {
      boatOrderId: string;
      fromId: string;
      toId: string;
    }) => {
      await transportApi.removeOrder(move.fromId, move.boatOrderId);
      await transportApi.assignOrder(move.toId, move.boatOrderId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: transportKeys.all });
    },
  });

  const confirmMove = (reason: string) => {
    if (!pendingMove) return;
    moveMutation.mutate(
      {
        boatOrderId: pendingMove.boat.order_id,
        fromId: pendingMove.from.id,
        toId: pendingMove.to.id,
      },
      {
        onSuccess: () => {
          setToast(
            `Barco #${pendingMove.boat.hull} movido para ${shortDate(
              pendingMove.to.transport_date,
            )}${reason ? ` · ${reason}` : ''}`,
          );
          setPendingMove(null);
          window.setTimeout(() => setToast(null), 4000);
        },
      },
    );
  };

  // KPIs derivados
  const kpis = useMemo(() => {
    let totalReady = 0;
    let totalAtRisk = 0;
    let partial = 0;
    for (const b of batches) {
      const c = countsByBatch.get(b.id);
      if (c) {
        totalReady += c.ready;
        totalAtRisk += c.atRisk;
      }
      const assigned = b.assigned_orders_count ?? c?.ready ?? 0;
      if (assigned > 0 && assigned < b.truck_capacity_units) partial++;
    }
    return { totalReady, totalAtRisk, partial };
  }, [batches, countsByBatch]);

  if (isLoading) {
    return (
      <div className="px-4 py-12 text-center text-xs text-text-dark-tertiary">
        A carregar expedições…
      </div>
    );
  }
  if (isError) {
    return (
      <div className="px-4 py-12 text-center text-xs text-danger">
        Erro a carregar /v1/plan/transport/batches.
      </div>
    );
  }
  if (batches.length === 0) {
    return (
      <EmptyState
        title="Sem expedições agendadas"
        hint="Sincroniza do ERP para criar os camiões a partir das ordens reais (data de transporte). Idempotente — não desfaz movimentos manuais."
        icon={<Truck size={32} />}
        action={
          onSync ? (
            <button
              type="button"
              onClick={onSync}
              disabled={isSyncing}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-teal-500/15 text-teal-200 hover:bg-teal-500/25 border border-teal-400/25 text-xs font-medium transition-colors disabled:opacity-60"
            >
              {isSyncing ? <Loader2 size={13} className="animate-spin" /> : <DownloadCloud size={13} />}
              {isSyncing ? 'A sincronizar…' : 'Sincronizar do ERP'}
            </button>
          ) : undefined
        }
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
        <KPIBig
          label="OTD · semana"
          value={otdQuery.data ? Math.round(otdQuery.data.otd_pct) : '—'}
          unit="%"
          context={
            otdQuery.data
              ? `${otdQuery.data.on_time}/${otdQuery.data.total} a tempo · meta 95%`
              : 'Sem dados de entregas'
          }
          target={95}
          status={
            otdQuery.data && otdQuery.data.otd_pct >= 95
              ? 'green'
              : otdQuery.data && otdQuery.data.otd_pct >= 85
                ? 'yellow'
                : 'red'
          }
          accent="green"
        />
        <KPIBig
          label="Camiões parciais"
          value={kpis.partial}
          context={
            kpis.partial > 0
              ? `${kpis.partial} abaixo da capacidade`
              : 'Todos os camiões cheios'
          }
          status={kpis.partial > 1 ? 'orange' : 'green'}
          accent="orange"
        />
        <KPIBig
          label="Barcos em risco"
          value={kpis.totalAtRisk}
          context={
            kpis.totalAtRisk > 0
              ? 'Atrasos de expedição identificados'
              : 'Nenhum barco em risco'
          }
          status={kpis.totalAtRisk > 3 ? 'red' : kpis.totalAtRisk > 0 ? 'yellow' : 'green'}
          accent="red"
        />
        <KPIBig
          label="Prontos em armazém"
          value={kpis.totalReady}
          context={
            manifestsQuery.isLoading
              ? 'A somar manifestos…'
              : 'Soma de barcos prontos em camiões activos'
          }
          status={kpis.totalReady > 0 ? 'green' : 'gray'}
          accent="green"
        />
      </div>

      {/* Split-pane */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.1fr] gap-3.5 min-h-[480px]">
        {/* Esquerda — lista de camiões (drop targets) */}
        <div>
          <div
            style={{
              fontSize: 10.5,
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
              fontWeight: 600,
              marginBottom: 10,
            }}
          >
            {batches.length} expedições
          </div>
          <div className="flex flex-col gap-2">
            {sortedBatches.map((b) => (
              <ShipmentRow
                key={b.id}
                batch={b}
                counts={countsByBatch.get(b.id) ?? { ready: 0, inProd: 0, atRisk: 0 }}
                active={b.id === effectiveSelected}
                onClick={() => setSelectedId(b.id)}
                onDropBoat={(payload) => {
                  if (!selectedBatch || payload.batchId === b.id) return;
                  setPendingMove({
                    boat: payload.boat,
                    from: selectedBatch,
                    to: b,
                  });
                }}
              />
            ))}
          </div>
        </div>

        {/* Direita — manifesto da expedição seleccionada */}
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-lg)',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {selectedBatch ? (
            <ShipmentDetail batch={selectedBatch} />
          ) : (
            <div
              style={{
                padding: 40,
                textAlign: 'center',
                color: 'var(--fg-3)',
                fontSize: 13,
              }}
            >
              Selecciona uma expedição para ver os barcos
            </div>
          )}
        </div>
      </div>

      {pendingMove ? (
        <MoveBoatConfirm
          pending={pendingMove}
          isPending={moveMutation.isPending}
          isError={moveMutation.isError}
          onConfirm={confirmMove}
          onCancel={() => setPendingMove(null)}
        />
      ) : null}

      {toast ? (
        <div
          className="anim-up"
          style={{
            position: 'fixed',
            bottom: 24,
            left: '50%',
            transform: 'translateX(-50%)',
            padding: '12px 18px',
            background: 'rgba(18,18,22,0.95)',
            backdropFilter: 'blur(20px)',
            border: '1px solid var(--green-bd)',
            borderRadius: 'var(--r-lg)',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            boxShadow: 'var(--shadow-3)',
            zIndex: 150,
          }}
        >
          <Check size={14} color="var(--green)" />
          <span style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
            {toast}
          </span>
        </div>
      ) : null}
    </div>
  );
}
