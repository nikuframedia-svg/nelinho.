// CausalPanels · WhyKpiPanel (Q.60.X). ZERO MOCKS — endpoints reais.
// Q.61.25 — via causalApi.causalGet em vez de fetch directo.
import { useQuery } from '@tanstack/react-query';
import { Panel, EmptyState } from '../../dark';
import { causalGet } from '../../../lib/api/causalApi';

export function WhyKpiPanel() {
  const q = useQuery({
    queryKey: ['kpis-snapshot-explained'],
    queryFn: () => causalGet('/kpis/snapshot-explained'),
    staleTime: 60_000,
    retry: 0,
  });

  const data = q.data as
    | { oee?: any; availability?: any; otd?: any; quality?: any }
    | undefined
    | null;

  const items = data
    ? [
        { id: 'oee', label: 'OEE', payload: data.oee },
        { id: 'availability', label: 'Disponibilidade', payload: data.availability },
        { id: 'otd', label: 'OTD', payload: data.otd },
        { id: 'quality', label: 'Qualidade', payload: data.quality },
      ]
    : [];

  return (
    <Panel
      title='"Por que?" — KPIs explicados'
      subtitle="GET /kpis/snapshot-explained (Direção/OEE/Qualidade)">
      {q.isLoading ? (
        <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>
          A carregar KPIs…
        </div>
      ) : !data ? (
        <EmptyState title="Sem snapshot disponível" hint="Backend retornou vazio. Snapshot é regenerado de hora em hora." size="sm" />
      ) : (
        <div className="space-y-2">
          {items.map((it) => (
            <details key={it.id} className="rounded-md border" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <summary className="cursor-pointer px-3 py-2 text-xs flex items-center justify-between">
                <span style={{ color: 'var(--fg-1)' }}>{it.label}</span>
                <span className="tabular-nums" style={{ color: 'var(--fg-3)' }}>
                  {typeof it.payload?.value === 'number' ? `${(it.payload.value * 100).toFixed(1)}%` : '—'}
                </span>
              </summary>
              <pre
                className="px-3 py-2 text-[10px] overflow-x-auto border-t font-mono"
                style={{ borderColor: 'var(--bd-1)', color: 'var(--fg-2)' }}
              >
                {JSON.stringify(it.payload ?? {}, null, 2).slice(0, 800)}
              </pre>
            </details>
          ))}
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 10. PoetiqPanel — POST /v1/copilot/poetiq/propose (iterative loop)
// ═══════════════════════════════════════════════════════════════════════════
