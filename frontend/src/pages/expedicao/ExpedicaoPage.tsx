/**
 * ExpedicaoPage — reconstrução fiel do protótipo NELO (page-expedicao.jsx).
 *
 * Sprint Q.52.J · Onda 1 · Track T4.
 *
 * Tabs:
 *   • Expedições — 4 KPIs + split-pane (lista de camiões à esquerda /
 *     manifesto à direita). Arrastar um barco do manifesto para outra
 *     expedição na lista abre o `MoveBoatConfirm` (ConsequenceBox); ao
 *     confirmar faz removeOrder+assignOrder reais.
 *   • CTP · novo pedido — Capable-to-Promise "encaixa-em-camião". SEM
 *     endpoint no backend (gap Q.53) → empty state explícito com a razão.
 *   • Encomendas activas — tabela de barcos activos.
 *
 * Endpoints reais (plano Q.52.J):
 *   - GET  /v1/plan/transport/batches            (transportApi.listBatches)
 *   - GET  /v1/plan/transport/batches/{id}/manifest (transportApi.manifest)
 *   - POST /v1/plan/transport/batches/{id}/orders   (transportApi.assignOrder)
 *   - DELETE .../orders/{id}                        (transportApi.removeOrder)
 *   - POST .../freeze · .../dispatch
 *   - GET  /v1/profit/otd                           (ceoDashboardApi.otd) — KPI
 *
 * ZERO MOCKS — counts derivam do manifesto real; CTP é empty state honesto.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Truck,
  Target,
  Flag,
  RefreshCw,
  GripVertical,
  Check,
  X,
  Snowflake,
  Send,
  CalendarClock,
  PackageCheck,
  AlertTriangle,
  CircleSlash,
} from 'lucide-react';
import {
  PageHeader,
  Tabs,
  KPIBig,
  EmptyState,
  useDraggable,
  useDropZone,
} from '../../components/dark';
import { TruckGrid } from '../../components/expedicao/TruckGrid';
import {
  transportApi,
  ceoDashboardApi,
  type TransportBatch,
  type TransportManifest,
  type TransportManifestBoat,
} from '../../lib/api';
import {
  expedicaoCtpApi,
  type CtpBoat,
  type CtpResponse,
} from './expedicaoCtpApi';

// ─── Helpers ────────────────────────────────────────────────────────────────

function dayLabel(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  const days = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
  return days[d.getDay()];
}

function shortDate(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

function daysUntil(iso: string): number {
  const t = new Date(iso + 'T00:00:00').getTime();
  const today = new Date().setHours(0, 0, 0, 0);
  return Math.round((t - today) / (1000 * 60 * 60 * 24));
}

/** Estado de um barco do manifesto → classificação para a grelha. */
function classifyBoat(b: TransportManifestBoat): 'ready' | 'at_risk' | 'in_prod' {
  const s = (b.status ?? '').toUpperCase();
  if (s === 'COMPLETED' || s === 'READY' || s === 'DISPATCHED') return 'ready';
  const phase = (b.current_phase ?? '').toLowerCase();
  if (phase.includes('cq') || phase.includes('expedi')) return 'ready';
  if (s === 'AT_RISK' || s === 'LATE' || s === 'DELAYED') return 'at_risk';
  return 'in_prod';
}

interface BatchCounts {
  ready: number;
  inProd: number;
  atRisk: number;
}

