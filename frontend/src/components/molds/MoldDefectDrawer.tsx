/**
 * MoldDefectDrawer — Onda 8 (H). Histórico defeitos por molde.
 *
 * Abre quando user clica num mold em /qualidade > Moldes.
 * Fetch GET /v1/quality/rework?mold_id={mold_id}&limit=50 (filtro
 * mold_id adicionado nesta onda).
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { X, Wrench, Plus, Play, Check, CalendarClock } from 'lucide-react';
import { ZipToneBadge, EmptyState } from '../dark';
import { getApiBase, moldsApi, type MoldMaintenanceEvent } from '../../lib/api';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const BASE = getApiBase();

interface ReworkRow {
  id?: string;
  detected_at?: string;
  error_code?: string;
  of_id?: string;
  phase_id_rework?: string;
  phase_id_causer?: string;
  // Q.154.D — nomes humanos das fases (backend resolve via routing_template_phase).
  phase_name_rework?: string | null;
  phase_name_causer?: string | null;
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
          {moldId ? <MoldMaintenanceSection moldId={moldId} /> : null}

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
                        {r.phase_name_rework ??
                          r.phase_name_causer ??
                          r.phase_id_rework ??
                          r.phase_id_causer ??
                          '—'}
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

// ─── Q.31.B — Manutenção do molde (planear / iniciar / concluir) ─────────────

const MNT_FIELD =
  'w-full px-2.5 py-1.5 rounded-md text-xs';

function moldFieldStyle(): React.CSSProperties {
  return {
    background: 'var(--bg-2)',
    border: '1px solid var(--bd-1)',
    color: 'var(--fg-1)',
  };
}

function MoldMaintenanceSection({ moldId }: { moldId: string }) {
  const queryClient = useQueryClient();
  const [plannedDate, setPlannedDate] = useState('');
  const [type, setType] = useState('preventive');
  const [comments, setComments] = useState('');

  const q = useQuery({
    queryKey: ['mold-maintenance', moldId],
    queryFn: () => moldsApi.listMaintenance(moldId),
    retry: 0,
  });
  const events = (q.data ?? []) as MoldMaintenanceEvent[];

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['mold-maintenance', moldId] });

  const planMut = useMutation({
    mutationFn: () =>
      moldsApi.planMaintenance(moldId, {
        planned_date: plannedDate,
        maintenance_type: type,
        comments: comments.trim() || undefined,
      }),
    onSuccess: () => {
      setPlannedDate('');
      setComments('');
      invalidate();
    },
  });
  const startMut = useMutation({
    mutationFn: (eventId: string) => moldsApi.startMaintenance(eventId),
    onSuccess: invalidate,
  });
  const completeMut = useMutation({
    mutationFn: (eventId: string) => moldsApi.completeMaintenance(eventId, {}),
    onSuccess: invalidate,
  });

  const busy = planMut.isPending || startMut.isPending || completeMut.isPending;

  return (
    <div
      className="rounded-md border p-3 space-y-3"
      style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}
    >
      <div className="flex items-center gap-2">
        <CalendarClock size={13} style={{ color: 'var(--fg-3)' }} />
        <span className="text-xs font-semibold" style={{ color: 'var(--fg-1)' }}>
          Manutenção
        </span>
      </div>

      {/* Planear */}
      <form
        className="grid grid-cols-2 gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (plannedDate && !busy) planMut.mutate();
        }}
      >
        <input
          type="date"
          value={plannedDate}
          onChange={(e) => setPlannedDate(e.target.value)}
          className={MNT_FIELD}
          style={moldFieldStyle()}
          required
        />
        <select
          value={type}
          onChange={(e) => setType(e.target.value)}
          className={MNT_FIELD}
          style={moldFieldStyle()}
        >
          <option value="preventive">Preventiva</option>
          <option value="corrective">Correctiva</option>
        </select>
        <input
          type="text"
          value={comments}
          onChange={(e) => setComments(e.target.value)}
          placeholder="Notas (opcional)"
          className={`${MNT_FIELD} col-span-2`}
          style={moldFieldStyle()}
        />
        <button
          type="submit"
          disabled={!plannedDate || busy}
          className="col-span-2 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-white text-xs font-semibold disabled:opacity-50 transition-colors"
          style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
        >
          <Plus size={12} />
          {planMut.isPending ? 'A planear…' : 'Planear manutenção'}
        </button>
      </form>

      {/* Eventos */}
      {q.isLoading ? (
        <div className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
          A carregar manutenções…
        </div>
      ) : events.length === 0 ? (
        <div className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
          Sem manutenções registadas para este molde.
        </div>
      ) : (
        <div className="space-y-1.5">
          {events.map((ev) => {
            const done = !!ev.completed_at;
            const running = !!ev.started_at && !done;
            return (
              <div
                key={ev.id}
                className="flex items-center justify-between gap-2 rounded-md border px-2.5 py-1.5"
                style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-1)' }}
              >
                <div className="min-w-0">
                  <div className="text-xs" style={{ color: 'var(--fg-1)' }}>
                    {ev.maintenance_type === 'corrective' ? 'Correctiva' : 'Preventiva'}
                    {ev.planned_date ? ` · ${ev.planned_date}` : ''}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <ZipToneBadge
                    tone={done ? 'green' : running ? 'yellow' : 'blue'}
                    size="sm"
                  >
                    {done ? 'concluída' : running ? 'em curso' : 'planeada'}
                  </ZipToneBadge>
                  {!ev.started_at && !done ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => startMut.mutate(ev.id)}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] hover:bg-white/5 disabled:opacity-50"
                      style={{ color: 'var(--fg-1)', border: '1px solid var(--bd-1)' }}
                    >
                      <Play size={11} /> Iniciar
                    </button>
                  ) : null}
                  {running ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => completeMut.mutate(ev.id)}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] hover:bg-white/5 disabled:opacity-50"
                      style={{ color: 'var(--green)', border: '1px solid var(--bd-1)' }}
                    >
                      <Check size={11} /> Concluir
                    </button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
