/**
 * ExpedicaoPage — port literal de design/nelo-zip/src/page-extra.jsx
 * (PageShipments).
 *
 * Layout:
 *   • PageHeader: título "Expedições" + botão "Nova expedição".
 *   • 3 KPI strip: Próxima expedição (dias) / Prontos em armazém / Em risco.
 *   • SectionHeader "Calendário das próximas 4 semanas".
 *   • Lista de ShipmentDetail cards (3-col grid: data 180px / progress 1fr /
 *     actions 220px). Progress bar stacked: green (ready) + blue (in_prod) +
 *     yellow (at_risk).
 *
 * Wire ao backend real:
 *   - /v1/plan/transport/batches → 3 batches seedados (16/05 FR+PT, 20/05 DE,
 *     22/05 IT+SE).
 *   - ready/in_prod/at_risk: derivados de assignments quando wired (Q.18.ZIP.
 *     EXP.BE pendente). Por agora usa truck_capacity_units como total e mostra
 *     placeholders honestos para os counts.
 *
 * ZERO MOCKS. Empty states explícitos.
 *
 * Sprint Q.18.ZIP.EXP (refactor profundo big-bang).
 */

import { lazy, Suspense, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  RefreshCw,
  Sparkles,
  Truck,
  Boxes,
  Plus,
  CheckCircle2,
  FileText,
  Printer,
  X,
} from 'lucide-react';
import { PageHeader, Tabs } from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import { getApiBase, transportApi } from '../../lib/api';

const SupplyDashboard = lazy(() =>
  import('../../components/supply/SupplyPanels').then((m) => ({ default: m.SupplyDashboard })),
);

// ─── Endpoint ───────────────────────────────────────────────────────────────

interface TransportBatch {
  id: string;
  code: string;
  transport_date: string;
  destination: string | null;
  truck_capacity_units: number;
  priority: number;
  status: string;
  // Não-canónicos (só se backend devolve):
  ready?: number;
  in_prod?: number;
  at_risk?: number;
  suggestion?: string | null;
}

