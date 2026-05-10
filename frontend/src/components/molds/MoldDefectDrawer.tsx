/**
 * MoldDefectDrawer — Onda 8 (H). Histórico defeitos por molde.
 *
 * Abre quando user clica num mold em /qualidade > Moldes.
 * Fetch GET /v1/quality/rework?mold_id={mold_id}&limit=50 (filtro
 * mold_id adicionado nesta onda).
 */

import { useQuery } from '@tanstack/react-query';
import { X, Wrench } from 'lucide-react';
import { ZipToneBadge, EmptyState } from '../dark';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
const BASE = 'http://127.0.0.1:8001';

interface ReworkRow {
  id?: string;
  detected_at?: string;
  error_code?: string;
  of_id?: string;
  phase_id_rework?: string;
  phase_id_causer?: string;
  cost_eur?: number;
  resolved_at?: string | null;
}

interface DrawerProps {
  open: boolean;
  moldId: string | null;
  moldCode?: string;
  onClose: () => void;
}

export function MoldDefectDrawer({ open, moldId, moldCode, onClose }: DrawerProps) {
  const q = useQuery({
    queryKey: ['mold-defects', moldId],
    queryFn: async () => {
      if (!moldId) return [];
      const r = await fetch(`${BASE}/v1/quality/rework?mold_id=${encodeURIComponent(moldId)}&limit=50`, { headers: TENANT });
      if (!r.ok) return [];
      return r.json();
    },
    enabled: open && !!moldId,
    retry: 0,
  });

  if (!open) return null;

  const rows = (q.data ?? []) as ReworkRow[];
  const totalCost = rows.reduce((acc, r) => acc + (r.cost_eur ?? 0), 0);
  const open_count = rows.filter((r) => !r.resolved_at).length;

  return (
    <>
      <div
        className="fixed inset-0 z-40 backdrop-blur-sm"
        style={{ background: 'rgba(0,0,0,0.4)' }}
        onClick={onClose}
      />
      <aside
        className="fixed right-0 top-0 z-50 h-full w-full max-w-xl border-l overflow-y-auto"
        style={{ background: 'var(--bg-1)', borderColor: 'var(--bd-1)' }}
      >
        <header
          className="sticky top-0 px-4 py-3 border-b flex items-center justify-between"
          style={{ background: 'var(--bg-1)', borderColor: 'var(--bd-1)' }}
        >
          <div className="flex items-center gap-2">
            <Wrench size={14} style={{ color: 'var(--fg-3)' }} />
            <div>
              <div className="text-xs uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                Histórico defeitos
              </div>
              <div className="text-sm font-semibold font-mono" style={{ color: 'var(--fg-1)' }}>
                {moldCode ?? moldId ?? '—'}
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-white/5" aria-label="Fechar">
            <X size={16} style={{ color: 'var(--fg-2)' }} />
          </button>
        </header>

        <div className="p-4 space-y-4">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                Total defeitos
              </div>
              <div className="text-lg font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                {rows.length}
              </div>
            </div>
            <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                Por resolver
              </div>
              <div className="text-lg font-semibold tabular-nums mt-1" style={{ color: open_count > 0 ? 'var(--red)' : 'var(--fg-1)' }}>
                {open_count}
              </div>
            </div>
            <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                Custo €
              </div>
              <div className="text-lg font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                €{totalCost.toFixed(0)}
              </div>
            </div>
          </div>

          {q.isLoading ? (
            <div className="px-2 py-6 text-xs text-center" style={{ color: 'var(--fg-3)' }}>
              A carregar histórico…
            </div>
          ) : rows.length === 0 ? (
            <EmptyState title="Sem defeitos registados para este molde" hint="Filtra por mold_id no endpoint /v1/quality/rework." size="sm" />
          ) : (
            <div className="overflow-x-auto rounded-md border" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <table className="w-full text-xs">
                <thead style={{ color: 'var(--fg-3)' }}>
                  <tr className="text-left">
                    <th className="px-3 py-2">Quando</th>
                    <th className="px-3 py-2">Erro</th>
                    <th className="px-3 py-2">OF</th>
                    <th className="px-3 py-2">Fase</th>
                    <th className="px-3 py-2 text-right">€</th>
                    <th className="px-3 py-2">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => (
                    <tr key={r.id ?? i} className="border-t" style={{ borderColor: 'var(--bd-1)' }}>
                      <td className="px-3 py-2 tabular-nums" style={{ color: 'var(--fg-2)' }}>
                        {r.detected_at ? new Date(r.detected_at).toLocaleDateString('pt-PT') : '—'}
                      </td>
                      <td className="px-3 py-2 font-mono" style={{ color: 'var(--fg-1)' }}>
                        {r.error_code ?? '—'}
                      </td>
                      <td className="px-3 py-2 font-mono" style={{ color: 'var(--fg-2)' }}>
                        {r.of_id ?? '—'}
                      </td>
                      <td className="px-3 py-2" style={{ color: 'var(--fg-2)' }}>
                        {r.phase_id_rework ?? r.phase_id_causer ?? '—'}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums" style={{ color: 'var(--fg-1)' }}>
                        €{(r.cost_eur ?? 0).toFixed(0)}
                      </td>
                      <td className="px-3 py-2">
                        <ZipToneBadge tone={r.resolved_at ? 'green' : 'yellow'} size="sm">
                          {r.resolved_at ? 'resolvido' : 'aberto'}
                        </ZipToneBadge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
