/**
 * PorExpedicaoView — calendário de expedições/camiões (Q.115.L).
 *
 * Lê de GET /v1/plan/transport/batches se existir; caso contrário mostra empty state.
 * Drop de OFs para slot expedição está preparado mas inactivo enquanto
 * POST /v1/plan/transport/assign não existir (Q.115.L.2 pendente).
 */

import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { format, eachDayOfInterval } from 'date-fns';
import { pt } from 'date-fns/locale';
import { Truck, Package, Ship } from 'lucide-react';
import { EmptyState, DarkCard } from '../../dark';
import { request } from '../../../lib/api/client';
import type { TimelineExpedition } from '../../../lib/api/planApi';
import { Clickable } from '../../entitySheets';

// ─── Tipos ──────────────────────────────────────────────────────────────────

interface TransportBatch {
  id: string;
  // Q.121.D1 — nomes alinhados ao backend TransportBatchOut (src/plan/api/transport.py).
  // Antes a interface usava camiao_id/destino/data_partida/order_ids — nomes que o
  // backend NUNCA envia → data_partida=undefined → format(new Date(undefined)) lançava
  // RangeError: Invalid time value e crashava a vista para o ErrorBoundary.
  code: string;
  destination?: string;
  transport_date: string;
  assigned_orders_count?: number;
  /** Q.116.C — UUIDs dos clientes nas orders desta batch (pode ser vazio). */
  customer_ids?: string[];
}

interface PorExpedicaoViewProps {
  startDate: Date;
  endDate: Date;
  /** Q.141.K — expedições REAIS (transp_of) do passado; lotes planeados vêm da query. */
  expeditions?: TimelineExpedition[];
}

// ─── API local (endpoint pode não existir) ──────────────────────────────────

function fetchTransportBatches(since: string, until: string): Promise<TransportBatch[]> {
  return request<TransportBatch[]>(
    `/v1/plan/transport/batches?since=${since}&until=${until}`,
  );
}

// ─── Componente principal ───────────────────────────────────────────────────

export function PorExpedicaoView({
  startDate,
  endDate,
  expeditions = [],
}: PorExpedicaoViewProps): ReactNode {
  const since = format(startDate, 'yyyy-MM-dd');
  const until = format(endDate, 'yyyy-MM-dd');

  const { data: batches, isLoading } = useQuery({
    queryKey: ['plan', 'transport', 'batches', since, until],
    queryFn: () => fetchTransportBatches(since, until),
    retry: false, // se endpoint não existe (404), não retry
    staleTime: 60_000,
  });

  // Q.141.K — expedições REAIS (passado, transp_of) agrupadas por dia de saída.
  const expedByDay = new Map<string, TimelineExpedition[]>();
  for (const e of expeditions) {
    const d = e.transport_date ? new Date(e.transport_date) : null;
    if (!d || Number.isNaN(d.getTime())) continue;
    const day = format(d, 'yyyy-MM-dd');
    if (!expedByDay.has(day)) expedByDay.set(day, []);
    expedByDay.get(day)!.push(e);
  }

  // Lotes de transporte PLANEADOS (futuro) agrupados por dia.
  const batchesByDay = new Map<string, TransportBatch[]>();
  for (const b of batches ?? []) {
    // Q.121.D1 — guard: nunca passar uma data inválida a format() (RangeError).
    const d = b.transport_date ? new Date(b.transport_date) : null;
    if (!d || Number.isNaN(d.getTime())) continue;
    const day = format(d, 'yyyy-MM-dd');
    if (!batchesByDay.has(day)) batchesByDay.set(day, []);
    batchesByDay.get(day)!.push(b);
  }

  if (isLoading && expeditions.length === 0) {
    return (
      <div className="text-center text-slate-400 text-sm py-8">
        A carregar expedições…
      </div>
    );
  }

  // Sem realizado (transp_of) E sem lotes planeados.
  if (expedByDay.size === 0 && batchesByDay.size === 0) {
    return (
      <EmptyState
        title="Sem expedições neste intervalo"
        hint="Nenhum barco saiu (transp_of) nem há lotes de transporte planeados para estas datas."
      />
    );
  }

  const days = eachDayOfInterval({ start: startDate, end: endDate });

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-2">
      {days.map((day) => {
        const key = format(day, 'yyyy-MM-dd');
        const dayBatches = batchesByDay.get(key) ?? [];
        const dayExped = expedByDay.get(key) ?? [];

        return (
          <DarkCard key={key} className="p-2 min-h-[80px]">
            {/* Q.135.F2.1 — clicar na data abre a Expedição → aba "Por data"
                (barcos previstos sair nesse dia + fase + risco). */}
            <Link
              to={`/expedicao?date=${key}`}
              className="block text-[10px] font-semibold text-slate-400 mb-1.5 hover:text-[color:var(--accent)] transition-colors"
              title="Ver barcos previstos sair nesta data e a fase de cada um"
            >
              {format(day, 'EEEE d MMM', { locale: pt })}
            </Link>
            {dayBatches.length === 0 && dayExped.length === 0 ? (
              <div className="text-[10px] text-slate-600 italic">livre</div>
            ) : (
              <div className="flex flex-col gap-1">
                {/* Q.141.K — barcos que SAÍRAM (real, transp_of) — sólido verde. */}
                {dayExped.map((e, i) => (
                  <div
                    key={`exp-${e.of_id}-${i}`}
                    className="flex items-start gap-1.5 px-1.5 py-1 rounded text-[10px]"
                    style={{ background: 'var(--green-bg)', border: '1px solid var(--green-bd)' }}
                    title={`Saiu: ${e.barco_nome ?? e.of_id} (OF ${e.of_id})`}
                  >
                    <Ship size={10} className="flex-shrink-0 mt-0.5" style={{ color: 'var(--green)' }} />
                    <div className="min-w-0">
                      <div className="text-slate-100 font-medium truncate">
                        {e.barco_nome ?? `OF ${e.of_id}`}
                      </div>
                      <div className="text-slate-400">saiu</div>
                    </div>
                  </div>
                ))}
                {/* Lotes de transporte PLANEADOS (futuro) — tracejado. */}
                {dayBatches.map((b) => (
                  <div
                    key={b.id}
                    className="flex items-start gap-1.5 px-1.5 py-1 rounded bg-slate-700/50 border border-dashed border-slate-600/50 text-[10px]"
                    title="Lote de transporte planeado"
                  >
                    <Truck size={10} className="text-teal-400 flex-shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <div className="text-slate-200 font-medium truncate">
                        {b.code}
                      </div>
                      {b.destination && (
                        <div className="text-slate-500 truncate">{b.destination}</div>
                      )}
                      <div className="flex items-center gap-0.5 text-slate-500 mt-0.5">
                        <Package size={8} />
                        <span>{b.assigned_orders_count ?? 0} OFs</span>
                      </div>
                      {b.customer_ids && b.customer_ids.length === 1 && (
                        <div className="text-slate-500 mt-0.5 truncate">
                          <Clickable kind="cliente" id={b.customer_ids[0]}>
                            Cliente {b.customer_ids[0].slice(0, 8)}…
                          </Clickable>
                        </div>
                      )}
                      {b.customer_ids && b.customer_ids.length > 1 && (
                        <div className="text-slate-500 mt-0.5">
                          {b.customer_ids.length} clientes
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </DarkCard>
        );
      })}
    </div>
  );
}
