/**
 * HealthDashboardPage — Sprint Q.7 Fase 1
 * ========================================
 *
 * Single-screen view of "is the factory safe to operate right now?".
 * Consumes /v1/diagnostics/full and renders 4 panels:
 *
 *   1. Per-module health rollup (17 módulos × {green/yellow/red})
 *   2. Infrastructure pings (PostgreSQL, Redis, Kafka, Ollama)
 *   3. Trust Index v2 composite + 5 gates (live)
 *   4. ScheduleCommit cadence (commits últimos 7 dias)
 *
 * Polling: refetch a cada 30s. Mostra import_errors textuais quando um
 * módulo está vermelho.
 */

import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  AlertCircle,
  Ban,
  CheckCircle2,
  Database,
  GitCommit,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkBadge, DarkButton, DarkCard } from '../../components/dark';
import {
  diagnosticsApi,
  type DiagnosticsModule,
  type ModuleHealthStatus,
} from '../../lib/api';

// ───────────────────────────────────────────────────────────────────────────
// Helpers
// ───────────────────────────────────────────────────────────────────────────

const HEALTH_COLOR: Record<ModuleHealthStatus, string> = {
  green: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300',
  yellow: 'bg-amber-500/15 border-amber-500/40 text-amber-300',
  red: 'bg-red-500/15 border-red-500/40 text-red-300',
};

const HEALTH_LABEL: Record<ModuleHealthStatus, string> = {
  green: 'OK',
  yellow: 'sem testes',
  red: 'IMPORTS A FALHAR',
};