async function fetchTransportBatches(): Promise<TransportBatch[]> {
  // Q.21.A — base URL via api.ts (concorda com VITE_API_URL).
  const resp = await fetch(
    `${getApiBase()}/v1/plan/transport/batches?limit=20`,
    { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
  );
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function shipmentDayLabel(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  const days = ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'];
  return days[d.getDay()];
}

function daysUntil(iso: string): number {
  const t = new Date(iso + 'T00:00:00').getTime();
  const today = new Date().setHours(0, 0, 0, 0);
  return Math.round((t - today) / (1000 * 60 * 60 * 24));
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════

export default function ExpedicaoPage() {
  const [tab, setTab] = useState<'expedicoes' | 'supply'>('expedicoes');
  const [showForm, setShowForm] = useState(false);
  const [manifestBatchId, setManifestBatchId] = useState<string | null>(null);
  const batchesQuery = useQuery({
    queryKey: ['expedicao', 'batches'],
    queryFn: fetchTransportBatches,
    staleTime: 60_000,
    retry: 0,
  });

  const batches = batchesQuery.data ?? [];

  // KPIs derivados
  const sortedBatches = useMemo(
    () =>
      [...batches]
        .filter((b) => daysUntil(b.transport_date) >= 0)
        .sort(
          (a, b) =>
            new Date(a.transport_date).getTime() - new Date(b.transport_date).getTime(),
        ),
    [batches],
  );
  const nextBatch = sortedBatches[0];
  const daysToNext = nextBatch ? daysUntil(nextBatch.transport_date) : null;

  const totalReady = batches.reduce((sum, b) => sum + (b.ready ?? 0), 0);
  const totalAtRisk = batches.reduce((sum, b) => sum + (b.at_risk ?? 0), 0);

  return (
    <div>
      <PageHeader
        title="Expedições"
        subtitle="Calendário de saídas · estado dos camiões"
        helpId="expedicao"
        actions={
          // Q.30.C — "Nova expedição" voltou, agora com formulário real
          // (POST /v1/plan/transport/batches via transportApi.createBatch).
          <>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
            >
              <RefreshCw size={13} />
              Atualizar
            </button>
            <button
              type="button"
              onClick={() => setShowForm((v) => !v)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-white text-xs font-medium transition-colors"
              style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
            >
              <Plus size={13} />
              Nova expedição
            </button>
          </>
        }
      />

      <div className="px-6 pt-2">
        <Tabs
          tabs={[
            { id: 'expedicoes', label: 'Expedições', icon: <Truck size={13} /> },
            { id: 'supply', label: 'Supply / Forecast', icon: <Boxes size={13} /> },
          ]}
          value={tab}
          onChange={(id) => setTab(id as 'expedicoes' | 'supply')}
        />
      </div>

      {tab === 'supply' && (
        <div className="px-6 py-4">
          <Suspense fallback={<div className="p-8"><SkeletonLoader count={5} /></div>}>
            <SupplyDashboard />
          </Suspense>
        </div>
      )}

      {tab === 'expedicoes' && (
      <div className="px-6 py-4 space-y-5 page-enter">
        {showForm && (
          <NovaExpedicaoForm onClose={() => setShowForm(false)} />
        )}

        {/* 3 KPI strip — Q.23.H: "Próxima expedição" em destaque */}
        <div
          className="page-enter"
          style={{
            display: 'grid',
            gridTemplateColumns: '1.4fr 1fr 1fr',
            gap: 14,
          }}
        >
          <KPIStrip
            hero
            label="Próxima expedição"
            value={daysToNext !== null ? daysToNext.toString() : '—'}
            unit="dias"
            context={
              nextBatch
                ? `${shipmentDayLabel(nextBatch.transport_date)} · ${nextBatch.truck_capacity_units} barcos para ${nextBatch.destination ?? '—'}`
                : 'Sem expedições agendadas'
            }
            tone={
              daysToNext === null
                ? 'gray'
                : daysToNext <= 1
                  ? 'red'
                  : daysToNext <= 3
                    ? 'yellow'
                    : 'green'
            }
          />
          <KPIStrip
            label="Prontos em armazém"
            value={totalReady.toString()}
            context={
              totalReady === 0
                ? 'Sem assignments wired ainda (Q.18.ZIP.EXP.BE)'
                : 'Soma de boats ready em batches activos'
            }
            tone={totalReady > 0 ? 'green' : 'gray'}
          />
          <KPIStrip
            label="Em risco"
            value={totalAtRisk.toString()}
            context={
              totalAtRisk === 0
                ? 'Nenhum barco em risco identificado'
                : `${totalAtRisk} barco${totalAtRisk !== 1 ? 's' : ''} a precisar de atenção`
            }
            tone={totalAtRisk > 0 ? 'yellow' : 'green'}
          />
        </div>

        {/* Section header */}
        <div>
          <div className="text-sm font-semibold text-text-dark-primary">
            Calendário das próximas 4 semanas
          </div>
          <div className="text-xs text-text-dark-tertiary mt-0.5">
            Cada cartão é uma expedição agendada com cliente
          </div>
        </div>

        {/* Shipment cards */}
        {batchesQuery.isLoading ? (
          <div className="px-4 py-12 text-center text-xs text-text-dark-tertiary">
            A carregar expedições…
          </div>
        ) : batchesQuery.isError ? (
          <div className="px-4 py-12 text-center text-xs text-danger">
            Erro a carregar /v1/plan/transport/batches.
          </div>
        ) : batches.length === 0 ? (
          <div className="px-4 py-12 text-center">
            <Truck size={32} className="mx-auto mb-3 text-text-dark-tertiary" />
            <div className="text-sm text-text-dark-secondary">
              Sem expedições agendadas
            </div>
            <div className="text-xs text-text-dark-tertiary mt-1">
              Adicione um camião para o próximo cliente.
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3.5 page-enter">
            {sortedBatches.map((s) => (
              <ShipmentDetail
                key={s.id}
                shipment={s}
                onManifest={() => setManifestBatchId(s.id)}
              />
            ))}
          </div>
        )}
      </div>
      )}

      {manifestBatchId ? (
        <ManifestModal
          batchId={manifestBatchId}
          onClose={() => setManifestBatchId(null)}
        />
      ) : null}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// NovaExpedicaoForm — Q.30.C: criar batch (POST /v1/plan/transport/batches)
// ═══════════════════════════════════════════════════════════════════════════

const EXP_FIELD_CLASS =
  'w-full px-3 py-2 rounded-md bg-dark-700 border border-white/10 text-sm ' +
  'text-text-dark-primary placeholder:text-text-dark-tertiary focus:outline-none ' +
  'focus:ring-2 focus:ring-accent-500/40 focus:border-accent-500/60';

function NovaExpedicaoForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [code, setCode] = useState('');
  const [transportDate, setTransportDate] = useState('');
  const [capacity, setCapacity] = useState('');
  const [destination, setDestination] = useState('');

  const mutation = useMutation({
    mutationFn: () => {
      const cap = Number(capacity);
      return transportApi.createBatch({
        code: code.trim(),
        transport_date: transportDate,
        truck_capacity_units:
          capacity.trim() !== '' && Number.isFinite(cap) ? cap : undefined,
        destination: destination.trim() || undefined,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['expedicao', 'batches'] });
      onClose();
    },
  });

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!code.trim() || !transportDate) return;
    mutation.mutate();
  }

  const disabled = !code.trim() || !transportDate || mutation.isPending;

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        padding: 18,
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 12,
      }}
      className="space-y-3 page-enter"
    >
      <div className="flex items-center gap-2">
        <Truck size={16} className="text-text-dark-secondary" />
        <span className="text-sm font-semibold text-text-dark-primary">
          Nova expedição
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <label className="block">
          <span className="text-xs text-text-dark-secondary">Código *</span>
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="EXP-2026-05-20"
            className={`mt-1 ${EXP_FIELD_CLASS}`}
            required
          />
        </label>
        <label className="block">
          <span className="text-xs text-text-dark-secondary">Data de transporte *</span>
          <input
            type="date"
            value={transportDate}
            onChange={(e) => setTransportDate(e.target.value)}
            className={`mt-1 ${EXP_FIELD_CLASS}`}
            required
          />
        </label>
        <label className="block">
          <span className="text-xs text-text-dark-secondary">Capacidade (barcos)</span>
          <input
            type="number"
            inputMode="numeric"
            min={0}
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
            placeholder="Ex: 6"
            className={`mt-1 ${EXP_FIELD_CLASS}`}
          />
        </label>
        <label className="block">
          <span className="text-xs text-text-dark-secondary">Destino</span>
          <input
            type="text"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            placeholder="Ex: França — Lyon"
            className={`mt-1 ${EXP_FIELD_CLASS}`}
          />
        </label>
      </div>

      {mutation.isError ? (
        <div className="text-xs text-danger" role="alert">
          Não foi possível criar a expedição. Tenta outra vez.
        </div>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={disabled}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
        >
          <CheckCircle2 size={14} />
          {mutation.isPending ? 'A criar…' : 'Criar expedição'}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center px-4 py-2 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-sm font-medium transition-colors"
        >
          Cancelar
        </button>
      </div>
    </form>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ShipmentDetail (port literal page-extra.jsx)
// ═══════════════════════════════════════════════════════════════════════════

function ShipmentDetail({
  shipment,
  onManifest,
}: {
  shipment: TransportBatch;
  onManifest: () => void;
}) {
  const total = shipment.truck_capacity_units;
  const ready = shipment.ready ?? 0;
  const in_prod = shipment.in_prod ?? 0;
  const at_risk = shipment.at_risk ?? 0;
  const pct = total > 0 ? (ready / total) * 100 : 0;
  const tone = at_risk > 0 ? 'yellow' : pct >= 100 ? 'green' : 'blue';
  const day = shipmentDayLabel(shipment.transport_date);
  const dx = daysUntil(shipment.transport_date);
  // Q.23.H — urgência visual: D-0/D-1 destacam-se (vermelho + halo),
  // D-2/D-3 amarelo, resto neutro.
  const urgent = dx >= 0 && dx <= 1;
  const urgencyColor =
    dx >= 0 && dx <= 1 ? 'var(--red)' : dx >= 0 && dx <= 3 ? 'var(--yellow)' : 'var(--bd-1)';

  return (
    <div
      style={{
        padding: 22,
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderLeft: `3px solid ${urgencyColor}`,
        borderRadius: 12,
        boxShadow: urgent ? '0 0 0 1px var(--red-bd)' : undefined,
      }}
    >
      {/* Q.21.D — coluna de acções removida: "Ver barcos" e "Documentos"
          não tinham onClick nem endpoint (vista de barcos por batch /
          documentos de expedição não existem no backend). */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '180px 1fr',
          gap: 22,
          alignItems: 'center',
        }}
      >
        {/* Left: data */}
        <div>
          <div
            style={{
              fontSize: 11,
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
              fontWeight: 600,
            }}
          >
            {day}
            {dx >= 0 && dx <= 7 ? (
              <span
                style={{
                  marginLeft: 8,
                  color: dx <= 1 ? 'var(--red)' : dx <= 3 ? 'var(--yellow)' : 'var(--green)',
                  fontWeight: 700,
                }}
              >
                D−{dx}
              </span>
            ) : null}
          </div>
          <div
            className="tabular-nums"
            style={{
              fontSize: 22,
              fontWeight: 700,
              color: 'var(--fg-0)',
              marginTop: 2,
            }}
          >
            {shipment.transport_date.slice(8, 10)}/{shipment.transport_date.slice(5, 7)}
          </div>
          <div
            style={{
              fontSize: 12,
              color: 'var(--fg-1)',
              marginTop: 4,
              lineHeight: 1.4,
            }}
          >
            {shipment.destination ?? '—'}
          </div>
          {/* Q.31.E — gerar documento de expedição (manifesto) */}
          <button
            type="button"
            onClick={onManifest}
            className="mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs transition-colors hover:bg-white/5"
            style={{ color: 'var(--fg-2)', border: '1px solid var(--bd-1)' }}
          >
            <FileText size={12} />
            Manifesto
          </button>
        </div>

        {/* Center: progress */}
        <div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              marginBottom: 8,
            }}
          >
            <span className="text-sm font-medium text-text-dark-primary">
              Estado dos {total} barcos
            </span>
            <span
              className="tabular-nums font-bold"
              style={{ fontSize: 14, color: `var(--${tone})` }}
            >
              {ready}/{total} prontos
            </span>
          </div>
          <div
            style={{
              height: 6,
              background: 'var(--bd-1)',
              borderRadius: 3,
              overflow: 'hidden',
              display: 'flex',
            }}
          >
            <div style={{ width: `${pct}%`, background: 'var(--green)' }} />
            {in_prod > 0 ? (
              <div
                style={{
                  width: `${(in_prod / total) * 100}%`,
                  background: 'var(--blue)',
                }}
              />
            ) : null}
            {at_risk > 0 ? (
              <div
                style={{
                  width: `${(at_risk / total) * 100}%`,
                  background: 'var(--yellow)',
                }}
              />
            ) : null}
          </div>
          <div
            style={{
              display: 'flex',
              gap: 14,
              marginTop: 8,
              fontSize: 11,
              color: 'var(--fg-2)',
            }}
          >
            <span>
              ●{' '}
              <span style={{ color: 'var(--green)' }}>
                {ready} pronto{ready !== 1 ? 's' : ''}
              </span>
            </span>
            {in_prod > 0 ? (
              <span>
                ●{' '}
                <span style={{ color: 'var(--blue)' }}>
                  {in_prod} em produção
                </span>
              </span>
            ) : null}
            {at_risk > 0 ? (
              <span>
                ●{' '}
                <span style={{ color: 'var(--yellow)' }}>
                  {at_risk} em risco
                </span>
              </span>
            ) : null}
          </div>
          {shipment.suggestion ? (
            <div
              style={{
                marginTop: 12,
                padding: '10px 12px',
                background: 'var(--blue-bg)',
                border: '1px solid var(--blue-bd)',
                borderRadius: 8,
                fontSize: 12,
                color: 'var(--fg-1)',
                display: 'flex',
                gap: 8,
                alignItems: 'flex-start',
              }}
            >
              <Sparkles
                size={14}
                style={{ color: 'var(--blue)', flexShrink: 0, marginTop: 1 }}
              />
              <span>{shipment.suggestion}</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ManifestModal — Q.31.E: documento de expedição imprimível
// ═══════════════════════════════════════════════════════════════════════════

function ManifestModal({
  batchId,
  onClose,
}: {
  batchId: string;
  onClose: () => void;
}) {
  const q = useQuery({
    queryKey: ['transport-manifest', batchId],
    queryFn: () => transportApi.manifest(batchId),
    retry: 0,
  });
  const m = q.data;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-xl"
        style={{ background: 'var(--bg-1)', border: '1px solid var(--bd-1)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="flex items-center justify-between px-5 py-3 border-b"
          style={{ borderColor: 'var(--bd-1)' }}
        >
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-text-dark-secondary" />
            <span className="text-sm font-semibold text-text-dark-primary">
              Manifesto de expedição
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => window.print()}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs text-white"
              style={{ background: 'var(--blue)' }}
            >
              <Printer size={12} />
              Imprimir
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-md hover:bg-white/5"
              aria-label="Fechar"
            >
              <X size={16} className="text-text-dark-secondary" />
            </button>
          </div>
        </div>

        <div className="p-5">
          {q.isLoading ? (
            <div className="text-xs text-text-dark-tertiary py-6 text-center">
              A carregar manifesto…
            </div>
          ) : q.isError || !m ? (
            <div className="text-xs text-danger py-6 text-center">
              Não foi possível carregar o manifesto.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-text-dark-tertiary">Código: </span>
                  <span className="text-text-dark-primary font-medium">
                    {m.batch.code}
                  </span>
                </div>
                <div>
                  <span className="text-text-dark-tertiary">Data: </span>
                  <span className="text-text-dark-primary font-medium">
                    {m.batch.transport_date ?? '—'}
                  </span>
                </div>
                <div>
                  <span className="text-text-dark-tertiary">Destino: </span>
                  <span className="text-text-dark-primary font-medium">
                    {m.batch.destination ?? '—'}
                  </span>
                </div>
                <div>
                  <span className="text-text-dark-tertiary">Estado: </span>
                  <span className="text-text-dark-primary font-medium">
                    {m.batch.status}
                  </span>
                </div>
              </div>

              <div>
                <div className="text-xs font-semibold text-text-dark-secondary mb-1">
                  Barcos ({m.boat_count} / {m.batch.truck_capacity_units} de capacidade)
                </div>
                {m.boats.length === 0 ? (
                  <div className="text-xs text-text-dark-tertiary py-3">
                    Nenhum barco atribuído a esta expedição.
                  </div>
                ) : (
                  <table className="w-full text-xs">
                    <thead className="border-b border-white/[0.08]">
                      <tr className="text-left text-[10px] uppercase tracking-wider text-text-dark-tertiary">
                        <th className="px-2 py-1.5">Casco</th>
                        <th className="px-2 py-1.5">Produto</th>
                        <th className="px-2 py-1.5">Tipo</th>
                        <th className="px-2 py-1.5">Fase actual</th>
                        <th className="px-2 py-1.5">Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {m.boats.map((b) => (
                        <tr
                          key={b.order_id}
                          className="border-b border-white/[0.04]"
                        >
                          <td className="px-2 py-1.5 font-mono text-text-dark-primary">
                            #{b.hull}
                          </td>
                          <td className="px-2 py-1.5 text-text-dark-secondary">
                            {b.product_name}
                          </td>
                          <td className="px-2 py-1.5 text-text-dark-secondary">
                            {b.product_type}
                          </td>
                          <td className="px-2 py-1.5 text-text-dark-secondary">
                            {b.current_phase}
                          </td>
                          <td className="px-2 py-1.5 text-text-dark-secondary">
                            {b.status}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="text-[10px] text-text-dark-tertiary">
                Gerado em {new Date(m.generated_at).toLocaleString('pt-PT')}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// KPIStrip (reusable)
// ═══════════════════════════════════════════════════════════════════════════

function KPIStrip({
  label,
  value,
  unit,
  context,
  tone,
  hero = false,
}: {
  label: string;
  value: string;
  unit?: string;
  context: string;
  tone: 'green' | 'yellow' | 'red' | 'blue' | 'gray';
  /** Q.23.H — variante destacada: valor maior, atmosfera, profundidade. */
  hero?: boolean;
}) {
  return (
    <div
      style={{
        padding: hero ? '20px 24px' : '16px 18px',
        background: hero ? 'var(--atmosphere-card), var(--bg-1)' : 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 12,
        boxShadow: hero ? 'var(--shadow-2)' : undefined,
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-2)',
          fontWeight: 500,
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div className="flex items-baseline gap-1 tabular-nums">
        <span
          style={{
            fontSize: hero ? 44 : 28,
            fontWeight: 700,
            color: `var(--${tone})`,
            lineHeight: 1,
            letterSpacing: hero ? '-0.02em' : undefined,
          }}
        >
          {value}
        </span>
        {unit ? (
          <span style={{ fontSize: hero ? 16 : 13, color: 'var(--fg-2)' }}>
            {unit}
          </span>
        ) : null}
      </div>
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          marginTop: 6,
          lineHeight: 1.4,
        }}
      >
        {context}
      </div>
    </div>
  );
}