function countManifest(boats: TransportManifestBoat[]): BatchCounts {
  let ready = 0;
  let atRisk = 0;
  let inProd = 0;
  for (const b of boats) {
    const c = classifyBoat(b);
    if (c === 'ready') ready++;
    else if (c === 'at_risk') {
      atRisk++;
      inProd++;
    } else inProd++;
  }
  return { ready, inProd, atRisk };
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════

type TabId = 'lista' | 'ctp' | 'activas';

export default function ExpedicaoPage() {
  const [tab, setTab] = useState<TabId>('lista');

  const batchesQuery = useQuery({
    queryKey: ['expedicao', 'batches'],
    queryFn: () => transportApi.listBatches(),
    staleTime: 60_000,
    retry: 0,
  });
  const batches = useMemo(() => batchesQuery.data ?? [], [batchesQuery.data]);

  const tabs = [
    { id: 'lista', label: 'Expedições', icon: <Truck size={13} /> },
    { id: 'ctp', label: 'CTP · novo pedido', icon: <Target size={13} /> },
    {
      id: 'activas',
      label: 'Encomendas activas',
      icon: <Flag size={13} />,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Expedição"
        subtitle="Camiões de 50 lugares · arrasta barcos entre expedições · CTP encaixa em camiões existentes"
        helpId="expedicao"
        actions={
          <button
            type="button"
            onClick={() => batchesQuery.refetch()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
          >
            <RefreshCw size={13} />
            Atualizar
          </button>
        }
      />

      <div className="px-6 pt-2">
        <Tabs
          tabs={tabs}
          value={tab}
          onChange={(id) => setTab(id as TabId)}
        />
      </div>

      <div className="px-6 py-4 page-enter">
        {tab === 'lista' && (
          <ListaTab
            batches={batches}
            isLoading={batchesQuery.isLoading}
            isError={batchesQuery.isError}
          />
        )}
        {tab === 'ctp' && (
          <CTPTab
            batches={batches}
            batchesLoading={batchesQuery.isLoading}
          />
        )}
        {tab === 'activas' && (
          <ActivasTab
            batches={batches}
            isLoading={batchesQuery.isLoading}
            isError={batchesQuery.isError}
          />
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ListaTab — KPIs + split-pane drag-and-drop
// ═══════════════════════════════════════════════════════════════════════════

function ListaTab({
  batches,
  isLoading,
  isError,
}: {
  batches: TransportBatch[];
  isLoading: boolean;
  isError: boolean;
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
      queryClient.invalidateQueries({ queryKey: ['expedicao'] });
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
        hint="Cria um camião para o próximo cliente no ERP."
        icon={<Truck size={32} />}
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
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
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1.1fr',
          gap: 14,
          minHeight: 480,
        }}
      >
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

// ─── ShipmentRow — cartão de camião na lista (drop target) ──────────────────

interface BoatDragData {
  boat: TransportManifestBoat;
  batchId: string;
}

function ShipmentRow({
  batch,
  counts,
  active,
  onClick,
  onDropBoat,
}: {
  batch: TransportBatch;
  counts: BatchCounts;
  active: boolean;
  onClick: () => void;
  onDropBoat: (payload: BoatDragData) => void;
}) {
  const { dropProps, isOver } = useDropZone<BoatDragData>({
    accept: 'boat',
    onDrop: (p) => onDropBoat(p.data),
  });

  const assigned = batch.assigned_orders_count ?? counts.ready + counts.inProd;
  const truckPct = assigned / batch.truck_capacity_units;
  const dx = daysUntil(batch.transport_date);

  return (
    <div
      {...dropProps}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick();
      }}
      style={{
        padding: '14px 16px',
        background: isOver
          ? 'var(--accent-bg)'
          : active
            ? 'var(--bg-3)'
            : 'var(--bg-1)',
        border: `1px solid ${
          isOver ? 'var(--accent-bd)' : active ? 'var(--bd-3)' : 'var(--bd-1)'
        }`,
        boxShadow: isOver ? '0 0 0 2px var(--accent-bd) inset' : 'none',
        borderRadius: 'var(--r-md)',
        cursor: 'pointer',
        transition: 'background 0.15s, border-color 0.15s',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 10,
          gap: 12,
        }}
      >
        <div>
          <div
            style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}
          >
            <span
              className="tabular display"
              style={{
                fontSize: 18,
                fontWeight: 500,
                color: 'var(--fg-0)',
                letterSpacing: -0.2,
              }}
            >
              {shortDate(batch.transport_date)}
            </span>
            <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              {dayLabel(batch.transport_date)}
            </span>
            {dx >= 0 && dx <= 7 ? (
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: dx <= 1 ? 'var(--red)' : dx <= 3 ? 'var(--yellow)' : 'var(--green)',
                }}
              >
                D−{dx}
              </span>
            ) : null}
            {counts.atRisk > 0 ? <RowTag tone="yellow">{counts.atRisk} em risco</RowTag> : null}
            {truckPct > 0 && truckPct < 1 ? (
              <RowTag tone="blue">incompleto</RowTag>
            ) : null}
            <RowTag tone={batch.status === 'OPEN' ? 'neutral' : 'green'}>
              {batch.status === 'OPEN'
                ? 'aberto'
                : batch.status === 'FROZEN'
                  ? 'congelado'
                  : 'expedido'}
            </RowTag>
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--fg-1)' }}>{batch.code}</div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>
            → {batch.destination ?? 'destino por definir'}
          </div>
        </div>
        <TruckGrid
          ready={counts.ready}
          inProd={counts.inProd}
          atRisk={counts.atRisk}
          total={batch.truck_capacity_units}
        />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          alignItems: 'baseline',
          gap: 12,
          fontSize: 11,
        }}
      >
        <span>
          <span style={{ color: 'var(--fg-3)' }}>prontos </span>
          <span className="tabular" style={{ color: 'var(--green)', fontWeight: 600 }}>
            {counts.ready}
          </span>
        </span>
        <span>
          <span style={{ color: 'var(--fg-3)' }}>produção </span>
          <span className="tabular" style={{ color: 'var(--fg-1)', fontWeight: 600 }}>
            {counts.inProd}
          </span>
        </span>
        <span>
          <span style={{ color: 'var(--fg-3)' }}>camião </span>
          <span
            className="tabular"
            style={{
              color: truckPct < 0.5 ? 'var(--yellow)' : 'var(--accent)',
              fontWeight: 600,
            }}
          >
            {assigned}/{batch.truck_capacity_units}
          </span>
        </span>
      </div>
    </div>
  );
}

