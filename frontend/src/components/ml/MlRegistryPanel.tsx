/**
 * MlRegistryPanel — Onda 16 (P).
 *
 *   - GET  /v1/ml/models                                        (lista nomes)
 *   - GET  /v1/ml/models/{name}/versions                        (versões)
 *   - GET  /v1/ml/models/{name}/active                          (versão ativa)
 *   - POST /v1/ml/models/{name}/versions/{artifact_id}/promote  (promote/rollback)
 *
 * Promote para versão anterior actua como rollback.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Box, Star, RotateCcw, ChevronRight } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
const BASE = 'http://127.0.0.1:8001';

interface Artifact {
  id?: string;
  artifact_id?: string;
  model_name?: string;
  version?: string;
  metrics?: Record<string, any>;
  created_at?: string;
  is_active?: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════
// MlRegistryPanel
// ═══════════════════════════════════════════════════════════════════════════

export function MlRegistryPanel() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);

  const modelsQ = useQuery({
    queryKey: ['ml-models'],
    queryFn: async () => {
      const r = await fetch(`${BASE}/v1/ml/models`, { headers: TENANT });
      if (!r.ok) return [] as string[];
      return r.json();
    },
    staleTime: 60_000,
    retry: 0,
  });

  const versionsQ = useQuery({
    queryKey: ['ml-versions', selected],
    queryFn: async () => {
      if (!selected) return [] as Artifact[];
      const r = await fetch(`${BASE}/v1/ml/models/${encodeURIComponent(selected)}/versions?limit=20`, { headers: TENANT });
      if (!r.ok) return [] as Artifact[];
      return r.json();
    },
    enabled: !!selected,
    retry: 0,
  });

  const activeQ = useQuery({
    queryKey: ['ml-active', selected],
    queryFn: async () => {
      if (!selected) return null;
      const r = await fetch(`${BASE}/v1/ml/models/${encodeURIComponent(selected)}/active`, { headers: TENANT });
      if (!r.ok) return null;
      return r.json();
    },
    enabled: !!selected,
    retry: 0,
  });

  const models = (modelsQ.data ?? []) as string[];
  const versions = (versionsQ.data ?? []) as Artifact[];
  const active = activeQ.data as Artifact | null | undefined;
  const activeId = (active as any)?.id ?? (active as any)?.artifact_id ?? null;

  const promoteM = useMutation({
    mutationFn: async (artifactId: string) => {
      const r = await fetch(`${BASE}/v1/ml/models/${encodeURIComponent(selected!)}/versions/${artifactId}/promote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...TENANT },
        body: JSON.stringify({ via_governance: true }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['ml-active', selected] });
      qc.invalidateQueries({ queryKey: ['ml-versions', selected] });
    },
  });

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
      {/* Models list */}
      <Panel title="ML models" subtitle="Registry · versões treinadas" badge={models.length || '—'}>
        {modelsQ.isLoading ? (
          <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
        ) : models.length === 0 ? (
          <EmptyState title="Sem modelos registados" hint="Treinar modelos via /v1/ml/train (sub-sprint P)." size="sm" />
        ) : (
          <div className="space-y-1">
            {models.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setSelected(m)}
                className="w-full flex items-center justify-between rounded-md px-3 py-2 text-xs transition-colors"
                style={{
                  background: selected === m ? 'var(--bg-3)' : 'var(--bg-2)',
                  color: selected === m ? 'var(--fg-1)' : 'var(--fg-2)',
                  border: '1px solid var(--bd-1)',
                }}
              >
                <span className="flex items-center gap-2 font-mono">
                  <Box size={12} />
                  {m}
                </span>
                {selected === m && <ChevronRight size={12} />}
              </button>
            ))}
          </div>
        )}
      </Panel>

      {/* Versions */}
      <Panel
        title={selected ? `Versões — ${selected}` : 'Selecciona modelo'}
        subtitle="Promote / rollback (admin)"
        badge={versions.length || '—'}
        className="xl:col-span-2"
      >
        {!selected ? (
          <EmptyState title="Sem modelo seleccionado" size="sm" />
        ) : versionsQ.isLoading ? (
          <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
        ) : versions.length === 0 ? (
          <EmptyState title="Sem versões" size="sm" />
        ) : (
          <div className="space-y-2">
            {versions.map((v) => {
              const id = v.id ?? v.artifact_id ?? '';
              const isActive = id === activeId;
              const wmape = v.metrics?.wmape ?? v.metrics?.WMAPE;
              return (
                <div
                  key={id}
                  className="rounded-md border p-3"
                  style={{
                    borderColor: isActive ? 'var(--green)' : 'var(--bd-1)',
                    background: 'var(--bg-2)',
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      {isActive && <Star size={12} style={{ color: 'var(--green)' }} fill="currentColor" />}
                      <span className="font-mono text-xs" style={{ color: 'var(--fg-1)' }}>
                        v{v.version ?? '?'} · {id.slice(0, 8)}
                      </span>
                      {isActive && <ZipToneBadge tone="green" size="sm">Active</ZipToneBadge>}
                    </div>
                    <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
                      {v.created_at ? new Date(v.created_at).toLocaleDateString('pt-PT') : '—'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span style={{ color: 'var(--fg-3)' }}>
                      {typeof wmape === 'number' ? `WMAPE ${(wmape * 100).toFixed(1)}%` : '—'}
                    </span>
                    {!isActive && (
                      <button
                        type="button"
                        onClick={() => promoteM.mutate(id)}
                        disabled={promoteM.isPending}
                        className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[10px] font-medium"
                        style={{
                          background: 'var(--blue-bg)',
                          color: 'var(--blue)',
                        }}
                      >
                        {promoteM.isPending ? '…' : (
                          <>
                            <RotateCcw size={10} />
                            Promote
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
            {promoteM.isError && (
              <div className="text-xs" style={{ color: 'var(--red)' }}>
                Erro: {(promoteM.error as Error).message} (precisa role admin se via_governance=false)
              </div>
            )}
            {promoteM.isSuccess && (
              <ZipToneBadge tone="green" size="sm">Promoção registada</ZipToneBadge>
            )}
          </div>
        )}
      </Panel>
    </div>
  );
}

export function MlRegistryDashboard() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs flex items-center gap-2" style={{ color: 'var(--fg-2)' }}>
          <Box size={13} />
          ML model registry — list / promote / rollback (Promote para versão anterior)
        </span>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda16 — P. ML
        </span>
      </div>
      <MlRegistryPanel />
    </div>
  );
}
