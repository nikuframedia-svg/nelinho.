/**
 * PorExpedicaoView — calendário de expedições/camiões (Q.115.L).
 *
 * Lê de GET /v1/plan/transport/batches se existir; caso contrário mostra empty state.
 * Drop de OFs para slot expedição está preparado mas inactivo enquanto
 * POST /v1/plan/transport/assign não existir (Q.115.L.2 pendente).
 */

import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { format, eachDayOfInterval } from 'date-fns';
import { pt } from 'date-fns/locale';
import { Truck, Package } from 'lucide-react';
import { EmptyState, DarkCard } from '../../dark';
import { request } from '../../../lib/api/client';
import { Clickable } from '../../entitySheets';

// ─── Tipos ──────────────────────────────────────────────────────────────────

interface TransportBatch {
  id: string;
  camiao_id: string;
  destino?: string;
  data_partida: string;
  order_ids: string[];
  /** Q.116.C — UUIDs dos clientes nas orders desta batch (pode ser vazio).
   *  Exposto pelo backend mas não usado em Clickable enquanto customer_name
   *  não for incluído no payload (Q.116.E). */
  customer_ids?: string[];
}

interface PorExpedicaoViewProps {
  startDate: Date;
  endDate: Date;
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
}: PorExpedicaoViewProps): ReactNode {
  const since = format(startDate, 'yyyy-MM-dd');
  const until = format(endDate, 'yyyy-MM-dd');

  const { data: batches, isError, isLoading } = useQuery({
    queryKey: ['plan', 'transport', 'batches', since, until],
    queryFn: () => fetchTransportBatches(since, until),
    retry: false, // se endpoint não existe (404), não retry
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="text-center text-slate-400 text-sm py-8">
        A carregar expedições…
      </div>
    );
  }

  // Endpoint ainda não existe ou está vazio
  if (isError || !batches || batches.length === 0) {
    return (
      <EmptyState
        title="Sem expedições planeadas"
        hint="Endpoint GET /v1/plan/transport/batches não encontrado ou sem dados. Q.115.L.2 pendente."
      />
    );
  }

  const days = eachDayOfInterval({ start: startDate, end: endDate });

  // Agrupar batches por dia
  const batchesByDay = new Map<string, TransportBatch[]>();
  for (const b of batches) {
    const day = format(new Date(b.data_partida), 'yyyy-MM-dd');
    if (!batchesByDay.has(day)) batchesByDay.set(day, []);
    batchesByDay.get(day)!.push(b);
  }

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(140px,1fr))] gap-2">
      {days.map((day) => {
        const key = format(day, 'yyyy-MM-dd');
        const dayBatches = batchesByDay.get(key) ?? [];

        return (
          <DarkCard key={key} className="p-2 min-h-[80px]">
            <div className="text-[10px] font-semibold text-slate-400 mb-1.5">
              {format(day, 'EEEE d MMM', { locale: pt })}
            </div>
            {dayBatches.length === 0 ? (
              <div className="text-[10px] text-slate-600 italic">livre</div>
            ) : (
              <div className="flex flex-col gap-1">
                {dayBatches.map((b) => (
                  <div
                    key={b.id}
                    className="flex items-start gap-1.5 px-1.5 py-1 rounded bg-slate-700/50 border border-slate-600/40 text-[10px]"
                    title={`Q.115.L.2 pendente — drag-drop para expedição não activo`}
                  >
                    <Truck size={10} className="text-teal-400 flex-shrink-0 mt-0.5" />
                    <div className="min-w-0">
                      <div className="text-slate-200 font-medium truncate">
                        {b.camiao_id}
                      </div>
                      {b.destino && (
                        <div className="text-slate-500 truncate">{b.destino}</div>
                      )}
                      <div className="flex items-center gap-0.5 text-slate-500 mt-0.5">
                        <Package size={8} />
                        <span>{b.order_ids.length} OFs</span>
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