function RowTag({
  tone,
  children,
}: {
  tone: 'yellow' | 'blue' | 'green' | 'neutral';
  children: React.ReactNode;
}) {
  const bg = tone === 'neutral' ? 'var(--bg-3)' : `var(--${tone}-bg)`;
  const bd = tone === 'neutral' ? 'var(--bd-1)' : `var(--${tone}-bd)`;
  const fg = tone === 'neutral' ? 'var(--fg-2)' : `var(--${tone})`;
  return (
    <span
      style={{
        fontSize: 9.5,
        padding: '1px 6px',
        background: bg,
        border: `1px solid ${bd}`,
        borderRadius: 4,
        color: fg,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: 0.3,
      }}
    >
      {children}
    </span>
  );
}

// ─── ShipmentDetail — manifesto da expedição seleccionada ───────────────────

function ShipmentDetail({ batch }: { batch: TransportBatch }) {
  const queryClient = useQueryClient();
  const manifestQuery = useQuery({
    queryKey: ['expedicao', 'manifest', batch.id],
    queryFn: () => transportApi.manifest(batch.id),
    retry: 0,
  });
  const manifest = manifestQuery.data;
  const counts = manifest
    ? countManifest(manifest.boats)
    : { ready: 0, inProd: 0, atRisk: 0 };

  const freezeMutation = useMutation({
    mutationFn: () => transportApi.freeze(batch.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['expedicao'] }),
  });
  const dispatchMutation = useMutation({
    mutationFn: () => transportApi.dispatch(batch.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['expedicao'] }),
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            justifyContent: 'space-between',
            marginBottom: 6,
            gap: 12,
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
              <span
                className="display tabular"
                style={{
                  fontSize: 22,
                  fontWeight: 500,
                  color: 'var(--fg-0)',
                  letterSpacing: -0.3,
                }}
              >
                {shortDate(batch.transport_date)}
              </span>
              <span style={{ fontSize: 13, color: 'var(--fg-2)' }}>
                {dayLabel(batch.transport_date)}
              </span>
            </div>
            <div style={{ fontSize: 12, color: 'var(--fg-1)', marginTop: 3 }}>
              {batch.code}
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              → {batch.destination ?? 'destino por definir'}
            </div>
          </div>
          <TruckGrid
            ready={counts.ready}
            inProd={counts.inProd}
            atRisk={counts.atRisk}
            total={batch.truck_capacity_units}
          />
        </div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--fg-3)',
            marginTop: 4,
          }}
        >
          {manifest ? `${manifest.boat_count} barcos no manifesto` : '—'}
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 14 }}>
        <div
          style={{
            fontSize: 10.5,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
            marginBottom: 8,
          }}
        >
          Barcos · arrasta para outra expedição
        </div>
        {manifestQuery.isLoading ? (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            A carregar manifesto…
          </div>
        ) : manifestQuery.isError ? (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--danger)', fontSize: 12 }}>
            Erro a carregar o manifesto.
          </div>
        ) : !manifest || manifest.boats.length === 0 ? (
          <div style={{ padding: 20, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            Sem barcos atribuídos a esta expedição.
          </div>
        ) : (
          manifest.boats.map((b) => (
            <BoatTile key={b.order_id} boat={b} batchId={batch.id} />
          ))
        )}
      </div>

      <div
        style={{
          padding: '12px 18px',
          borderTop: '1px solid var(--bd-1)',
          display: 'flex',
          justifyContent: 'flex-end',
          gap: 8,
        }}
      >
        {batch.status === 'OPEN' ? (
          <button
            type="button"
            onClick={() => freezeMutation.mutate()}
            disabled={freezeMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors disabled:opacity-50"
            style={{
              background: 'var(--bg-2)',
              color: 'var(--fg-0)',
              border: '1px solid var(--bd-2)',
            }}
          >
            <Snowflake size={12} />
            {freezeMutation.isPending ? 'A congelar…' : 'Congelar manifesto'}
          </button>
        ) : null}
        {batch.status === 'FROZEN' ? (
          <button
            type="button"
            onClick={() => dispatchMutation.mutate()}
            disabled={dispatchMutation.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-white transition-colors disabled:opacity-50"
            style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
          >
            <Send size={12} />
            {dispatchMutation.isPending ? 'A expedir…' : 'Expedir camião'}
          </button>
        ) : null}
        {batch.status === 'DISPATCHED' ? (
          <span style={{ fontSize: 12, color: 'var(--green)', fontWeight: 500 }}>
            ● Camião já expedido
          </span>
        ) : null}
      </div>
    </div>
  );
}

// ─── BoatTile — barco arrastável dentro do manifesto ────────────────────────

function BoatTile({
  boat,
  batchId,
}: {
  boat: TransportManifestBoat;
  batchId: string;
}) {
  const { dragProps, dragging } = useDraggable<BoatDragData>({
    kind: 'boat',
    data: { boat, batchId },
  });
  const cls = classifyBoat(boat);
  const color =
    cls === 'ready' ? 'green' : cls === 'at_risk' ? 'yellow' : 'fg-3';

  return (
    <div
      {...dragProps}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 11px',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-sm)',
        cursor: 'grab',
        marginBottom: 4,
        opacity: dragging ? 0.4 : 1,
        transition: 'opacity 0.12s',
      }}
    >
      <GripVertical size={12} color="var(--fg-3)" />
      <span
        style={{
          width: 3,
          height: 24,
          background: `var(--${color})`,
          borderRadius: 2,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--fg-0)', fontWeight: 500 }}>
            #{boat.hull}{' '}
            <span style={{ color: 'var(--fg-3)', fontWeight: 400 }}>
              {boat.product_type}
            </span>
          </span>
          <span style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>{boat.status}</span>
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--fg-2)', marginTop: 2 }}>
          {boat.product_name} · {boat.current_phase}
        </div>
      </div>
    </div>
  );
}

