/**
 * PorDataTab — Q.135.F2.1.
 *
 * Para uma data de expedição, mostra os barcos previstos sair nesse dia e a
 * FASE atual de cada um: quais já estão prontos (fase terminal) e quais ainda
 * estão em produção (= risco, marcados para sair mas não-prontos). Dados reais
 * de `GET /v1/plan/transport/by-date` (production_orders). ZERO MOCKS.
 */
import { useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, Clock } from 'lucide-react';
import { DarkBadge, DarkCard, EmptyState } from '../../../components/dark';
import { SkeletonLoader } from '../../../components/ui/Skeleton';
import { transportApi, type BoatOnDate } from '../../../lib/api/supplyApi';
import { Clickable } from '../../../components/entitySheets';

function todayISO(): string {
  // Q.135 — Date.now indisponível em alguns contextos; new Date() local OK no browser.
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function bucketBadge(b: BoatOnDate): ReactNode {
  if (b.ready) {
    return (
      <DarkBadge variant="success" size="sm">
        <CheckCircle2 size={11} /> pronto
      </DarkBadge>
    );
  }
  if (b.bucket === 'POR_COMECAR') {
    return (
      <DarkBadge variant="neutral" size="sm">
        <Clock size={11} /> por começar
      </DarkBadge>
    );
  }
  return (
    <DarkBadge variant="danger" size="sm">
      <AlertTriangle size={11} /> em produção — risco
    </DarkBadge>
  );
}

export function PorDataTab({ initialDate }: { initialDate?: string }): ReactNode {
  const [date, setDate] = useState<string>(initialDate || todayISO());

  const query = useQuery({
    queryKey: ['expedicao', 'by-date', date],
    queryFn: () => transportApi.byDate(date),
    enabled: !!date,
    staleTime: 30_000,
    retry: 0,
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <label className="text-xs text-text-dark-secondary">Data de expedição</label>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="bg-white text-slate-900 placeholder:text-slate-400 rounded-md px-2.5 py-1.5 text-sm border border-white/10"
        />
        {query.data && (
          <div className="flex items-center gap-2 text-xs">
            <DarkBadge variant="neutral" size="sm">{query.data.total} barcos</DarkBadge>
            <DarkBadge variant="success" size="sm">{query.data.ready} prontos</DarkBadge>
            <DarkBadge variant={query.data.at_risk > 0 ? 'danger' : 'neutral'} size="sm">
              {query.data.at_risk} em risco
            </DarkBadge>
          </div>
        )}
      </div>

      {query.isLoading && <SkeletonLoader count={6} />}

      {query.isError && (
        <EmptyState
          title="Não foi possível carregar os barcos desta data"
          hint="O endpoint /v1/plan/transport/by-date falhou. Confirma se o backend está a correr."
        />
      )}

      {query.data && query.data.boats.length === 0 && (
        <EmptyState
          title="Sem barcos previstos para esta data"
          hint="Nenhuma ordem em curso tem esta data de expedição planeada."
        />
      )}

      {query.data && query.data.boats.length > 0 && (
        <DarkCard className="p-0 overflow-hidden">
          <div className="grid grid-cols-[auto_1fr_auto_auto] gap-x-4 px-4 py-2 text-[10px] uppercase tracking-wide text-text-dark-tertiary border-b border-white/[0.06]">
            <span>Barco</span>
            <span>Fase atual</span>
            <span>Modelo</span>
            <span>Estado</span>
          </div>
          {query.data.boats.map((b) => (
            <div
              key={b.order_id}
              className="grid grid-cols-[auto_1fr_auto_auto] gap-x-4 items-center px-4 py-2 border-b border-white/[0.04] text-sm"
            >
              <span className="font-mono tabular-nums text-text-dark-secondary">
                <Clickable kind="encomenda" id={b.hull ?? b.order_id}>
                  #{b.hull ?? '—'}
                </Clickable>
              </span>
              <span className="text-text-dark-primary truncate">
                {b.current_phase_name ?? '—'}
              </span>
              <span className="text-text-dark-tertiary text-xs truncate">
                {b.product_name ?? '—'}
              </span>
              <span>{bucketBadge(b)}</span>
            </div>
          ))}
        </DarkCard>
      )}
    </div>
  );
}
