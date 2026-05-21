/**
 * OperationsDashboard — Ondas 21-27 (AA-GG). 7 features esquecidas.
 *
 * AA. Health Checks UI       — GET /health/ready + /health/live
 * BB. Observability OTel/Sentry — embed in /health/ready (tracing flag)
 * CC. Rate Limiting Status   — GET /v1/copilot/diagnose
 * DD. Authentication UI      — GET /v1/auth/me (claims)
 * EE. Soft Delete UI         — POST /v1/workforce/employees/{id}/soft-delete
 * FF. Bulk Operations UI     — POST /v1/governance/decisions/bulk
 * GG. Background Scheduler   — placeholder (sem endpoint admin)
 */

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Activity, Trash2, CheckSquare } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';
import { opsApi } from '../../lib/api';
import { opsKeys } from '../../lib/api/keys';

// Q.67.2.A — fetches directos migrados para `lib/api/opsApi.ts`
// (request() central injecta tenant/user/trace_id + circuit breaker).

// ═══════════════════════════════════════════════════════════════════════════
// AA + BB. Health & OTel
// ═══════════════════════════════════════════════════════════════════════════

export function HealthPanel() {
  const readyQ = useQuery({
    queryKey: opsKeys.healthReady(),
    queryFn: () => opsApi.getHealthReady(),
    refetchInterval: 30_000,
    retry: 0,
  });

  const liveQ = useQuery({
    queryKey: opsKeys.healthLive(),
    queryFn: async () => {
      const r = await opsApi.getHealthLive();
      return { ok: r.ok, status: r.status };
    },
    refetchInterval: 30_000,
    retry: 0,
  });

  const ready = readyQ.data;
  const live = liveQ.data;
  const checks = (ready?.body as any)?.checks ?? {};

  return (
    <Panel title="Health checks (AA + BB)" subtitle="GET /health/ready + /health/live · OTel + Sentry status">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>Liveness</div>
            <ZipToneBadge tone={live?.ok ? 'green' : 'red'} size="sm">
              {live?.ok ? 'alive' : `dead (${live?.status ?? '—'})`}
            </ZipToneBadge>
          </div>
          <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>Readiness</div>
            <ZipToneBadge tone={ready?.ok ? 'green' : 'red'} size="sm">
              {ready?.ok ? 'ready' : `not ready (${ready?.status ?? '—'})`}
            </ZipToneBadge>
          </div>
        </div>
        {Object.keys(checks).length > 0 && (
          <div className="rounded-md border p-3 text-xs space-y-1" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--fg-3)' }}>Checks</div>
            {Object.entries(checks).map(([k, v]) => (
              <div key={k} className="flex items-center justify-between">
                <span className="font-mono" style={{ color: 'var(--fg-2)' }}>{k}</span>
                <ZipToneBadge tone={v ? 'green' : 'red'} size="sm">
                  {v ? 'ok' : 'fail'}
                </ZipToneBadge>
              </div>
            ))}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// CC. Rate Limit
// ═══════════════════════════════════════════════════════════════════════════

export function RateLimitPanel() {
  const q = useQuery({
    queryKey: opsKeys.copilotDiagnose(),
    queryFn: async () => {
      try {
        return await opsApi.getCopilotDiagnose();
      } catch {
        return null;
      }
    },
    staleTime: 60_000,
    retry: 0,
  });

  const data = q.data as any;
  const rl = data?.rate_limit ?? {};

  return (
    <Panel title="Rate limit (CC)" subtitle="GET /api/copilot/diagnose — Copilot quota Redis Lua atomic">
      {q.isLoading ? (
        <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
      ) : !data ? (
        <EmptyState title="Diagnose indisponível" hint="Endpoint /api/copilot/diagnose pode requerer JWT." size="sm" />
      ) : (
        <div className="grid grid-cols-2 gap-2 text-xs">
          {Object.entries(rl).slice(0, 6).map(([k, v]) => (
            <div key={k} className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>{k}</div>
              <div className="font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                {String(v)}
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// DD. Authentication
// ═══════════════════════════════════════════════════════════════════════════

export function AuthPanel() {
  const q = useQuery({
    queryKey: opsKeys.authMe(),
    queryFn: async () => {
      try {
        return await opsApi.getAuthMe();
      } catch {
        return null;
      }
    },
    staleTime: 5 * 60_000,
    retry: 0,
  });

  const me = q.data as any;

  return (
    <Panel title="Authentication (DD)" subtitle="GET /v1/auth/me — claims do JWT (ou dev fallback)">
      {q.isLoading ? (
        <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
      ) : !me ? (
        <EmptyState title="Sem auth/me" size="sm" />
      ) : (
        <div className="space-y-2 text-xs">
          {[
            ['User ID', me.user_id],
            ['Tenant ID', me.tenant_id],
            ['Role', me.role],
            ['Name', me.name],
            ['Email', me.email],
            ['Umwelt', me.umwelt],
          ].map(([k, v]) => (
            <div key={k as string} className="flex justify-between border-b pb-1" style={{ borderColor: 'var(--bd-1)' }}>
              <span style={{ color: 'var(--fg-3)' }}>{k}</span>
              <span className="font-mono" style={{ color: 'var(--fg-1)' }}>{String(v ?? '—').slice(0, 40)}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// EE. Soft Delete
// ═══════════════════════════════════════════════════════════════════════════

export function SoftDeletePanel() {
  const [empId, setEmpId] = useState('');
  const [reason, setReason] = useState('');

  const m = useMutation({
    mutationFn: async () => {
      if (!empId.trim()) throw new Error('Employee ID obrigatório.');
      return opsApi.softDeleteEmployee(empId.trim(), reason);
    },
  });

  return (
    <Panel title="Soft delete (EE)" subtitle="POST /v1/workforce/employees/{id}/soft-delete">
      <div className="space-y-3">
        <input type="text" value={empId} onChange={(e) => setEmpId(e.target.value)}
          placeholder="employee_id (UUID)"
          className="w-full rounded-md border px-2 py-1.5 text-xs font-mono"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
        <input type="text" value={reason} onChange={(e) => setReason(e.target.value)}
          placeholder="razão (opcional)"
          className="w-full rounded-md border px-2 py-1.5 text-xs"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
        <button
          onClick={() => m.mutate()}
          disabled={!empId.trim() || m.isPending}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--red-bg)', color: 'var(--red)' }}
        >
          <Trash2 size={12} />
          {m.isPending ? '…' : 'Soft-delete (TERMINATED)'}
        </button>
        {m.isSuccess && (
          <ZipToneBadge tone="green" size="sm">
            Status: {(m.data as any)?.status ?? 'OK'}
          </ZipToneBadge>
        )}
        {m.isError && (
          <div className="text-xs" style={{ color: 'var(--red)' }}>
            {(m.error as Error).message}
          </div>
        )}
        <div className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Restore endpoint ainda não exposto — preserva history em DB (status=TERMINATED).
        </div>
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// FF. Bulk Operations
// ═══════════════════════════════════════════════════════════════════════════

export function BulkOperationsPanel() {
  const [ids, setIds] = useState('');
  const [action, setAction] = useState<'approve' | 'reject'>('approve');
  const [reason, setReason] = useState('Bulk via UI Ops dashboard');

  const m = useMutation({
    mutationFn: async () => {
      const list = ids.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
      if (list.length === 0) throw new Error('Pelo menos um decision_id.');
      const items = list.map((id) => ({ decision_id: id, action, reason }));
      return opsApi.bulkDecisions(items);
    },
  });

  const data = m.data as any;

  return (
    <Panel title="Bulk operations (FF)" subtitle="POST /v1/governance/decisions/bulk — approve/reject lote">
      <div className="space-y-3">
        <textarea value={ids} onChange={(e) => setIds(e.target.value)} rows={3}
          placeholder="decision_ids (csv ou um por linha)"
          className="w-full rounded-md border px-2 py-1.5 text-xs font-mono"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
        <div className="grid grid-cols-2 gap-2">
          <select value={action} onChange={(e) => setAction(e.target.value as any)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}>
            <option value="approve">approve</option>
            <option value="reject">reject</option>
          </select>
          <input type="text" value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="razão"
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
        </div>
        <button
          onClick={() => m.mutate()}
          disabled={m.isPending || !ids.trim()}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          <CheckSquare size={12} />
          {m.isPending ? '…' : `Bulk ${action}`}
        </button>
        {data && (
          <div className="rounded-md border p-3 text-xs flex items-center gap-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
            <ZipToneBadge tone="green" size="sm">{data.ok ?? 0} OK</ZipToneBadge>
            <ZipToneBadge tone="red" size="sm">{data.failed ?? 0} falhou</ZipToneBadge>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// GG. Scheduler placeholder
// ═══════════════════════════════════════════════════════════════════════════

export function SchedulerPanel() {
  return (
    <Panel title="Background scheduler (GG)" subtitle="APScheduler · sem endpoint admin exposto">
      <div className="space-y-2 text-xs">
        <div style={{ color: 'var(--fg-2)' }}>Jobs registados no startup:</div>
        <ul className="space-y-1" style={{ color: 'var(--fg-2)' }}>
          {[
            { id: 'alerts_scan:{tenant_id}', cron: 'every 15 min', desc: 'Scan production alerts' },
            { id: 'daily_feedback', cron: 'daily 00:30 UTC', desc: 'Generate Copilot feedback' },
            { id: 'audit_retention_purge', cron: 'daily 04:30 UTC', desc: 'GDPR audit cleanup' },
          ].map((j) => (
            <li key={j.id} className="flex items-center justify-between rounded-md border px-3 py-2" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <span className="font-mono text-[11px]" style={{ color: 'var(--fg-1)' }}>{j.id}</span>
              <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>{j.cron} · {j.desc}</span>
            </li>
          ))}
        </ul>
        <EmptyState
          title="Trigger manual indisponível"
          hint="Endpoint /v1/admin/scheduler/* ainda não exposto. Jobs apenas legíveis via logs startup."
          size="sm"
        />
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Composição
// ═══════════════════════════════════════════════════════════════════════════

export function OperationsDashboard() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs flex items-center gap-2" style={{ color: 'var(--fg-2)' }}>
          <Activity size={13} />
          Ops · Health · Auth · Bulk · Scheduler · Soft delete · Rate limit
        </span>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Ondas21-27 — AA-GG
        </span>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <HealthPanel />
        <RateLimitPanel />
        <AuthPanel />
        <SoftDeletePanel />
        <BulkOperationsPanel />
        <SchedulerPanel />
      </div>
    </div>
  );
}