// ─── MoveBoatConfirm — ConsequenceBox de arrasto ────────────────────────────

function MoveBoatConfirm({
  pending,
  isPending,
  isError,
  onConfirm,
  onCancel,
}: {
  pending: { boat: TransportManifestBoat; from: TransportBatch; to: TransportBatch };
  isPending: boolean;
  isError: boolean;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [reason, setReason] = useState('');
  const earlier = pending.to.transport_date < pending.from.transport_date;
  const deltaDays = Math.abs(
    Math.round(
      (new Date(pending.to.transport_date).getTime() -
        new Date(pending.from.transport_date).getTime()) /
        86_400_000,
    ),
  );

  return (
    <div
      className="anim-up"
      style={{
        position: 'fixed',
        bottom: 20,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 200,
        width: 560,
        maxWidth: '92vw',
      }}
    >
      <div
        style={{
          background: 'rgba(18,18,22,0.98)',
          backdropFilter: 'blur(20px)',
          border: '1px solid var(--bd-3)',
          borderRadius: 'var(--r-lg)',
          boxShadow: 'var(--shadow-3)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--bd-1)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <Truck size={14} color="var(--accent)" />
          <span style={{ fontSize: 13, color: 'var(--fg-0)', fontWeight: 500 }}>
            Mover #{pending.boat.hull} · {pending.boat.product_type}
          </span>
          <span style={{ fontSize: 11.5, color: 'var(--fg-3)', marginLeft: 'auto' }}>
            {shortDate(pending.from.transport_date)} → {shortDate(pending.to.transport_date)}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
          <div
            style={{
              padding: 12,
              borderRight: '1px solid var(--bd-1)',
              background: 'var(--green-bg)',
            }}
          >
            <div
              style={{
                fontSize: 10.5,
                color: 'var(--green)',
                textTransform: 'uppercase',
                letterSpacing: 0.4,
                fontWeight: 600,
                marginBottom: 6,
              }}
            >
              Se mover
            </div>
            <ul
              style={{
                margin: 0,
                paddingLeft: 14,
                fontSize: 11.5,
                color: 'var(--fg-1)',
                lineHeight: 1.6,
              }}
            >
              <li>
                Cliente recebe {deltaDays} dia{deltaDays !== 1 ? 's' : ''}{' '}
                {earlier ? 'mais cedo' : 'mais tarde'}
              </li>
              <li>{pending.from.code}: liberta 1 lugar</li>
              <li>{pending.to.code}: ocupa mais 1 lugar</li>
            </ul>
          </div>
          <div style={{ padding: 12, background: 'var(--red-bg)' }}>
            <div
              style={{
                fontSize: 10.5,
                color: 'var(--red)',
                textTransform: 'uppercase',
                letterSpacing: 0.4,
                fontWeight: 600,
                marginBottom: 6,
              }}
            >
              Riscos
            </div>
            <ul
              style={{
                margin: 0,
                paddingLeft: 14,
                fontSize: 11.5,
                color: 'var(--fg-1)',
                lineHeight: 1.6,
              }}
            >
              {earlier ? (
                <li>Pode forçar horas extra para acabar a tempo</li>
              ) : (
                <li>Avisar o cliente da nova data</li>
              )}
              {(pending.to.assigned_orders_count ?? 0) + 1 >
              pending.to.truck_capacity_units ? (
                <li>Camião excede a capacidade · precisa de 2º</li>
              ) : null}
              <li>Reagendar a logística</li>
            </ul>
          </div>
        </div>

        <div
          style={{
            padding: '10px 14px',
            background: 'var(--bg-2)',
            borderTop: '1px solid var(--bd-1)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Porquê esta mudança? (opcional)"
            className="text-slate-900 placeholder:text-slate-400"
            style={{
              flex: 1,
              padding: '5px 10px',
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 6,
              color: 'var(--fg-0)',
              fontSize: 11.5,
              outline: 'none',
            }}
          />
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
            style={{ background: 'transparent', color: 'var(--fg-2)' }}
          >
            <X size={11} />
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => onConfirm(reason)}
            disabled={isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold text-white transition-colors disabled:opacity-50"
            style={{ background: 'var(--green)' }}
          >
            <Check size={11} />
            {isPending ? 'A mover…' : 'Confirmar'}
          </button>
        </div>
        {isError ? (
          <div
            style={{
              padding: '6px 14px',
              background: 'var(--red-bg)',
              borderTop: '1px solid var(--red-bd)',
              fontSize: 11,
              color: 'var(--red)',
            }}
          >
            Não foi possível mover o barco. Tenta outra vez.
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CTPTab — Capable to Promise · POST /v1/plan/ctp (Q.53.B)
// ═══════════════════════════════════════════════════════════════════════════

/** ISO de hoje, YYYY-MM-DD — default do campo de data. */
function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function CTPTab({
  batches,
  batchesLoading,
}: {
  batches: TransportBatch[];
  batchesLoading: boolean;
}) {
  // Pré-preenche com o camião aberto mais próximo, se houver.
  const openBatches = useMemo(
    () =>
      [...batches]
        .filter((b) => b.status === 'OPEN')
        .sort(
          (a, b) =>
            new Date(a.transport_date).getTime() -
            new Date(b.transport_date).getTime(),
        ),
    [batches],
  );

  const [truckDate, setTruckDate] = useState('');
  const [capacity, setCapacity] = useState('6');
  const [startFrom, setStartFrom] = useState('');

  // Resultado da última avaliação — mutation porque o CTP só *computa*
  // a pedido (não é uma query reactiva a parâmetros de URL).
  const ctpMutation = useMutation({
    mutationFn: (vars: {
      truck_date: string;
      truck_capacity: number;
      start_from?: string;
    }) => expedicaoCtpApi.evaluate(vars),
  });

  const result = ctpMutation.data ?? null;

  const capacityNum = Number(capacity);
  const dateValid = truckDate.length === 10;
  const capacityValid =
    Number.isFinite(capacityNum) && capacityNum >= 1 && capacityNum <= 100;
  const canSubmit = dateValid && capacityValid && !ctpMutation.isPending;

  const applyBatch = (b: TransportBatch) => {
    setTruckDate(b.transport_date.slice(0, 10));
    setCapacity(String(b.truck_capacity_units));
  };

  const runCtp = () => {
    if (!canSubmit) return;
    ctpMutation.mutate({
      truck_date: truckDate,
      truck_capacity: capacityNum,
      start_from: startFrom || undefined,
    });
  };

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '320px 1fr',
        gap: 14,
        alignItems: 'start',
      }}
    >
      {/* ─── Esquerda — formulário do pedido ─────────────────────────── */}
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--bd-1)',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 7,
              background: 'var(--bg-3)',
              border: '1px solid var(--bd-2)',
              display: 'grid',
              placeItems: 'center',
              color: 'var(--accent)',
            }}
          >
            <Target size={14} />
          </div>
          <div>
            <div className="display" style={{ fontSize: 14, fontWeight: 500 }}>
              CTP · Capable to Promise
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
              Que barcos encaixam num camião/data
            </div>
          </div>
        </div>

        <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Atalhos — camiões abertos */}
          {batchesLoading ? (
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              A carregar camiões…
            </div>
          ) : openBatches.length > 0 ? (
            <div>
              <FieldLabel>Usar camião aberto</FieldLabel>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {openBatches.slice(0, 6).map((b) => (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => applyBatch(b)}
                    style={{
                      fontSize: 10.5,
                      padding: '3px 9px',
                      borderRadius: 999,
                      background:
                        truckDate === b.transport_date.slice(0, 10)
                          ? 'var(--accent-bg)'
                          : 'var(--bg-3)',
                      border: `1px solid ${
                        truckDate === b.transport_date.slice(0, 10)
                          ? 'var(--accent-bd)'
                          : 'var(--bd-1)'
                      }`,
                      color: 'var(--fg-1)',
                      cursor: 'pointer',
                    }}
                  >
                    {shortDate(b.transport_date)} · {b.code}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div>
            <FieldLabel>Data de partida do camião</FieldLabel>
            <input
              type="date"
              value={truckDate}
              min={todayIso()}
              onChange={(e) => setTruckDate(e.target.value)}
              className="text-slate-900"
              style={ctpInputStyle}
            />
          </div>

          <div>
            <FieldLabel>Capacidade (slots)</FieldLabel>
            <input
              type="number"
              min={1}
              max={100}
              value={capacity}
              onChange={(e) => setCapacity(e.target.value)}
              className="text-slate-900 placeholder:text-slate-400"
              style={ctpInputStyle}
            />
            {!capacityValid && capacity !== '' ? (
              <div style={{ fontSize: 10, color: 'var(--red)', marginTop: 3 }}>
                Capacidade entre 1 e 100.
              </div>
            ) : null}
          </div>

          <div>
            <FieldLabel>Produção pode começar (opcional)</FieldLabel>
            <input
              type="date"
              value={startFrom}
              onChange={(e) => setStartFrom(e.target.value)}
              className="text-slate-900"
              style={ctpInputStyle}
            />
            <div style={{ fontSize: 10, color: 'var(--fg-3)', marginTop: 3 }}>
              Vazio → assume hoje.
            </div>
          </div>

          <button
            type="button"
            onClick={runCtp}
            disabled={!canSubmit}
            className="inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md text-xs font-semibold text-white transition-colors disabled:opacity-50"
            style={{ background: 'var(--accent)' }}
          >
            <Target size={12} />
            {ctpMutation.isPending ? 'A calcular…' : 'Calcular encaixe'}
          </button>

          {ctpMutation.isError ? (
            <div
              style={{
                fontSize: 11,
                color: 'var(--red)',
                background: 'var(--red-bg)',
                border: '1px solid var(--red-bd)',
                borderRadius: 6,
                padding: '6px 9px',
              }}
            >
              Não foi possível calcular o CTP. Confirma a data e tenta outra
              vez.
            </div>
          ) : null}
        </div>
      </div>

      {/* ─── Direita — painel de sugestão ────────────────────────────── */}
      <div>
        {ctpMutation.isPending ? (
          <div
            style={{
              padding: 48,
              textAlign: 'center',
              color: 'var(--fg-3)',
              fontSize: 12,
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-lg)',
            }}
          >
            A avaliar barcos contra a data do camião…
          </div>
        ) : result ? (
          <CTPResultPanel result={result} />
        ) : (
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-lg)',
              padding: 8,
            }}
          >
            <EmptyState
              title="Escolhe um camião e uma data"
              hint="Indica a data de partida e a capacidade do camião — o CTP avalia cada barco em curso (data viável, capacidade, materiais, molde) e diz quais podes prometer."
              icon={<Target size={32} />}
            />
          </div>
        )}
      </div>
    </div>
  );
}

const ctpInputStyle: React.CSSProperties = {
  width: '100%',
  padding: '6px 10px',
  background: 'white',
  border: '1px solid var(--bd-2)',
  borderRadius: 6,
  fontSize: 12,
  outline: 'none',
};

function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10,
        color: 'var(--fg-3)',
        textTransform: 'uppercase',
        letterSpacing: 0.4,
        fontWeight: 600,
        marginBottom: 5,
      }}
    >
      {children}
    </div>
  );
}

