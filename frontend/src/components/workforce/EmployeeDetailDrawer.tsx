/**
 * EmployeeDetailDrawer — Q.18 fix-workforce.
 *
 * Drawer aberto ao clicar num row de /equipa > Lista. Mostra:
 *   - Header: nome + badge nível derivado (1/2/3) + quality score
 *   - Section "Nível explicado" com tabela 1-3 + descrição + barcos recomendados
 *   - Section "Skills per-fase" (polivalência) — phases × {can_do, nivel, last_used}
 *   - Acções: Pedir ao Copilot · Editar · Soft-delete
 *
 * GET /v1/workforce/employees/{id}/level-summary alimenta tudo (1 só request).
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  X,
  Sparkles,
  Pencil,
  Trash2,
  Award,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { ZipToneBadge, EmptyState } from '../dark';
import { workforceEmployeesApi } from '../../lib/api';

interface DrawerProps {
  open: boolean;
  employeeId: string | null;
  employeeName?: string;
  onClose: () => void;
  onEdit?: () => void;
  onError?: (msg: string) => void;
  onSuccess?: (msg: string) => void;
}

type Level = 1 | 2 | 3;

function levelTone(level: Level | undefined): 'green' | 'yellow' | 'red' | 'gray' {
  if (level === 1) return 'green';
  if (level === 2) return 'yellow';
  if (level === 3) return 'red';
  return 'gray';
}

function daysSince(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return Math.floor((Date.now() - d.getTime()) / 86400000);
}

function recencyLabel(days: number | null): string {
  if (days == null) return 'nunca';
  if (days === 0) return 'hoje';
  if (days < 30) return `${days}d`;
  if (days < 365) return `${Math.floor(days / 30)}m`;
  return `${(days / 365).toFixed(1)}a`;
}

const LEVEL_TABLE: Array<{ level: Level; label: string; thresholds: string; tone: 'green' | 'yellow' | 'red' }> = [
  { level: 1, label: 'Top', thresholds: 'score ≥ 8.0', tone: 'green' },
  { level: 2, label: 'Médio', thresholds: 'score 5.0 – 7.9', tone: 'yellow' },
  { level: 3, label: 'Em formação', thresholds: 'score < 5.0', tone: 'red' },
];

export function EmployeeDetailDrawer({
  open,
  employeeId,
  employeeName,
  onClose,
  onEdit,
  onError,
  onSuccess,
}: DrawerProps) {
  const qc = useQueryClient();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const summaryQ = useQuery({
    queryKey: ['employee-level-summary', employeeId],
    queryFn: async () => {
      if (!employeeId) return null;
      return workforceEmployeesApi.levelSummary(employeeId);
    },
    enabled: open && !!employeeId,
    retry: 0,
    staleTime: 60_000,
  });

  const deleteMutation = useMutation({
    mutationFn: () => {
      if (!employeeId) throw new Error('employeeId em falta');
      return workforceEmployeesApi.softDelete(employeeId, {
        reason: 'Soft-delete via /equipa > drawer',
      });
    },
    onSuccess: () => {
      onSuccess?.('Operador desactivado (histórico preservado).');
      qc.invalidateQueries({ queryKey: ['equipa', 'employees'] });
      qc.invalidateQueries({ queryKey: ['employees'] });
      setConfirmDelete(false);
      onClose();
    },
    onError: (err: Error & { message?: string }) => onError?.(err?.message ?? 'Erro ao desactivar.'),
  });

  if (!open) return null;

  const summary = summaryQ.data;
  const phases = summary?.per_phase_skills ?? [];

  function pedirAoCopilot() {
    if (!summary || !employeeId) return;
    const query = `Que barcos posso atribuir ao operador ${employeeName ?? employeeId}? (nível derivado: ${summary.derived_level} — ${summary.level_label})`;
    window.dispatchEvent(
      new CustomEvent('copilot:open', {
        detail: {
          query,
          entity_type: 'employee',
          entity_id: employeeId,
        },
      }),
    );
  }

  return (
    <>
      <div
        className="fixed inset-0 z-40 backdrop-blur-sm"
        style={{ background: 'rgba(0,0,0,0.5)' }}
        onClick={onClose}
      />
      <aside
        className="fixed right-0 top-0 z-50 h-full w-full max-w-2xl border-l overflow-y-auto"
        style={{ background: 'var(--bg-1)', borderColor: 'var(--bd-1)' }}
      >
        <header
          className="sticky top-0 px-5 py-4 border-b flex items-center justify-between"
          style={{ background: 'var(--bg-1)', borderColor: 'var(--bd-1)' }}
        >
          <div className="flex items-center gap-3 min-w-0">
            <Award size={18} style={{ color: 'var(--fg-3)' }} />
            <div className="min-w-0">
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                Operador
              </div>
              <div className="text-sm font-semibold truncate" style={{ color: 'var(--fg-1)' }}>
                {employeeName ?? employeeId ?? '—'}
              </div>
            </div>
            {summary && (
              <ZipToneBadge tone={levelTone(summary.derived_level)} size="sm">
                Nível {summary.derived_level} · {summary.level_label}
              </ZipToneBadge>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-white/5"
            aria-label="Fechar"
          >
            <X size={16} style={{ color: 'var(--fg-2)' }} />
          </button>
        </header>

        <div className="p-5 space-y-4">
          {/* Acções */}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={pedirAoCopilot}
              disabled={!summary}
              className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium"
              style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
            >
              <Sparkles size={12} />
              Pedir ao Copilot
            </button>
            <button
              type="button"
              onClick={() => onEdit?.()}
              className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium"
              style={{ background: 'var(--bg-2)', color: 'var(--fg-1)', border: '1px solid var(--bd-1)' }}
            >
              <Pencil size={12} />
              Editar
            </button>
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium ml-auto"
              style={{ background: 'var(--red-bg)', color: 'var(--red)' }}
            >
              <Trash2 size={12} />
              Desactivar
            </button>
          </div>

          {confirmDelete && (
            <div
              className="rounded-md border p-3 text-xs space-y-2"
              style={{ borderColor: 'var(--red)', background: 'var(--red-bg)' }}
            >
              <div style={{ color: 'var(--red)' }}>
                Confirmar soft-delete? Histórico fica preservado, status passa a TERMINATED.
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate()}
                  disabled={deleteMutation.isPending}
                  className="rounded px-2 py-1 text-xs font-medium"
                  style={{ background: 'var(--red)', color: 'white' }}
                >
                  {deleteMutation.isPending ? '…' : 'Sim, desactivar'}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDelete(false)}
                  className="rounded px-2 py-1 text-xs"
                  style={{ background: 'var(--bg-2)', color: 'var(--fg-1)' }}
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

          {/* KPIs */}
          {summaryQ.isLoading && (
            <div className="px-2 py-6 text-xs text-center" style={{ color: 'var(--fg-3)' }}>
              A carregar nível…
            </div>
          )}

          {summary && (
            <>
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                  <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                    Quality score
                  </div>
                  <div className="text-2xl font-semibold tabular-nums mt-1" style={{ color: 'var(--fg-1)' }}>
                    {summary.quality_score.toFixed(1)}
                    <span className="text-xs ml-1" style={{ color: 'var(--fg-3)' }}>/10</span>
                  </div>
                </div>
                <div className="rounded-md border p-3" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                  <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>
                    Nível derivado
                  </div>
                  <div
                    className="text-2xl font-semibold tabular-nums mt-1"
                    style={{ color: `var(--${levelTone(summary.derived_level)})` }}
                  >
                    {summary.derived_level}
                    <span className="text-xs ml-2" style={{ color: 'var(--fg-2)' }}>{summary.level_label}</span>
                  </div>
                </div>
              </div>

              {/* Nível explicado */}
              <details
                open
                className="rounded-md border"
                style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}
              >
                <summary
                  className="cursor-pointer px-3 py-2 text-xs font-semibold"
                  style={{ color: 'var(--fg-1)' }}
                >
                  Nível explicado (1=melhor, 3=pior)
                </summary>
                <div className="px-3 pb-3 space-y-3">
                  <div className="text-[11px]" style={{ color: 'var(--fg-2)' }}>
                    {summary.level_description}
                  </div>
                  <div className="overflow-x-auto rounded border" style={{ borderColor: 'var(--bd-1)' }}>
                    <table className="w-full text-[11px]">
                      <thead style={{ color: 'var(--fg-3)' }}>
                        <tr className="text-left">
                          <th className="px-2 py-1.5">Nível</th>
                          <th className="px-2 py-1.5">Etiqueta</th>
                          <th className="px-2 py-1.5">Score Laplace</th>
                        </tr>
                      </thead>
                      <tbody>
                        {LEVEL_TABLE.map((r) => (
                          <tr
                            key={r.level}
                            className="border-t"
                            style={{
                              borderColor: 'var(--bd-1)',
                              background:
                                r.level === summary.derived_level ? 'var(--bg-3)' : 'transparent',
                            }}
                          >
                            <td className="px-2 py-1.5">
                              <ZipToneBadge tone={r.tone} size="sm">
                                {r.level}
                              </ZipToneBadge>
                            </td>
                            <td className="px-2 py-1.5" style={{ color: 'var(--fg-1)' }}>{r.label}</td>
                            <td className="px-2 py-1.5 font-mono" style={{ color: 'var(--fg-3)' }}>{r.thresholds}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wider mb-1" style={{ color: 'var(--fg-3)' }}>
                      Barcos recomendados (nível {summary.derived_level})
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {summary.recommended_boats.map((b) => (
                        <ZipToneBadge key={b} tone={levelTone(summary.derived_level)} size="sm">
                          {b}
                        </ZipToneBadge>
                      ))}
                    </div>
                  </div>
                </div>
              </details>

              {/* Skills per-fase (polivalência) */}
              <div className="rounded-md border" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                <div
                  className="px-3 py-2 text-xs font-semibold border-b flex items-center justify-between"
                  style={{ color: 'var(--fg-1)', borderColor: 'var(--bd-1)' }}
                >
                  <span>Polivalência (skill matrix per-fase)</span>
                  <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
                    {phases.filter((p) => p.can_do).length}/{phases.length} fases aptas
                  </span>
                </div>
                {phases.length === 0 ? (
                  <EmptyState title="Sem skill matrix" hint="ERP ainda não populou skills curados." size="sm" />
                ) : (
                  <div className="overflow-x-auto max-h-72">
                    <table className="w-full text-[11px]">
                      <thead style={{ color: 'var(--fg-3)' }}>
                        <tr className="text-left">
                          <th className="px-3 py-1.5">Fase</th>
                          <th className="px-3 py-1.5 text-center">Apto</th>
                          <th className="px-3 py-1.5 text-center">Nível curado</th>
                          <th className="px-3 py-1.5 text-right">Ops</th>
                          <th className="px-3 py-1.5 text-right">Última</th>
                        </tr>
                      </thead>
                      <tbody>
                        {phases.map((p) => {
                          const d = daysSince(p.last_used_at);
                          return (
                            <tr key={p.phase_id} className="border-t" style={{ borderColor: 'var(--bd-1)' }}>
                              <td className="px-3 py-1.5" style={{ color: 'var(--fg-1)' }}>
                                {p.phase_name ?? p.phase_id}
                              </td>
                              <td className="px-3 py-1.5 text-center">
                                {p.can_do ? (
                                  <CheckCircle2 size={12} style={{ color: 'var(--green)', display: 'inline' }} />
                                ) : (
                                  <AlertCircle size={12} style={{ color: 'var(--fg-3)', display: 'inline' }} />
                                )}
                              </td>
                              <td className="px-3 py-1.5 text-center tabular-nums" style={{ color: 'var(--fg-2)' }}>
                                {p.nivel ?? '—'}
                              </td>
                              <td className="px-3 py-1.5 text-right tabular-nums" style={{ color: 'var(--fg-2)' }}>
                                {p.ops_count}
                              </td>
                              <td className="px-3 py-1.5 text-right tabular-nums" style={{ color: 'var(--fg-3)' }}>
                                {recencyLabel(d)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
