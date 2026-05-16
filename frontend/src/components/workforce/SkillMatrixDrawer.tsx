/**
 * SkillMatrixDrawer + SkillRecencyPanel — Onda 7 (G).
 *
 * - SkillMatrixDrawer: drawer per-employee → fetch /skill-matrix → matriz
 *   phases × {can_do, nivel, ops_count, last_used_at} com filtro 12 meses
 *   ("expirado" se last_used_at > 365 dias).
 * - SkillRecencyPanel: tabela operadores ordenada por skill mais recentemente
 *   usada (recency global da equipa).
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, Clock, CheckCircle2, AlertCircle, History } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';
import { getApiBase } from '../../lib/api';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const BASE = getApiBase();

interface SkillRow {
  phase_id: string;
  phase_name?: string;
  can_do: boolean;
  nivel?: number | null;
  ops_count: number;
  last_used_at?: string | null;
}

function daysSince(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / 86400000);
}

function recencyTone(days: number | null): 'green' | 'yellow' | 'red' | 'gray' {
  if (days == null) return 'gray';
  if (days <= 90) return 'green';
  if (days <= 365) return 'yellow';
  return 'red';
}

function recencyLabel(days: number | null): string {
  if (days == null) return 'nunca';
  if (days === 0) return 'hoje';
  if (days < 30) return `${days}d`;
  if (days < 365) return `${Math.floor(days / 30)}m`;
  return `${(days / 365).toFixed(1)}a`;
}

// ═══════════════════════════════════════════════════════════════════════════
// SkillMatrixDrawer
// ═══════════════════════════════════════════════════════════════════════════

interface DrawerProps {
  open: boolean;
  employeeId: string | null;
  employeeName?: string;
  onClose: () => void;
}

export function SkillMatrixDrawer({ open, employeeId, employeeName, onClose }: DrawerProps) {
  const [filter12m, setFilter12m] = useState(false);

  const q = useQuery({
    queryKey: ['skill-matrix', employeeId],
    queryFn: async () => {
      if (!employeeId) return null;
      const r = await fetch(`${BASE}/v1/workforce/employees/${employeeId}/skill-matrix`, { headers: TENANT });
      if (!r.ok) return null;
      return r.json();
    },
    enabled: open && !!employeeId,
    retry: 0,
  });

  if (!open) return null;

  const data = q.data as { phases?: SkillRow[]; total?: number } | undefined | null;
  const allPhases = (data?.phases ?? []) as SkillRow[];
  const phases = filter12m
    ? allPhases.filter((p) => {
        const d = daysSince(p.last_used_at);
        return d == null || d <= 365;
      })
    : allPhases;

  const expiredCount = allPhases.filter((p) => {
    const d = daysSince(p.last_used_at);
    return d != null && d > 365;
  }).length;

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
        <header className="sticky top-0 px-4 py-3 border-b flex items-center justify-between" style={{ background: 'var(--bg-1)', borderColor: 'var(--bd-1)' }}>
          <div>
            <div className="text-xs uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
              Skill matrix history
            </div>
            <div className="text-sm font-semibold" style={{ color: 'var(--fg-1)' }}>
              {employeeName ?? employeeId ?? '—'}
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-white/5" aria-label="Fechar">
            <X size={16} style={{ color: 'var(--fg-2)' }} />
          </button>
        </header>

        <div className="p-4 space-y-3">
          <label className="flex items-center gap-2 text-xs cursor-pointer" style={{ color: 'var(--fg-2)' }}>
            <input
              type="checkbox"
              checked={filter12m}
              onChange={(e) => setFilter12m(e.target.checked)}
              className="rounded"
            />
            <Clock size={12} />
            Apenas com actividade ≤ 12 meses
            {expiredCount > 0 && (
              <ZipToneBadge tone="red" size="sm">
                {expiredCount} expirados
              </ZipToneBadge>
            )}
          </label>

          {q.isLoading ? (
            <div className="px-2 py-6 text-xs text-center" style={{ color: 'var(--fg-3)' }}>
              A carregar matriz…
            </div>
          ) : phases.length === 0 ? (
            <EmptyState title="Sem skills no filtro" hint={filter12m ? 'Desactiva o filtro 12m para ver todas.' : undefined} size="sm" />
          ) : (
            <div className="overflow-x-auto rounded-md border" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
              <table className="w-full text-xs">
                <thead style={{ color: 'var(--fg-3)' }}>
                  <tr className="text-left">
                    <th className="px-3 py-2">Fase</th>
                    <th className="px-3 py-2 text-center">Apto</th>
                    <th className="px-3 py-2 text-center">Nível</th>
                    <th className="px-3 py-2 text-right">Ops</th>
                    <th className="px-3 py-2 text-right">Última</th>
                  </tr>
                </thead>
                <tbody>
                  {phases.map((p) => {
                    const d = daysSince(p.last_used_at);
                    return (
                      <tr key={p.phase_id} className="border-t" style={{ borderColor: 'var(--bd-1)' }}>
                        <td className="px-3 py-2" style={{ color: 'var(--fg-1)' }}>
                          {p.phase_name ?? p.phase_id}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {p.can_do ? (
                            <CheckCircle2 size={14} style={{ color: 'var(--green)', display: 'inline' }} />
                          ) : (
                            <AlertCircle size={14} style={{ color: 'var(--fg-3)', display: 'inline' }} />
                          )}
                        </td>
                        <td className="px-3 py-2 text-center tabular-nums" style={{ color: 'var(--fg-2)' }}>
                          {p.nivel ?? '—'}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums" style={{ color: 'var(--fg-2)' }}>
                          {p.ops_count}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <ZipToneBadge tone={recencyTone(d)} size="sm">
                            {recencyLabel(d)}
                          </ZipToneBadge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// SkillRecencyPanel — operadores ordenados por última actividade global
// ═══════════════════════════════════════════════════════════════════════════

interface EmployeeRow {
  employee_id?: string;
  id?: string;
  name?: string;
  job_title?: string;
}

interface OnSelectFn {
  (employeeId: string, name?: string): void;
}

export function SkillRecencyPanel({ onSelect }: { onSelect?: OnSelectFn }) {
  const empQ = useQuery({
    queryKey: ['workforce-employees'],
    queryFn: async () => {
      const r = await fetch(`${BASE}/v1/workforce/employees?limit=200`, { headers: TENANT });
      if (!r.ok) return { items: [] as EmployeeRow[] };
      return r.json();
    },
    staleTime: 60_000,
    retry: 0,
  });

  const employees = ((empQ.data as { items?: EmployeeRow[] } | undefined)?.items ?? []) as EmployeeRow[];

  return (
    <Panel title="Skill recency — equipa" subtitle="Clica um operador → ver matriz completa + filtro 12m" badge={employees.length || '—'}>
      {empQ.isLoading ? (
        <div className="px-2 py-6 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
      ) : employees.length === 0 ? (
        <EmptyState title="Sem operadores activos" size="sm" />
      ) : (
        <div className="space-y-1">
          {employees.slice(0, 50).map((e) => {
            const id = e.employee_id ?? e.id ?? '';
            return (
              <button
                key={id}
                onClick={() => onSelect?.(id, e.name)}
                className="w-full flex items-center justify-between px-3 py-2 rounded-md text-xs text-left hover:opacity-90 transition-opacity"
                style={{ background: 'var(--bg-2)', color: 'var(--fg-1)', border: '1px solid var(--bd-1)' }}
              >
                <span>{e.name ?? id}</span>
                <span className="flex items-center gap-2" style={{ color: 'var(--fg-3)' }}>
                  <span>{e.job_title ?? '—'}</span>
                  <History size={12} />
                </span>
              </button>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// SkillsDashboard — composição
// ═══════════════════════════════════════════════════════════════════════════

export function SkillsDashboard() {
  const [drawerEmpId, setDrawerEmpId] = useState<string | null>(null);
  const [drawerEmpName, setDrawerEmpName] = useState<string | undefined>();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs" style={{ color: 'var(--fg-2)' }}>
          Skill matrix history — recency 12m + drawer per-operador
        </span>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda7 — G. Workforce
        </span>
      </div>
      <SkillRecencyPanel
        onSelect={(id, name) => {
          setDrawerEmpId(id);
          setDrawerEmpName(name);
        }}
      />
      <SkillMatrixDrawer
        open={!!drawerEmpId}
        employeeId={drawerEmpId}
        employeeName={drawerEmpName}
        onClose={() => setDrawerEmpId(null)}
      />
    </div>
  );
}