// ─── CTPResultPanel — sugestão do CTP ───────────────────────────────────────

function CTPResultPanel({ result }: { result: CtpResponse }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Resumo */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 8,
        }}
      >
        <CTPSummaryCell
          label="Slots usados"
          value={`${result.slots_used}/${result.truck_capacity}`}
          tone="accent"
        />
        <CTPSummaryCell
          label="Encaixam"
          value={result.summary.n_committable}
          tone="green"
        />
        <CTPSummaryCell
          label="Em risco"
          value={result.summary.n_at_risk}
          tone={result.summary.n_at_risk > 0 ? 'yellow' : 'fg-2'}
        />
        <CTPSummaryCell
          label="Não chegam"
          value={result.summary.n_rejected}
          tone={result.summary.n_rejected > 0 ? 'red' : 'fg-2'}
        />
      </div>

      <CTPBoatGroup
        icon={<PackageCheck size={13} color="var(--green)" />}
        title="Encaixam no camião"
        subtitle={`Data viável, capacidade e materiais OK · partida ${shortDate(result.truck_date)}`}
        boats={result.committable}
        tone="green"
        emptyHint="Nenhum barco encaixa neste camião com estes parâmetros. Tenta uma data mais tarde ou outra capacidade."
      />

      {result.at_risk.length > 0 ? (
        <CTPBoatGroup
          icon={<AlertTriangle size={13} color="var(--yellow)" />}
          title="Encaixam mas com risco"
          subtitle="Data viável, mas falta material — decisão do planeador"
          boats={result.at_risk}
          tone="yellow"
        />
      ) : null}

      {result.rejected.length > 0 ? (
        <CTPBoatGroup
          icon={<CircleSlash size={13} color="var(--fg-3)" />}
          title="Não chegam a tempo"
          subtitle="A data sugerida de expedição é depois da partida do camião"
          boats={result.rejected}
          tone="neutral"
        />
      ) : null}
    </div>
  );
}

