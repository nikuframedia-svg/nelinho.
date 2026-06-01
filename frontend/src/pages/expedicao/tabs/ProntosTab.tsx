/**
 * ProntosTab — Q.135.F2.2 + F2.3.
 *
 * Barcos PRONTOS a sair (fase "Embalado", do ERP) + backlog honesto (Armazém
 * acumulado) + ritmo real de expedição (mart) + recomendação do "próximo
 * camião" (os prontos há mais tempo). Tudo dados reais. ZERO MOCKS.
 *
 * Nota honesta: os barcos prontos vivem no ERP (factory_raw), e o sistema de
 * camiões (assign) opera sobre WIP (production_orders) — por isso a sugestão é
 * INFORMATIVA (que barcos deviam ir a seguir), não um auto-compor.
 */
import { useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Package, Truck, Clock, ChevronDown } from 'lucide-react';
import { DarkBadge, DarkCard, EmptyState } from '../../../components/dark';
import { SkeletonLoader } from '../../../components/ui/Skeleton';
import { transportApi, type ReadyBoat } from '../../../lib/api/supplyApi';
import { Clickable } from '../../../components/entitySheets';

const TRUCK_CAP = 26; // moda real Vila do Conde (Q.13.E)

export function ProntosTab(): ReactNode {
  const readyQ = useQuery({
    queryKey: ['expedicao', 'ready'],
    queryFn: () => transportApi.ready(200),
    staleTime: 30_000,
    retry: 0,
  });
  const thrQ = useQuery({
    queryKey: ['expedicao', 'throughput'],
    queryFn: () => transportApi.throughput(3),
    staleTime: 60_000,
    retry: 0,
  });

  // Ritmo semanal real: total expedido nos meses do mart / nº de semanas.
  const weeklyRate = useMemo(() => {
    const rows = thrQ.data ?? [];
    if (rows.length === 0) return null;
    const months = new Set(rows.map((r) => r.month));
    const total = rows.reduce((s, r) => s + (r.n_ofs ?? 0), 0);
    const weeks = Math.max(1, months.size * 4.33);
    return Math.round(total / weeks);
  }, [thrQ.data]);

  // Q.143.E — o resto (além do próximo camião) fica colapsado por defeito.
  const [showAll, setShowAll] = useState(false);

  if (readyQ.isLoading) return <SkeletonLoader count={6} />;
  if (readyQ.isError) {
    return (
      <EmptyState
        title="Não foi possível carregar os barcos prontos"
        hint="O endpoint /v1/plan/transport/ready falhou. Confirma se o backend está a correr."
      />
    );
  }

  const data = readyQ.data!;
  const nextTruck = data.boats.slice(0, TRUCK_CAP);
  const oldest = nextTruck.length > 0 ? nextTruck[0].days_ready : null;

  return (
    <div className="flex flex-col gap-4">
      {/* Contexto honesto do backlog + ritmo */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <DarkCard className="p-3">
          <div className="text-[10px] uppercase tracking-wide text-text-dark-tertiary">Prontos (Embalado)</div>
          <div className="text-2xl font-semibold text-text-dark-primary tabular-nums">{data.embalado_count}</div>
        </DarkCard>
        <DarkCard className="p-3">
          <div className="text-[10px] uppercase tracking-wide text-text-dark-tertiary">Backlog (Armazém)</div>
          <div className="text-2xl font-semibold text-amber-300 tabular-nums">{data.armazem_count.toLocaleString('pt-PT')}</div>
          <div className="text-[10px] text-text-dark-tertiary mt-0.5">acumulado, não fila</div>
        </DarkCard>
        <DarkCard className="p-3">
          <div className="text-[10px] uppercase tracking-wide text-text-dark-tertiary">Idade média pronto</div>
          <div className="text-2xl font-semibold text-text-dark-primary tabular-nums">{data.avg_days_ready ?? '—'}<span className="text-sm"> dias</span></div>
        </DarkCard>
        <DarkCard className="p-3">
          <div className="text-[10px] uppercase tracking-wide text-text-dark-tertiary">Ritmo real</div>
          <div className="text-2xl font-semibold text-text-dark-primary tabular-nums">{weeklyRate ?? '—'}<span className="text-sm"> /semana</span></div>
          <div className="text-[10px] text-text-dark-tertiary mt-0.5">expedidos (mart)</div>
        </DarkCard>
      </div>

      {/* Recomendação: próximo camião = os mais antigos */}
      {nextTruck.length > 0 && (
        <div
          className="rounded-lg p-3 flex items-start gap-2.5"
          style={{ background: 'var(--accent-bg)', border: '1px dashed var(--accent-bd)' }}
        >
          <Truck size={16} className="text-[color:var(--accent)] flex-shrink-0 mt-0.5" />
          <div className="text-xs">
            <div className="font-semibold text-text-dark-primary">
              Próximo camião sugerido — {nextTruck.length} barcos prontos há mais tempo
              {oldest != null ? ` (até ${oldest} dias)` : ''}
            </div>
            <div className="text-text-dark-secondary mt-0.5">
              Recomendação por antiguidade (sem destino fiável nos dados). Composição manual na aba
              <strong> Expedições</strong>. Ritmo real ~{weeklyRate ?? '—'}/semana.
            </div>
          </div>
        </div>
      )}

      {data.boats.length === 0 ? (
        <EmptyState title="Sem barcos prontos (Embalado)" hint="Nenhum barco está na fase Embalado à espera de transporte." />
      ) : (
        <DarkCard className="p-0 overflow-hidden">
          <div className="grid grid-cols-[auto_1fr_auto] gap-x-4 px-4 py-2 text-[10px] uppercase tracking-wide text-text-dark-tertiary border-b border-white/[0.06]">
            <span>Barco</span>
            <span>Item / referência</span>
            <span>Pronto há</span>
          </div>
          {/* Próximo camião — sempre visível e destacado */}
          {nextTruck.map((b) => (
            <ReadyRow key={b.of_id} boat={b} isNext />
          ))}

          {/* Resto — colapsado por defeito (174 linhas seriam ruído) */}
          {showAll && data.boats.slice(TRUCK_CAP).map((b) => (
            <ReadyRow key={b.of_id} boat={b} isNext={false} />
          ))}

          {data.boats.length > TRUCK_CAP && (
            <button
              type="button"
              onClick={() => setShowAll((v) => !v)}
              className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 text-xs font-medium text-text-dark-secondary hover:text-text-dark-primary hover:bg-white/[0.03] transition-colors"
            >
              <ChevronDown size={13} className={showAll ? 'rotate-180 transition-transform' : 'transition-transform'} />
              {showAll
                ? 'Mostrar só o próximo camião'
                : `Mostrar mais ${data.boats.length - TRUCK_CAP} prontos`}
            </button>
          )}
        </DarkCard>
      )}
    </div>
  );
}

/** Linha de um barco pronto. Mostra o modelo real e, quando é o genérico
 *  "Encomenda de Cliente", a referência da OF como descritor honesto (Q.143.E). */
function ReadyRow({ boat: b, isNext }: { boat: ReadyBoat; isNext: boolean }): ReactNode {
  const generic = !b.model || b.model === 'Encomenda de Cliente';
  const primary = generic && b.reference ? b.reference : (b.model ?? '—');
  const secondary = generic && b.reference && b.model ? b.model : null;
  return (
    <div
      className="grid grid-cols-[auto_1fr_auto] gap-x-4 items-center px-4 py-2 border-b border-white/[0.04] text-sm"
      style={isNext ? { background: 'var(--accent-bg)' } : undefined}
    >
      <span className="font-mono tabular-nums text-text-dark-secondary">
        <Clickable kind="encomenda" id={b.of_id}>#{b.of_id}</Clickable>
      </span>
      <span className="min-w-0 flex items-center gap-1.5">
        <Package size={11} className="text-text-dark-tertiary flex-shrink-0" />
        <span className="truncate text-text-dark-primary">{primary}</span>
        {secondary && (
          <span className="truncate text-text-dark-tertiary text-xs">· {secondary}</span>
        )}
      </span>
      <span className="text-text-dark-tertiary text-xs tabular-nums flex items-center gap-1">
        <Clock size={10} />
        {b.days_ready != null ? `${b.days_ready} dias` : '—'}
        {isNext && <DarkBadge variant="accent" size="sm">próximo</DarkBadge>}
      </span>
    </div>
  );
}
