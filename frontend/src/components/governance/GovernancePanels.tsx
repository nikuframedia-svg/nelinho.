/**
 * GovernancePanels — Onda 14 (N).
 *
 *   1. EventOutboxPanel — GET /v1/governance/event-outbox
 *   2. RbacMatrixPanel  — GET /v1/governance/rbac/matrix
 *   3. DecisionRollbackPanel — POST /v1/governance/decisions/{id}/rollback
 */

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Activity, Shield, RotateCcw } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';
import { getApiBase } from '../../lib/api';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const BASE = getApiBase();

// ═══════════════════════════════════════════════════════════════════════════
// 1. EventOutboxPanel
// ═══════════════════════════════════════════════════════════════════════════

interface OutboxRow {
  id?: string;
  event_type?: string;
  status?: string;
  aggregate_id?: string | null;
  payload_keys?: string[];
  created_at?: string;
}

export function EventOutboxPanel() {
  const [filter, setFilter] = useState<'all' | 'pending' | 'sent' | 'failed'>('all');
  const q = useQuery({
    queryKey: ['event-outbox', filter],
    queryFn: async () => {
      const url = filter === 'all'
        ? `${BASE}/v1/governance/event-outbox?limit=80`
        : `${BASE}/v1/governance/event-outbox?status_filter=${filter}&limit=80`;
      const r = await fetch(url, { headers: TENANT });
      if (!r.ok) return { items: [] as OutboxRow[] };
      return r.json();
    },
    staleTime: 30_000,
    retry: 0,
  });

  const items = ((q.data as { items?: OutboxRow[] } | undefined)?.items ?? []) as OutboxRow[];

  return (
    <Panel
      title="Activity outbox ledger"
      subtitle="Eventos publicados pelo backend (Kafka via OutboxDispatcher)"
      badge={items.length || '—'}
    >
      <div className="space-y-3">
        <div className="flex gap-1">
          {(['all', 'pending', 'sent', 'failed'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className="rounded-md px-2.5 py-1 text-xs"
              style={{
                background: filter === f ? 'var(--bg-3)' : 'var(--bg-2)',
                color: filter === f ? 'var(--fg-1)' : 'var(--fg-3)',
                border: '1px solid var(--bd-1)',
              }}
            >
              {f}
            </button>
          ))}
        </div>
        {q.isLoading ? (
          <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
        ) : items.length === 0 ? (
          <EmptyState title="Outbox vazio" hint="Sem eventos no filtro." size="sm" />
        ) : (
          <div className="overflow-x-auto rounded-md border" style={{ borderColor: 'var(--bd-1)' }}>
            <table className="w-full text-xs">
              <thead style={{ color: 'var(--fg-3)' }}>
                <tr className="text-left">
                  <th className="px-3 py-2">Quando</th>
                  <th className="px-3 py-2">Evento</th>
                  <th className="px-3 py-2">Aggregate</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.slice(0, 50).map((r, i) => (
                  <tr key={r.id ?? i} className="border-t" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                    <td className="px-3 py-2 tabular-nums" style={{ color: 'var(--fg-2)' }}>
                      {r.created_at ? new Date(r.created_at).toLocaleString('pt-PT') : '—'}
                    </td>
                    <td className="px-3 py-2 font-mono" style={{ color: 'var(--fg-1)' }}>{r.event_type ?? '—'}</td>
                    <td className="px-3 py-2 font-mono text-[10px]" style={{ color: 'var(--fg-3)' }}>
                      {r.aggregate_id ? r.aggregate_id.slice(0, 12) : '—'}
                    </td>
                    <td className="px-3 py-2">
                      <ZipToneBadge tone={r.status === 'sent' ? 'green' : r.status === 'failed' ? 'red' : 'yellow'} size="sm">
                        {r.status ?? '—'}
                      </ZipToneBadge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 2. RbacMatrixPanel
// ═══════════════════════════════════════════════════════════════════════════

export function RbacMatrixPanel() {
  const q = useQuery({
    queryKey: ['rbac-matrix'],
    queryFn: async () => {
      const r = await fetch(`${BASE}/v1/governance/rbac/matrix`, { headers: TENANT });
      if (!r.ok) return null;
      return r.json();
    },
    staleTime: 5 * 60_000,
    retry: 0,
  });

  const data = q.data as
    | { roles?: string[]; permissions?: string[]; matrix?: Record<string, string[]> }
    | undefined
    | null;

  return (
    <Panel title="RBAC matrix" subtitle="Roles × Permissions actual (Q.18 N)">
      {q.isLoading ? (
        <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
      ) : !data ? (
        <EmptyState title="Endpoint indisponível" size="sm" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead style={{ color: 'var(--fg-3)' }}>
              <tr>
                <th className="px-2 py-1 text-left">Permission</th>
                {(data.roles ?? []).map((role) => (
                  <th key={role} className="px-2 py-1 text-center font-mono" style={{ minWidth: 80 }}>
                    {role.replace(/_/g, ' ').toLowerCase()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data.permissions ?? []).map((perm) => (
                <tr key={perm} className="border-t" style={{ borderColor: 'var(--bd-1)' }}>
                  <td className="px-2 py-1 font-mono" style={{ color: 'var(--fg-1)' }}>{perm}</td>
                  {(data.roles ?? []).map((role) => {
                    const has = (data.matrix?.[role] ?? []).includes(perm);
                    return (
                      <td key={role} className="px-2 py-1 text-center">
                        {has ? <span style={{ color: 'var(--green)' }}>●</span> : <span style={{ color: 'var(--fg-3)' }}>·</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 3. DecisionRollbackPanel
// ═══════════════════════════════════════════════════════════════════════════

export function DecisionRollbackPanel() {
  const [decisionId, setDecisionId] = useState('');

  const m = useMutation({
    mutationFn: async () => {
      if (!decisionId.trim()) throw new Error('Decision ID obrigatório.');
      const r = await fetch(`${BASE}/v1/governance/decisions/${encodeURIComponent(decisionId.trim())}/rollback`, {
        method: 'POST',
        headers: TENANT,
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
  });

  return (
    <Panel title="Decision rollback" subtitle="POST /v1/governance/decisions/{id}/rollback (chain hash verified)">
      <div className="space-y-3">
        <input
          type="text"
          value={decisionId}
          onChange={(e) => setDecisionId(e.target.value)}
          placeholder="decision_id (UUID)"
          className="w-full rounded-md border px-2 py-1.5 text-xs font-mono"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
        />
        <button
          type="button"
          onClick={() => m.mutate()}
          disabled={!decisionId.trim() || m.isPending}
          className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--red-bg)', color: 'var(--red)' }}
        >
          <RotateCcw size={12} />
          {m.isPending ? 'A reverter…' : 'Rollback decisão'}
        </button>
        {m.isSuccess && (
          <div className="rounded-md border p-3 text-xs" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)', color: 'var(--green)' }}>
            ✓ Rollback registado.
            <pre className="mt-2 text-[10px] overflow-x-auto" style={{ color: 'var(--fg-2)' }}>
              {JSON.stringify(m.data, null, 2).slice(0, 400)}
            </pre>
          </div>
        )}
        {m.isError && (
          <div className="text-xs" style={{ color: 'var(--red)' }}>
            Erro: {(m.error as Error).message}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Composição
// ═══════════════════════════════════════════════════════════════════════════

export function GovernanceDashboard() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs flex items-center gap-2" style={{ color: 'var(--fg-2)' }}>
          <Activity size={13} />
          Outbox ledger · RBAC matrix · Decision rollback
        </span>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda14 — N. Governance
        </span>
      </div>
      <div className="grid grid-cols-1 gap-4">
        <EventOutboxPanel />
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <RbacMatrixPanel />
          <DecisionRollbackPanel />
        </div>
      </div>
      <div className="text-xs flex items-center gap-2 px-1" style={{ color: 'var(--fg-3)' }}>
        <Shield size={12} />
        Audit per-user filter: ✓ live em /admin/audit-trail (AuditTrailPage)
      </div>
    </div>
  );
}
