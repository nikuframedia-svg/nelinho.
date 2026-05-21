/**
 * TwinPanels — Onda 17 (Q). Digital Twin sandbox.
 *
 *   - GET    /v1/twin/scenarios                     (list)
 *   - POST   /v1/twin/scenarios                     (create)
 *   - POST   /v1/twin/scenarios/{id}/simulate       (run)
 *   - POST   /v1/twin/scenarios/{id}/solve          (CPO solve)
 *   - GET    /v1/twin/scenarios/{id}/compare        (diff vs baseline)
 *   - DELETE /v1/twin/scenarios/{id}                (delete)
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { FlaskConical, Play, Trash2, Plus, RotateCcw } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';
import { twinApi } from '../../lib/api';
import { twinKeys } from '../../lib/api/keys';

// Q.67.2.A — fetches directos migrados para `lib/api/copilotApi.ts:twinApi`
// (request() central injecta tenant/user/trace_id + circuit breaker).

interface Scenario {
  id?: string;
  scenario_id?: string;
  name?: string;
  description?: string;
  status?: string;
  created_at?: string;
}

export function TwinDashboard() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [newName, setNewName] = useState('');

  const listQ = useQuery({
    queryKey: twinKeys.scenarios(),
    queryFn: async () => {
      try {
        return await twinApi.listScenarios();
      } catch {
        return [] as Scenario[];
      }
    },
    staleTime: 30_000,
    retry: 0,
  });

  const scenarios = (listQ.data ?? []) as Scenario[];

  const createM = useMutation({
    // Backend espera `title` no body — twinApi central já reflecte isso
    // (lib/api/copilotApi.ts:twinApi.createScenario).
    mutationFn: () =>
      twinApi.createScenario({ title: newName.trim(), description: 'Criado via UI Onda 17' }),
    onSuccess: () => {
      setNewName('');
      qc.invalidateQueries({ queryKey: twinKeys.scenarios() });
    },
  });

  const simulateM = useMutation({
    mutationFn: (id: string) => twinApi.simulate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: twinKeys.scenarios() }),
  });

  const solveM = useMutation({
    mutationFn: (id: string) => twinApi.solve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: twinKeys.compare(selected) }),
  });

  const deleteM = useMutation({
    mutationFn: async (id: string) => {
      await twinApi.deleteScenario(id);
      if (selected === id) setSelected(null);
      return true;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: twinKeys.scenarios() }),
  });

  const compareQ = useQuery({
    queryKey: twinKeys.compare(selected),
    queryFn: async () => {
      if (!selected) return null;
      try {
        return await twinApi.compare(selected);
      } catch {
        return null;
      }
    },
    enabled: !!selected,
    retry: 0,
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs flex items-center gap-2" style={{ color: 'var(--fg-2)' }}>
          <FlaskConical size={13} />
          Digital twin sandbox · scenarios CRUD + simulate + solve
        </span>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda17 — Q. Twin
        </span>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="Scenarios" subtitle="Cria · simula · solve · apaga" badge={scenarios.length || '—'}>
          <div className="space-y-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Nome do novo scenario"
                className="flex-1 rounded-md border px-2 py-1.5 text-xs"
                style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
              />
              <button
                type="button"
                onClick={() => createM.mutate()}
                disabled={!newName.trim() || createM.isPending}
                className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium"
                style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
              >
                <Plus size={12} />
                Novo
              </button>
            </div>
            {listQ.isLoading ? (
              <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
            ) : scenarios.length === 0 ? (
              <EmptyState title="Sem scenarios" hint="Cria um scenario para começar." size="sm" />
            ) : (
              <div className="space-y-1">
                {scenarios.map((s) => {
                  const id = s.id ?? s.scenario_id ?? '';
                  return (
                    <div
                      key={id}
                      className="rounded-md border p-2 flex items-center gap-2 text-xs"
                      style={{
                        background: selected === id ? 'var(--bg-3)' : 'var(--bg-2)',
                        borderColor: selected === id ? 'var(--blue)' : 'var(--bd-1)',
                      }}
                    >
                      <button
                        type="button"
                        onClick={() => setSelected(id)}
                        className="flex-1 text-left"
                        style={{ color: 'var(--fg-1)' }}
                      >
                        <div className="font-mono">{s.name ?? id.slice(0, 8)}</div>
                        {s.status && (
                          <ZipToneBadge tone={s.status === 'simulated' ? 'green' : 'gray'} size="sm">
                            {s.status}
                          </ZipToneBadge>
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => simulateM.mutate(id)}
                        disabled={simulateM.isPending}
                        className="p-1 rounded hover:bg-white/5"
                        title="Simulate"
                      >
                        <Play size={11} style={{ color: 'var(--blue)' }} />
                      </button>
                      <button
                        type="button"
                        onClick={() => solveM.mutate(id)}
                        disabled={solveM.isPending}
                        className="p-1 rounded hover:bg-white/5"
                        title="Solve (CPO)"
                      >
                        <RotateCcw size={11} style={{ color: 'var(--green)' }} />
                      </button>
                      <button
                        type="button"
                        onClick={() => deleteM.mutate(id)}
                        disabled={deleteM.isPending}
                        className="p-1 rounded hover:bg-white/5"
                        title="Apagar"
                      >
                        <Trash2 size={11} style={{ color: 'var(--red)' }} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </Panel>

        <Panel
          title={selected ? 'Compare vs baseline' : 'Selecciona scenario'}
          subtitle="GET /v1/twin/scenarios/{id}/compare"
        >
          {!selected ? (
            <EmptyState title="Sem scenario seleccionado" size="sm" />
          ) : compareQ.isFetching ? (
            <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar diff…</div>
          ) : !compareQ.data ? (
            <EmptyState title="Scenario ainda não simulado" hint="Click ▶ para simulate." size="sm" />
          ) : (
            <pre
              className="text-[10px] font-mono overflow-x-auto rounded-md border p-3 max-h-96"
              style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-2)' }}
            >
              {JSON.stringify(compareQ.data, null, 2)}
            </pre>
          )}
        </Panel>
      </div>

      <div className="text-[10px] flex items-center gap-2 px-1" style={{ color: 'var(--fg-3)' }}>
        ScenarioDiffViewer + ScenarioTemplatesGallery ✓ já wired em /admin/twin (legacy).
      </div>
    </div>
  );
}