function CTPSummaryCell({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone: 'accent' | 'green' | 'yellow' | 'red' | 'fg-2';
}) {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        padding: '10px 12px',
      }}
    >
      <div
        style={{
          fontSize: 9.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        className="tabular display"
        style={{ fontSize: 20, fontWeight: 500, color: `var(--${tone})` }}
      >
        {value}
      </div>
    </div>
  );
}

function CTPBoatGroup({
  icon,
  title,
  subtitle,
  boats,
  tone,
  emptyHint,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  boats: CtpBoat[];
  tone: 'green' | 'yellow' | 'neutral';
  emptyHint?: string;
}) {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--bd-1)',
          display: 'flex',
          alignItems: 'center',
          gap: 9,
        }}
      >
        {icon}
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
            {title}{' '}
            <span
              className="tabular"
              style={{ color: 'var(--fg-3)', fontWeight: 400 }}
            >
              ({boats.length})
            </span>
          </div>
          <div style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>{subtitle}</div>
        </div>
      </div>
      {boats.length === 0 ? (
        <div
          style={{
            padding: 16,
            fontSize: 11.5,
            color: 'var(--fg-3)',
            textAlign: 'center',
          }}
        >
          {emptyHint ?? 'Sem barcos neste grupo.'}
        </div>
      ) : (
        <div style={{ padding: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {boats.map((b) => (
            <CTPBoatRow key={b.order_id} boat={b} tone={tone} />
          ))}
        </div>
      )}
    </div>
  );
}

