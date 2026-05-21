/**
 * FactoryPulsePanels — Onda 15 (O). Data Product semantic queries.
 *
 * GET /v1/factory/semantic — lista todas as views allow-listed (7 views).
 * GET /v1/factory/semantic/{view_id} — query individual com paginação.
 * GET /v1/factory/semantic/blocked-metrics — métricas bloqueadas.
 *
 * Renderiza como dashboard "Factory pulse" com card por view.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Database, Activity, Lock } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';
import { dataProductApi } from '../../lib/api';
import { dataProductKeys } from '../../lib/api/keys';
import type { SemanticView } from '../../lib/api/dataProductApi';

// ═══════════════════════════════════════════════════════════════════════════
// FactoryPulseListPanel — todas as views
// ═══════════════════════════════════════════════════════════════════════════

export function FactoryPulseListPanel({ onSelect }: { onSelect?: (id: string, name: string) => void }) {
  const q = useQuery({
    queryKey: dataProductKeys.semanticViews(),
    queryFn: () => dataProductApi.listSemanticViews().catch(() => null),
    staleTime: 5 * 60_000,
    retry: 0,
  });

  const data = q.data as { views?: SemanticView[] } | undefined | null;
  const views = data?.views ?? [];

  return (
    <Panel title="Factory pulse — semantic views" subtitle="Allow-listed queries (read-only, anti-SQL-injection)" badge={views.length || '—'}>
      {q.isLoading ? (
        <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
      ) : views.length === 0 ? (
        <EmptyState title="Sem semantic views" hint="Endpoint /v1/factory/semantic devolveu vazio." size="sm" />
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
          {views.map((v) => (
            <button
              key={v.view_id}
              type="button"
              onClick={() => onSelect?.(v.view_id, v.name)}
              className="text-left rounded-md border p-3 hover:opacity-90 transition-opacity"
              style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <span className="font-mono text-xs" style={{ color: 'var(--fg-1)' }}>{v.view_id}</span>
                <div className="flex items-center gap-1">
                  {v.is_sensitive && (
                    <ZipToneBadge tone="red" size="sm">
                      <Lock size={9} className="inline mr-1" />sensible
                    </ZipToneBadge>
                  )}
                  {typeof v.trust_score === 'number' && (
                    <ZipToneBadge tone={v.trust_score >= 0.8 ? 'green' : v.trust_score >= 0.5 ? 'yellow' : 'red'} size="sm">
                      trust {(v.trust_score * 100).toFixed(0)}%
                    </ZipToneBadge>
                  )}
                </div>
              </div>
              <div className="text-xs" style={{ color: 'var(--fg-2)' }}>{v.name}</div>
              {v.description && (
                <div className="text-[10px] mt-1" style={{ color: 'var(--fg-3)' }}>
                  {v.description.slice(0, 120)}
                </div>
              )}
            </button>
          ))}
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// FactoryPulseQueryPanel — query individual
// ═══════════════════════════════════════════════════════════════════════════

export function FactoryPulseQueryPanel({ viewId, name }: { viewId: string | null; name: string | null }) {
  const q = useQuery({
    queryKey: dataProductKeys.semanticQuery(viewId),
    queryFn: () => {
      if (!viewId) return null;
      return dataProductApi.querySemanticView(viewId, 15).catch(() => null);
    },
    enabled: !!viewId,
    retry: 0,
  });

  const data = q.data as
    | { view_id?: string; rows?: any[]; row_count?: number; fields?: string[]; trust_score?: number; disclaimers?: string[] }
    | undefined
    | null;

  const rows = data?.rows ?? [];
  const fields = data?.fields ?? (rows[0] ? Object.keys(rows[0]) : []);

  return (
    <Panel
      title={name ?? 'Selecciona view'}
      subtitle={viewId ?? '—'}
      badge={typeof data?.row_count === 'number' ? data.row_count : (rows.length || '—')}
    >
      {!viewId ? (
        <EmptyState title="Sem view seleccionada" hint="Clica num card à esquerda." size="sm" />
      ) : q.isFetching ? (
        <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
      ) : !data ? (
        <EmptyState title="Erro ao carregar view" size="sm" />
      ) : (
        <>
          {data.disclaimers && data.disclaimers.length > 0 && (
            <div className="mb-2 px-3 py-2 rounded text-[10px]" style={{ background: 'var(--yellow-bg)', color: 'var(--yellow)' }}>
              ⚠ {data.disclaimers.join(' · ')}
            </div>
          )}
          {rows.length === 0 ? (
            <EmptyState title="View vazia" size="sm" />
          ) : (
            <div className="overflow-x-auto rounded-md border" style={{ borderColor: 'var(--bd-1)' }}>
              <table className="w-full text-[11px]">
                <thead style={{ color: 'var(--fg-3)' }}>
                  <tr className="text-left">
                    {fields.slice(0, 6).map((f) => (
                      <th key={f} className="px-2 py-1.5 font-mono">{f}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 15).map((row, i) => (
                    <tr key={i} className="border-t" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                      {fields.slice(0, 6).map((f) => (
                        <td key={f} className="px-2 py-1.5 truncate max-w-[150px]" style={{ color: 'var(--fg-1)' }}>
                          {String(row[f] ?? '—').slice(0, 40)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Composição
// ═══════════════════════════════════════════════════════════════════════════

export function FactoryPulseDashboard() {
  const [selected, setSelected] = useState<{ id: string | null; name: string | null }>({ id: null, name: null });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs flex items-center gap-2" style={{ color: 'var(--fg-2)' }}>
          <Database size={13} />
          Factory data product · semantic views
        </span>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda15 — O. Data Product
        </span>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <FactoryPulseListPanel onSelect={(id, name) => setSelected({ id, name })} />
        <FactoryPulseQueryPanel viewId={selected.id} name={selected.name} />
      </div>
      <div className="text-[10px] flex items-center gap-2 px-1" style={{ color: 'var(--fg-3)' }}>
        <Activity size={10} />
        Excel ingest + activate/rollback + Quality report ✓ live em /admin/data-quality (DataQualityPage).
      </div>
    </div>
  );
}
