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
import { useQuery } from '@tanstack/react-query';
import {
  Plus,
  RefreshCw,
  Sparkles,
  Truck,
  Boxes,
} from 'lucide-react';
import { PageHeader, Tabs } from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import { getApiBase } from '../../lib/api';

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
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-white text-xs font-medium transition-colors"
              style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
              onClick={() => alert('Nova expedição — wire ao /v1/plan/transport/batches POST em sub-sprint')}
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
      <div className="px-6 py-4 space-y-5">
        {/* 3 KPI strip */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 14,
          }}
        >
          <KPIStrip
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
          <div className="flex flex-col gap-3.5">
            {sortedBatches.map((s) => (
              <ShipmentDetail key={s.id} shipment={s} />
            ))}
          </div>
        )}
      </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ShipmentDetail (port literal page-extra.jsx)
// ═══════════════════════════════════════════════════════════════════════════

function ShipmentDetail({ shipment }: { shipment: TransportBatch }) {
  const total = shipment.truck_capacity_units;
  const ready = shipment.ready ?? 0;
  const in_prod = shipment.in_prod ?? 0;
  const at_risk = shipment.at_risk ?? 0;
  const pct = total > 0 ? (ready / total) * 100 : 0;
  const tone = at_risk > 0 ? 'yellow' : pct >= 100 ? 'green' : 'blue';
  const day = shipmentDayLabel(shipment.transport_date);
  const dx = daysUntil(shipment.transport_date);

  return (
    <div
      style={{
        padding: 22,
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 12,
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '180px 1fr 220px',
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

        {/* Right: actions */}
        <div className="flex flex-col gap-2">
          <button
            type="button"
            className="w-full px-3 py-2 rounded-md text-xs font-medium border transition-colors"
            style={{
              background: 'var(--bg-2)',
              borderColor: 'var(--bd-2)',
              color: 'var(--fg-1)',
            }}
          >
            Ver barcos
          </button>
          <button
            type="button"
            className="w-full px-3 py-2 rounded-md text-xs font-medium border transition-colors"
            style={{
              background: 'transparent',
              borderColor: 'transparent',
              color: 'var(--fg-2)',
            }}
          >
            Documentos
          </button>
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
}: {
  label: string;
  value: string;
  unit?: string;
  context: string;
  tone: 'green' | 'yellow' | 'red' | 'blue' | 'gray';
}) {
  return (
    <div
      style={{
        padding: '16px 18px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 12,
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
            fontSize: 28,
            fontWeight: 700,
            color: `var(--${tone})`,
            lineHeight: 1,
          }}
        >
          {value}
        </span>
        {unit ? (
          <span style={{ fontSize: 13, color: 'var(--fg-2)' }}>
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