function CTPBoatRow({
  boat,
  tone,
}: {
  boat: CtpBoat;
  tone: 'green' | 'yellow' | 'neutral';
}) {
  const stripe =
    tone === 'green' ? 'green' : tone === 'yellow' ? 'yellow' : 'fg-3';
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 11px',
        background: 'var(--bg-2)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-sm)',
      }}
    >
      <span
        style={{
          width: 3,
          height: 28,
          background: `var(--${stripe})`,
          borderRadius: 2,
        }}
      />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <span style={{ fontSize: 12, color: 'var(--fg-0)', fontWeight: 500 }}>
            {boat.hull ? `#${boat.hull}` : 'Ordem'}{' '}
            <span style={{ color: 'var(--fg-3)', fontWeight: 400 }}>
              {boat.product_type ?? ''}
            </span>
          </span>
          <span
            className="tabular"
            style={{
              fontSize: 10.5,
              color: 'var(--fg-2)',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
            }}
          >
            <CalendarClock size={10} color="var(--fg-3)" />
            {boat.suggested_shipment
              ? shortDate(boat.suggested_shipment)
              : 'sem data'}
          </span>
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--fg-2)', marginTop: 2 }}>
          {boat.product_name ?? 'produto por definir'}
          {boat.lead_time !== null ? ` · lead-time ${boat.lead_time}` : ''}
        </div>
        {/* Razões — porque é que o barco está neste grupo */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 5,
            marginTop: 5,
          }}
        >
          <CTPReason ok={boat.date_feasible}>
            {boat.date_feasible ? 'data viável' : 'data inviável'}
          </CTPReason>
          <CTPReason ok={boat.materials_ok}>
            {boat.materials_ok
              ? 'materiais OK'
              : `falta material${
                  boat.missing_materials.length > 0
                    ? ` (${boat.missing_materials.length})`
                    : ''
                }`}
          </CTPReason>
          {boat.risk ? <CTPReason ok={false}>{boat.risk}</CTPReason> : null}
        </div>
      </div>
    </div>
  );
}