function ModuleTile({ m }: { m: DiagnosticsModule }) {
  return (
    <div
      className={`rounded-lg border p-3 transition ${HEALTH_COLOR[m.health]}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-white truncate" title={m.module}>
          {m.module}
        </span>
        <DarkBadge
          variant={
            m.health === 'green' ? 'success' : m.health === 'yellow' ? 'warning' : 'danger'
          }
          size="sm"
        >
          {HEALTH_LABEL[m.health]}
        </DarkBadge>
      </div>
      <div className="grid grid-cols-2 gap-1 text-xs text-slate-300">
        <span>src: <strong className="text-white">{m.src_files}</strong></span>
        <span>tests: <strong className="text-white">{m.test_files}</strong></span>
        <span>rotas: <strong className="text-white">{m.routes}</strong></span>
        <span>TODOs: <strong className="text-white">{m.todo_count}</strong></span>
      </div>
      {m.import_errors.length > 0 && (
        <ul className="mt-2 space-y-0.5">
          {m.import_errors.slice(0, 3).map((e) => (
            <li key={e} className="text-xs text-red-300 truncate" title={e}>
              {e}
            </li>
          ))}
          {m.import_errors.length > 3 && (
            <li className="text-xs text-red-400/70">
              +{m.import_errors.length - 3} mais
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────
// Page
// ───────────────────────────────────────────────────────────────────────────

export function HealthDashboardPage() {
  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['diagnostics', 'full'],
    queryFn: () => diagnosticsApi.full(),
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  return (
    <DarkPageLayout
      title="Health Dashboard"
      subtitle="Audit em tempo real · Sprint Q.7 Fase 1"
      icon={<Activity size={20} />}
      actions={
        <DarkButton
          variant="secondary"
          icon={
            isFetching ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <RefreshCw size={14} />
            )
          }
          onClick={() => refetch()}
        >
          Refresh
        </DarkButton>
      }
    >
      {isLoading && (
        <DarkCard className="text-center py-10 text-slate-400">
          <Loader2 size={28} className="mx-auto mb-2 text-teal-400 animate-spin" />
          A coletar diagnósticos…
        </DarkCard>
      )}

      {error && (
        <DarkCard className="border-red-500/30 bg-red-500/10">
          <div className="flex items-center gap-3 text-red-400">
            <AlertCircle size={20} />
            <div>
              <p className="font-medium">Falha ao carregar /v1/diagnostics/full</p>
              <p className="text-sm text-red-400/80">{(error as Error).message}</p>
            </div>
          </div>
        </DarkCard>
      )}

      {data && (
        <div className="space-y-6">
          {/* Top stats — 4 quick numbers */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <SummaryTile
              label="Módulos OK"
              value={`${data.modules_summary.green} / ${data.modules_summary.total}`}
              tone={data.modules_summary.red > 0 ? 'danger' : 'success'}
              icon={<CheckCircle2 size={16} />}
            />
            <SummaryTile
              label="Módulos com problemas"
              value={`${data.modules_summary.yellow + data.modules_summary.red}`}
              tone={data.modules_summary.red > 0 ? 'danger' : 'warning'}
              icon={<AlertCircle size={16} />}
            />
            <SummaryTile
              label="Infraestrutura UP"
              value={`${data.infrastructure.summary.healthy} / ${data.infrastructure.summary.total}`}
              tone={data.infrastructure.summary.unhealthy > 0 ? 'danger' : 'success'}
              icon={<Database size={16} />}
            />
            <SummaryTile
              label="Trust Index"
              value={
                typeof data.trust_index.composite === 'number'
                  ? `${(data.trust_index.composite * 100).toFixed(0)}%`
                  : '—'
              }
              tone={
                typeof data.trust_index.composite !== 'number'
                  ? 'neutral'
                  : data.trust_index.composite >= 0.75
                  ? 'success'
                  : data.trust_index.composite >= 0.5
                  ? 'warning'
                  : 'danger'
              }
              icon={<ShieldCheck size={16} />}
            />
          </div>

          {/* 17-module grid */}
          <DarkCard>
            <h2 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
              <Activity size={16} className="text-teal-400" />
              17 Módulos
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
              {data.modules.map((m) => (
                <ModuleTile key={m.module} m={m} />
              ))}
            </div>
          </DarkCard>

          {/* Infrastructure */}
          <DarkCard>
            <h2 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
              <Database size={16} className="text-teal-400" />
              Infraestrutura
            </h2>
            <div className="space-y-2">
              {data.infrastructure.items.map((c) => (
                <div
                  key={c.component}
                  className="flex items-center justify-between p-2 bg-slate-800/40 rounded"
                >
                  <div className="flex items-center gap-2">
                    {c.healthy ? (
                      <CheckCircle2 size={14} className="text-emerald-400" />
                    ) : (
                      <Ban size={14} className="text-red-400" />
                    )}
                    <span className="text-sm text-white capitalize">{c.component}</span>
                  </div>
                  <div className="flex items-center gap-3 text-xs">
                    {c.latency_ms != null && (
                      <span className="text-slate-500">{c.latency_ms.toFixed(0)}ms</span>
                    )}
                    <span
                      className={c.healthy ? 'text-emerald-300' : 'text-red-300'}
                      title={c.detail}
                    >
                      {c.detail.length > 50 ? c.detail.slice(0, 50) + '…' : c.detail}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </DarkCard>

          {/* Trust Index gates */}
          {data.trust_index.effective_gates && (
            <DarkCard>
              <h2 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
                <ShieldCheck size={16} className="text-teal-400" />
                Trust Index v2 — Effective Gates
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                {Object.entries(data.trust_index.effective_gates).map(([gate, allowed]) => (
                  <div
                    key={gate}
                    className={`p-2 rounded border text-xs ${
                      allowed
                        ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                        : 'bg-red-500/10 border-red-500/40 text-red-300'
                    }`}
                  >
                    <div className="font-medium">{gate}</div>
                    <div className="text-[10px] opacity-80">
                      {allowed ? 'OPEN' : 'BLOCKED'}
                    </div>
                  </div>
                ))}
              </div>
            </DarkCard>
          )}

          {/* Commit cadence */}
          <DarkCard>
            <h2 className="text-base font-semibold text-white mb-3 flex items-center gap-2">
              <GitCommit size={16} className="text-teal-400" />
              ScheduleCommit (últimos 7 dias)
            </h2>
            {'error' in data.commits && data.commits.error ? (
              <p className="text-sm text-red-300">
                Erro: {data.commits.error}
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div>
                  <p className="text-xs text-slate-400">Commits 7d</p>
                  <p className="text-2xl font-bold text-white">
                    {data.commits.commits_last_7_days ?? 0}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-400">Último SHA</p>
                  <p className="text-sm font-mono text-white">
                    {data.commits.latest_commit_sha ?? '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-400">Último commit</p>
                  <p className="text-sm text-white">
                    {data.commits.latest_commit_at
                      ? new Date(data.commits.latest_commit_at).toLocaleString('pt-PT')
                      : '—'}
                  </p>
                </div>
              </div>
            )}
          </DarkCard>

          <p className="text-xs text-slate-500 text-center">
            Auto-refresh 30s. Para audit estático profundo correr{' '}
            <code>python scripts/audit.py</code> e ver{' '}
            <code>scripts/AUDIT_BASELINE.md</code>.
          </p>
        </div>
      )}
    </DarkPageLayout>
  );
}

function SummaryTile({
  label,
  value,
  tone,
  icon,
}: {
  label: string;
  value: string;
  tone: 'success' | 'warning' | 'danger' | 'neutral';
  icon: React.ReactNode;
}) {
  const bg = {
    success: 'bg-emerald-500/10 border-emerald-500/30',
    warning: 'bg-amber-500/10 border-amber-500/30',
    danger: 'bg-red-500/10 border-red-500/30',
    neutral: 'bg-slate-800/40 border-slate-700/40',
  }[tone];
  return (
    <div className={`rounded-xl border ${bg} p-4`}>
      <div className="flex items-center gap-2 text-xs text-slate-300 mb-2">
        {icon}
        <span>{label}</span>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  );
}

export default HealthDashboardPage;
