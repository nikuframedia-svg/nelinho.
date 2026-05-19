/**
 * StartByCard — "Quando começar" um barco (Q.53.G).
 *
 * Para o barco seleccionado na timeline, mostra:
 *   - data-limite de início (`GET /v1/plan/orders/{id}/start-by`) — a
 *     última data em que o barco pode arrancar e ainda chegar à data de
 *     transporte prometida;
 *   - expedição sugerida (`GET /v1/plan/orders/{id}/suggest-shipment`) —
 *     se o barco começar hoje, quando fica pronto.
 *
 * Ambas devolvem o breakdown de lead time (horas de trabalho + gaps de
 * cura/secagem). ZERO MOCKS — sem data de transporte / sem routing →
 * mensagem honesta vinda do backend.
 */

import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CalendarClock, Ship } from 'lucide-react';
import { planeamentoApi } from './planeamentoApi';
import type { LeadTimeBreakdown } from './planeamentoApi';

function fmtDate(iso: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('pt-PT', {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
  });
}

function LeadTimeNote({ lead }: { lead: LeadTimeBreakdown | null }): ReactNode {
  if (!lead) return null;
  return (
    <div style={{ fontSize: 10.5, color: 'var(--fg-3)', marginTop: 4 }}>
      {lead.n_phases} fases · {lead.work_hours.toFixed(0)}h de trabalho +{' '}
      {lead.curing_gap_hours.toFixed(0)}h de cura/secagem
    </div>
  );
}

export function StartByCard({
  orderId,
  hull,
  productName,
}: {
  orderId: string;
  hull: string | null;
  productName: string | null;
}): ReactNode {
  const startByQuery = useQuery({
    queryKey: ['planeamento', 'start-by', orderId],
    queryFn: () => planeamentoApi.startBy(orderId),
    refetchOnWindowFocus: false,
  });
  const shipmentQuery = useQuery({
    queryKey: ['planeamento', 'suggest-shipment', orderId],
    queryFn: () => planeamentoApi.suggestShipment(orderId),
    refetchOnWindowFocus: false,
  });

  const startBy = startByQuery.data;
  const shipment = shipmentQuery.data;

  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding: 16,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 7,
          marginBottom: 12,
        }}
      >
        <CalendarClock size={14} color="var(--fg-2)" />
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
          Quando começar — {hull ?? productName ?? orderId}
        </span>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, 1fr)',
          gap: 12,
        }}
      >
        {/* ── Data-limite de início ──────────────────────────────────── */}
        <div
          style={{
            background: 'var(--bg-2)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-sm)',
            padding: 12,
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
              fontWeight: 600,
            }}
          >
            Data-limite de início
          </div>
          {startByQuery.isLoading ? (
            <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 6 }}>
              A calcular…
            </div>
          ) : startByQuery.isError ? (
            <div style={{ fontSize: 11.5, color: 'var(--red)', marginTop: 6 }}>
              Falha a calcular a data-limite.
            </div>
          ) : startBy && startBy.start_by ? (
            <>
              <div
                className="display tabular"
                style={{
                  fontSize: 20,
                  fontWeight: 600,
                  marginTop: 4,
                  color:
                    startBy.feasible === false
                      ? 'var(--red)'
                      : 'var(--green)',
                }}
              >
                {fmtDate(startBy.start_by)}
              </div>
              <div style={{ fontSize: 10.5, color: 'var(--fg-3)', marginTop: 2 }}>
                p/ transporte {fmtDate(startBy.target_date)}
              </div>
              <LeadTimeNote lead={startBy.lead_time} />
              <div
                style={{
                  fontSize: 10.5,
                  marginTop: 6,
                  color:
                    startBy.feasible === false
                      ? 'var(--red)'
                      : 'var(--fg-2)',
                }}
              >
                {startBy.reason}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 6 }}>
              {startBy?.reason ?? 'Sem data-limite calculável.'}
            </div>
          )}
        </div>

        {/* ── Expedição sugerida ─────────────────────────────────────── */}
        <div
          style={{
            background: 'var(--bg-2)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-sm)',
            padding: 12,
          }}
        >
          <div
            style={{
              fontSize: 10,
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: 5,
            }}
          >
            <Ship size={11} />
            Expedição sugerida (se começar hoje)
          </div>
          {shipmentQuery.isLoading ? (
            <div style={{ fontSize: 12, color: 'var(--fg-3)', marginTop: 6 }}>
              A calcular…
            </div>
          ) : shipmentQuery.isError ? (
            <div style={{ fontSize: 11.5, color: 'var(--red)', marginTop: 6 }}>
              Falha a calcular a expedição.
            </div>
          ) : shipment && shipment.suggested_shipment ? (
            <>
              <div
                className="display tabular"
                style={{
                  fontSize: 20,
                  fontWeight: 600,
                  marginTop: 4,
                  color:
                    shipment.meets_transport_date === false
                      ? 'var(--red)'
                      : 'var(--fg-0)',
                }}
              >
                {fmtDate(shipment.suggested_shipment)}
              </div>
              {shipment.transport_date && (
                <div
                  style={{ fontSize: 10.5, color: 'var(--fg-3)', marginTop: 2 }}
                >
                  prometido {fmtDate(shipment.transport_date)}
                </div>
              )}
              <LeadTimeNote lead={shipment.lead_time} />
              <div
                style={{
                  fontSize: 10.5,
                  marginTop: 6,
                  color:
                    shipment.meets_transport_date === false
                      ? 'var(--red)'
                      : 'var(--fg-2)',
                }}
              >
                {shipment.reason}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 6 }}>
              {shipment?.reason ?? 'Sem expedição calculável.'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