function CTPReason({
  ok,
  children,
}: {
  ok: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      style={{
        fontSize: 9.5,
        padding: '1px 6px',
        borderRadius: 4,
        background: ok ? 'var(--green-bg)' : 'var(--red-bg)',
        border: `1px solid ${ok ? 'var(--green-bd)' : 'var(--red-bd)'}`,
        color: ok ? 'var(--green)' : 'var(--red)',
        fontWeight: 600,
      }}
    >
      {children}
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ActivasTab — encomendas activas por camião
// ═══════════════════════════════════════════════════════════════════════════

function ActivasTab({
  batches,
  isLoading,
  isError,
}: {
  batches: TransportBatch[];
  isLoading: boolean;
  isError: boolean;
}) {
  if (isLoading) {
    return (
      <div className="px-4 py-12 text-center text-xs text-text-dark-tertiary">
        A carregar encomendas…
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
        title="Sem encomendas activas"
        hint="Não há camiões agendados de momento."
        icon={<Flag size={32} />}
      />
    );
  }

  const sorted = [...batches].sort(
    (a, b) =>
      new Date(a.transport_date).getTime() - new Date(b.transport_date).getTime(),
  );

  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.4fr 1fr 120px 120px 120px',
          alignItems: 'center',
          padding: '12px 18px',
          borderBottom: '1px solid var(--bd-1)',
          background: 'var(--bg-2)',
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
        }}
      >
        <div>Camião</div>
        <div>Destino</div>
        <div>Data</div>
        <div>Capacidade</div>
        <div>Estado</div>
      </div>
      {sorted.map((b, i) => (
        <div
          key={b.id}
          style={{
            display: 'grid',
            gridTemplateColumns: '1.4fr 1fr 120px 120px 120px',
            alignItems: 'center',
            padding: '12px 18px',
            borderBottom:
              i < sorted.length - 1 ? '1px solid var(--bd-1)' : 'none',
          }}
        >
          <div style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
            {b.code}
          </div>
          <div style={{ fontSize: 12, color: 'var(--fg-2)' }}>
            {b.destination ?? '—'}
          </div>
          <div className="tabular" style={{ fontSize: 12, color: 'var(--fg-1)' }}>
            {shortDate(b.transport_date)}
          </div>
          <div className="tabular" style={{ fontSize: 12, color: 'var(--fg-1)' }}>
            {b.assigned_orders_count ?? 0}/{b.truck_capacity_units}
          </div>
          <div>
            <RowTag tone={b.status === 'OPEN' ? 'neutral' : 'green'}>
              {b.status === 'OPEN'
                ? 'aberto'
                : b.status === 'FROZEN'
                  ? 'congelado'
                  : 'expedido'}
            </RowTag>
          </div>
        </div>
      ))}
    </div>
  );
}
