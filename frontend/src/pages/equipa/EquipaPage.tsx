/**
 * EquipaPage — port literal de design/nelo-zip/src/page-workforce.jsx
 * (tab Lista) + page-dispatch.jsx (tab Alocações).
 *
 * Tabs:
 *   • Lista         — page-workforce.jsx port literal: explainer + 4 KPI
 *                     strip + tabela 8 cols (Avatar+name/Tier/Score/Err%/
 *                     Ops/Skill/Estado/Chevron). Wire ao /v1/core/employees.
 *   • Alocações     — page-dispatch.jsx port literal: explainer + 2-col
 *                     (Operadores 320px / Atribuições 1fr com WorkerRow +
 *                     DispatchRow + drag-drop visual). Wire a employees +
 *                     orders/active.
 *   • Produtividade — wrap ProductivityPage existing.
 *   • Risco         — WorkforceDashboard composto (consome /v1/workforce/
 *                     risks/spof + /dependency-graph + /cascade-impact).
 *   • Simulador     — WorkforceDashboard composto.
 *   • Formação      — WorkforceDashboard composto (training-recommendations).
 *
 * ZERO MOCKS. Empty states honestos.
 *
 * Sprint Q.18.ZIP.EQ (refactor profundo big-bang).
 */

import { lazy, Suspense, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Users,
  CalendarRange,
  TrendingUp,
  AlertTriangle,
  FlaskConical,
  GraduationCap,
  RefreshCw,
  Sparkles,
  Plus,
  ChevronRight,
  GripVertical,
  Info,
  Printer,
} from 'lucide-react';
import {
  PageHeader,
  Tabs,
  Panel,
  ZipToneBadge,
  ZipStatusBadge,
  type ZipBoatStatus,
} from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';

const ProductivityPage = lazy(() =>
  import('../hr/ProductivityPage').then((m) => ({ default: m.ProductivityPage })),
);
const WorkforceDashboard = lazy(() =>
  import('../workforce/WorkforceDashboard').then((m) => ({
    default: m.WorkforceDashboard,
  })),
);

// ─── Types ──────────────────────────────────────────────────────────────────

interface Employee {
  id: string;
  employee_code: string;
  employee_name: string;
  status: string;
  hire_date: string | null;
  job_title: string | null;
  department: string | null;
}

interface ActiveOrder {
  id: string;
  hull: string | null;
  product_name: string;
  product_type: string;
  phase: string | null;
  status: string;
  transport_date: string | null;
}

// Mapping cliente_code → flag (matching data.jsx CLIENTS)
const CLIENT_FLAGS: Record<string, string> = {
  FR: '🇫🇷',
  DE: '🇩🇪',
  PT: '🇵🇹',
  IT: '🇮🇹',
  SE: '🇸🇪',
  NO: '🇳🇴',
  AT: '🇦🇹',
};

// Hull → cliente map (data.jsx BOATS)
const HULL_CLIENT: Record<number, string> = {
  4271: 'FR',
  4272: 'PT',
  4273: 'FR',
  4274: 'PT',
  4275: 'PT',
  5103: 'DE',
  5104: 'IT',
  5105: 'DE',
  6001: 'PT',
  6002: 'PT',
  6003: 'NO',
  6004: 'SE',
};

// ─── Endpoints ──────────────────────────────────────────────────────────────

async function fetchEmployees(): Promise<Employee[]> {
  const resp = await fetch(
    'http://127.0.0.1:8001/v1/core/employees?limit=200',
    { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
  );
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

async function fetchEmployeeQualityScore(id: string): Promise<{ score: number; defect_rate: number; operations: number } | null> {
  try {
    const resp = await fetch(
      `http://127.0.0.1:8001/v1/workforce/employees/${id}/quality-score`,
      { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
    );
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

async function fetchActiveOrders(): Promise<ActiveOrder[]> {
  const resp = await fetch(
    'http://127.0.0.1:8001/v1/plan/orders/active?limit=500',
    { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } },
  );
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function tierFromHire(hire_date: string | null): '>12m' | '<12m' | '<5m' {
  if (!hire_date) return '<5m';
  const months = (Date.now() - new Date(hire_date).getTime()) / (1000 * 60 * 60 * 24 * 30);
  if (months >= 12) return '>12m';
  if (months >= 5) return '<12m';
  return '<5m';
}

function tierTone(tier: string): 'green' | 'blue' | 'yellow' {
  return tier === '>12m' ? 'green' : tier === '<12m' ? 'blue' : 'yellow';
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function deriveBoatStatus(transport_date: string | null, phase: string | null): ZipBoatStatus {
  if (phase === 'Cura') return 'curing';
  if (!transport_date) return 'on_time';
  const dx = Math.round((new Date(transport_date).getTime() - new Date().setHours(0, 0, 0, 0)) / (1000 * 60 * 60 * 24));
  if (dx < 0) return 'late';
  if (dx <= 2) return 'at_risk';
  return 'on_time';
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════

const TAB_IDS = ['lista', 'alocacoes', 'produtividade', 'risco', 'simulador', 'formacao'] as const;
type TabId = (typeof TAB_IDS)[number];
function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

export default function EquipaPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'lista';

  const tabs = useMemo(
    () => [
      { id: 'lista', label: 'Lista', icon: <Users size={13} /> },
      { id: 'alocacoes', label: 'Alocações', icon: <CalendarRange size={13} /> },
      { id: 'produtividade', label: 'Produtividade', icon: <TrendingUp size={13} /> },
      { id: 'risco', label: 'Risco', icon: <AlertTriangle size={13} /> },
      { id: 'simulador', label: 'Simulador', icon: <FlaskConical size={13} /> },
      { id: 'formacao', label: 'Formação', icon: <GraduationCap size={13} /> },
    ],
    [],
  );

  const handleTabChange = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', id);
    setSearchParams(next, { replace: true });
  };

  const fallback = (
    <div className="p-8">
      <SkeletonLoader count={5} />
    </div>
  );

  const titleByTab = (tab: TabId) =>
    tab === 'lista'
      ? 'Operadores'
      : tab === 'alocacoes'
        ? 'Atribuição diária'
        : tab === 'produtividade'
          ? 'Produtividade'
          : tab === 'risco'
            ? 'Risco · SPOFs'
            : tab === 'simulador'
              ? 'Simulador de ausência'
              : 'Formação · sugestões';

  const subtitleByTab = (tab: TabId, count: number) =>
    tab === 'lista'
      ? `Score, skills e taxa de erro · ${count} operadores activos`
      : tab === 'alocacoes'
        ? `Quem faz o quê hoje · ${count} operadores · barcos activos`
        : '';

  // Para o subtitle dinâmico precisamos de count
  const employeesCountQuery = useQuery({
    queryKey: ['equipa', 'employees-count'],
    queryFn: async () => {
      const r = await fetchEmployees();
      return r.length;
    },
    staleTime: 60_000,
    retry: 0,
  });
  const empCount = employeesCountQuery.data ?? 0;

  return (
    <div>
      <PageHeader
        title={titleByTab(activeTab)}
        subtitle={subtitleByTab(activeTab, empCount)}
        actions={
          <>
            {activeTab === 'lista' ? (
              <button
                type="button"
                disabled
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-tertiary border border-white/[0.08] text-xs font-medium opacity-50 cursor-not-allowed"
              >
                <Plus size={13} />
                Adicionar operador
              </button>
            ) : null}
            {activeTab === 'alocacoes' ? (
              <>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
                  onClick={() => window.print()}
                >
                  <Printer size={13} />
                  Imprimir folha
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-white text-xs font-medium transition-colors"
                  style={{ background: 'var(--blue)', border: '1px solid var(--blue)' }}
                  onClick={() => alert('Sugerir atribuição — wire ao CPO em sub-sprint')}
                >
                  <Sparkles size={13} />
                  Sugerir atribuição
                </button>
              </>
            ) : null}
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
            >
              <RefreshCw size={13} />
              Atualizar
            </button>
          </>
        }
      />

      <div className="px-6 pt-2">
        <Tabs tabs={tabs} value={activeTab} onChange={handleTabChange} />
      </div>

      <div className="px-6 py-4">
        {activeTab === 'lista' && <ListaTab />}
        {activeTab === 'alocacoes' && <AlocacoesTab />}
        {activeTab === 'produtividade' && (
          <Suspense fallback={fallback}>
            <ProductivityPage />
          </Suspense>
        )}
        {activeTab === 'risco' && (
          <>
            <FocusBanner focus="risco" />
            <Suspense fallback={fallback}>
              <WorkforceDashboard />
            </Suspense>
          </>
        )}
        {activeTab === 'simulador' && (
          <>
            <FocusBanner focus="simulador" />
            <Suspense fallback={fallback}>
              <WorkforceDashboard />
            </Suspense>
          </>
        )}
        {activeTab === 'formacao' && (
          <>
            <FocusBanner focus="formacao" />
            <Suspense fallback={fallback}>
              <WorkforceDashboard />
            </Suspense>
          </>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ListaTab — port literal page-workforce.jsx
// ═══════════════════════════════════════════════════════════════════════════

interface EmployeeWithStats extends Employee {
  tier: '>12m' | '<12m' | '<5m';
  score: number | null;
  err: number | null;
  ops: number | null;
}

function ListaTab() {
  const employeesQuery = useQuery({
    queryKey: ['equipa', 'employees'],
    queryFn: fetchEmployees,
    staleTime: 60_000,
    retry: 0,
  });

  const employees = employeesQuery.data ?? [];

  // Quality scores em paralelo (Promise.all dentro de useQuery)
  const statsQuery = useQuery({
    queryKey: ['equipa', 'employees-quality-scores', employees.map((e) => e.id).join(',')],
    queryFn: async () => {
      if (employees.length === 0) return new Map<string, any>();
      const results = await Promise.all(
        employees.map(async (e) => {
          const stats = await fetchEmployeeQualityScore(e.id);
          return [e.id, stats] as const;
        }),
      );
      return new Map(results);
    },
    enabled: employees.length > 0,
    staleTime: 60_000,
    retry: 0,
  });

  const enriched: EmployeeWithStats[] = useMemo(() => {
    const statsMap = statsQuery.data ?? new Map();
    return employees.map((e) => {
      const stats: any = statsMap.get(e.id);
      return {
        ...e,
        tier: tierFromHire(e.hire_date),
        score: stats?.score ?? null,
        err: stats?.defect_rate ?? null,
        ops: stats?.operations ?? null,
      };
    });
  }, [employees, statsQuery.data]);

  // KPI strip
  const totalActive = enriched.filter((e) => e.status === 'ACTIVE').length;
  const totalEmployees = enriched.length;
  const validScores = enriched.filter((e) => e.score !== null);
  const avgScore =
    validScores.length > 0
      ? validScores.reduce((sum, e) => sum + (e.score ?? 0), 0) / validScores.length
      : null;
  const validErrs = enriched.filter((e) => e.err !== null);
  const avgErr =
    validErrs.length > 0
      ? validErrs.reduce((sum, e) => sum + (e.err ?? 0), 0) / validErrs.length
      : null;
  // Cobertura crítica: skills com só 1 operador tier >12m
  const skillCount: Record<string, number> = {};
  for (const e of enriched) {
    if (e.tier === '>12m' && e.job_title) {
      skillCount[e.job_title] = (skillCount[e.job_title] ?? 0) + 1;
    }
  }
  const criticalSkills = Object.values(skillCount).filter((c) => c <= 1).length;

  return (
    <div className="space-y-5">
      {/* Explainer */}
      <div
        style={{
          padding: '14px 18px',
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 12,
          fontSize: 13,
          color: 'var(--fg-1)',
          lineHeight: 1.6,
        }}
      >
        <strong style={{ color: 'var(--fg-0)' }}>
          Como o sistema mede operadores:
        </strong>{' '}
        O score 0–10 vem do histórico — taxa de erro, qualidade, tempo médio.{' '}
        <strong>Não é uma avaliação humana</strong>, é o que ajuda o sistema a
        sugerir a melhor pessoa para cada barco. Operadores podem sempre ver e
        corrigir o seu próprio perfil.
      </div>

      {/* KPI strip */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 14,
        }}
      >
        <KPIStrip
          label="Operadores hoje"
          value={`${totalActive}/${totalEmployees}`}
          context={
            totalActive === totalEmployees
              ? 'Todos disponíveis'
              : `${totalEmployees - totalActive} ausente${totalEmployees - totalActive !== 1 ? 's' : ''}`
          }
          tone={totalActive === totalEmployees ? 'green' : 'yellow'}
        />
        <KPIStrip
          label="Score médio"
          value={avgScore !== null ? avgScore.toFixed(1) : '—'}
          context={
            avgScore !== null
              ? 'Derivado de operações + retrabalho'
              : 'Sem operações registadas'
          }
          tone={avgScore !== null && avgScore >= 7 ? 'green' : avgScore !== null && avgScore >= 5 ? 'yellow' : 'gray'}
        />
        <KPIStrip
          label="Taxa de erro média"
          value={avgErr !== null ? `${(avgErr * 100).toFixed(1)}` : '—'}
          unit="%"
          context={
            avgErr !== null
              ? `Tier >12m vs <5m varia muito`
              : 'Sem rework registado'
          }
          tone={avgErr !== null && avgErr < 0.05 ? 'green' : avgErr !== null && avgErr < 0.10 ? 'yellow' : 'gray'}
        />
        <KPIStrip
          label="Cobertura crítica"
          value={criticalSkills.toString()}
          context={
            criticalSkills > 0
              ? `${criticalSkills} skill${criticalSkills !== 1 ? 's' : ''} com só 1 tier >12m`
              : 'Cobertura suficiente'
          }
          tone={criticalSkills > 0 ? 'yellow' : 'green'}
        />
      </div>

      {/* Table */}
      <Panel title="Equipa" badge={enriched.length || '—'} flush>
        {employeesQuery.isLoading ? (
          <div className="px-4 py-12 text-center text-xs text-text-dark-tertiary">
            A carregar operadores…
          </div>
        ) : employeesQuery.isError ? (
          <div className="px-4 py-12 text-center text-xs text-danger">
            Erro a carregar /v1/core/employees.
          </div>
        ) : enriched.length === 0 ? (
          <div className="px-4 py-12 text-center text-xs text-text-dark-tertiary">
            Sem operadores registados.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: 'var(--bg-2)' }}>
                  {['Operador', 'Tier', 'Score', 'Taxa erro', 'Operações', 'Skill principal', 'Estado', ''].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: '10px 16px',
                        textAlign: 'left',
                        fontSize: 11,
                        color: 'var(--fg-2)',
                        fontWeight: 600,
                        textTransform: 'uppercase',
                        letterSpacing: 0.4,
                        borderBottom: '1px solid var(--bd-1)',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {enriched.map((w, i) => {
                  const scoreTone =
                    w.score === null
                      ? 'gray'
                      : w.score >= 8
                        ? 'green'
                        : w.score >= 6
                          ? 'blue'
                          : w.score >= 4
                            ? 'yellow'
                            : 'red';
                  const errTone =
                    w.err === null
                      ? 'gray'
                      : w.err < 0.05
                        ? 'green'
                        : w.err < 0.1
                          ? 'blue'
                          : w.err < 0.18
                            ? 'yellow'
                            : 'red';
                  return (
                    <tr
                      key={w.id}
                      style={{
                        cursor: 'pointer',
                        borderBottom:
                          i < enriched.length - 1
                            ? '1px solid var(--bd-1)'
                            : 'none',
                        transition: 'background-color 0.12s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'var(--bg-1)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent';
                      }}
                    >
                      <td style={{ padding: '12px 16px' }}>
                        <div className="flex items-center gap-2.5">
                          <WorkerAvatar name={w.employee_name} size={30} />
                          <span className="font-medium text-text-dark-primary">
                            {w.employee_name}
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <ZipToneBadge tone={tierTone(w.tier)} size="sm">
                          {w.tier}
                        </ZipToneBadge>
                      </td>
                      <td style={{ padding: '12px 16px' }} className="tabular-nums">
                        <span
                          style={{
                            color: `var(--${scoreTone})`,
                            fontWeight: 600,
                          }}
                        >
                          ★ {w.score !== null ? w.score.toFixed(1) : '—'}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px' }} className="tabular-nums">
                        <span
                          style={{
                            color: `var(--${errTone})`,
                            fontWeight: 600,
                          }}
                        >
                          {w.err !== null ? `${(w.err * 100).toFixed(1)}%` : '—'}
                        </span>
                      </td>
                      <td
                        style={{ padding: '12px 16px', color: 'var(--fg-1)' }}
                        className="tabular-nums"
                      >
                        {w.ops !== null ? w.ops.toLocaleString('pt-PT') : '—'}
                      </td>
                      <td style={{ padding: '12px 16px', color: 'var(--fg-1)' }}>
                        {w.job_title ?? '—'}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        {w.status === 'ACTIVE' ? (
                          <span style={{ fontSize: 12, color: 'var(--green)' }}>
                            ● Activo
                          </span>
                        ) : (
                          <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>
                            ○ {w.status === 'VACATION' ? 'Férias' : 'Inactivo'}
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <ChevronRight size={14} className="text-text-dark-tertiary" />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// AlocacoesTab — port literal page-dispatch.jsx
// ═══════════════════════════════════════════════════════════════════════════

function AlocacoesTab() {
  const employeesQuery = useQuery({
    queryKey: ['equipa', 'alocacoes', 'employees'],
    queryFn: fetchEmployees,
    staleTime: 60_000,
    retry: 0,
  });
  const ordersQuery = useQuery({
    queryKey: ['equipa', 'alocacoes', 'orders'],
    queryFn: fetchActiveOrders,
    staleTime: 30_000,
    retry: 0,
  });
  const statsQuery = useQuery({
    queryKey: ['equipa', 'alocacoes', 'stats', employeesQuery.data?.map((e) => e.id).join(',')],
    queryFn: async () => {
      if (!employeesQuery.data) return new Map();
      const results = await Promise.all(
        employeesQuery.data.map(async (e) => {
          const stats = await fetchEmployeeQualityScore(e.id);
          return [e.id, stats] as const;
        }),
      );
      return new Map(results);
    },
    enabled: !!employeesQuery.data && employeesQuery.data.length > 0,
    staleTime: 60_000,
    retry: 0,
  });

  const employees = employeesQuery.data ?? [];
  const orders = ordersQuery.data ?? [];

  return (
    <div className="space-y-5">
      {/* Explainer */}
      <div
        style={{
          padding: '12px 16px',
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 8,
          fontSize: 12,
          color: 'var(--fg-2)',
          lineHeight: 1.5,
        }}
      >
        <strong style={{ color: 'var(--fg-1)' }}>Como funciona:</strong>{' '}
        Cada operador tem skills com score 0–10 baseado no histórico (taxa de
        erro, qualidade, tempo). O sistema sugere a melhor atribuição mas você
        pode arrastar-e-largar livremente. Operadores tier{' '}
        <code
          style={{
            color: 'var(--fg-1)',
            background: 'var(--bd-1)',
            padding: '0 4px',
            borderRadius: 3,
            fontFamily: 'monospace',
          }}
        >
          &lt;5m
        </code>{' '}
        precisam de supervisão.
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 18 }}>
        {/* Left: Operadores */}
        <div>
          <SectionHeader title="Operadores" subtitle="Disponíveis hoje" />
          <div className="flex flex-col gap-2">
            {employeesQuery.isLoading ? (
              <div className="px-3 py-6 text-center text-xs text-text-dark-tertiary">
                A carregar operadores…
              </div>
            ) : employees.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs text-text-dark-tertiary">
                Sem operadores registados.
              </div>
            ) : (
              employees.map((e) => {
                const stats: any = statsQuery.data?.get(e.id);
                const score = stats?.score ?? null;
                return (
                  <WorkerRowZip
                    key={e.id}
                    employee={e}
                    score={score}
                  />
                );
              })
            )}
          </div>
        </div>

        {/* Right: Atribuições */}
        <div>
          <SectionHeader
            title="Atribuições de hoje"
            subtitle={`${orders.length} barcos · arraste operadores para reatribuir`}
          />
          <div className="flex flex-col gap-2.5">
            {ordersQuery.isLoading ? (
              <div className="px-3 py-6 text-center text-xs text-text-dark-tertiary">
                A carregar barcos…
              </div>
            ) : orders.length === 0 ? (
              <div className="px-3 py-6 text-center text-xs text-text-dark-tertiary">
                Sem barcos activos.
              </div>
            ) : (
              orders.slice(0, 8).map((o) => <DispatchRowZip key={o.id} order={o} />)
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Helpers visuais
// ═══════════════════════════════════════════════════════════════════════════

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <div className="text-sm font-semibold text-text-dark-primary">{title}</div>
      {subtitle ? (
        <div className="text-xs text-text-dark-tertiary mt-0.5">{subtitle}</div>
      ) : null}
    </div>
  );
}

function KPIStrip({
  label,
  value,
  unit,
  context,
  tone,
}: {
  label: string;
  value: string;
  unit?: string;
  context: string;
  tone: 'green' | 'yellow' | 'red' | 'blue' | 'gray';
}) {
  return (
    <div
      style={{
        padding: '16px 18px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 12,
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-2)',
          fontWeight: 500,
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div className="flex items-baseline gap-1 tabular-nums">
        <span
          style={{
            fontSize: 28,
            fontWeight: 700,
            color: `var(--${tone})`,
            lineHeight: 1,
          }}
        >
          {value}
        </span>
        {unit ? (
          <span style={{ fontSize: 13, color: 'var(--fg-2)' }}>
            {unit}
          </span>
        ) : null}
      </div>
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          marginTop: 6,
          lineHeight: 1.4,
        }}
      >
        {context}
      </div>
    </div>
  );
}

function WorkerAvatar({ name, size = 32 }: { name: string; size?: number }) {
  const init = initials(name);
  // Hash-based deterministic color from name
  const hash = name.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
  const tones = ['green', 'blue', 'yellow', 'orange', 'purple'];
  const tone = tones[hash % tones.length];
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        background: `var(--${tone}-bg)`,
        border: `1px solid var(--${tone}-bd)`,
        color: `var(--${tone})`,
        display: 'grid',
        placeItems: 'center',
        fontSize: Math.round(size * 0.38),
        fontWeight: 600,
        flexShrink: 0,
      }}
    >
      {init}
    </div>
  );
}

function WorkerRowZip({
  employee,
  score,
}: {
  employee: Employee;
  score: number | null;
}) {
  const tone =
    score === null
      ? 'gray'
      : score >= 8
        ? 'green'
        : score >= 6
          ? 'blue'
          : score >= 4
            ? 'yellow'
            : 'red';
  const isAvailable = employee.status === 'ACTIVE';
  const statusLabel = isAvailable ? 'Disponível' : 'Férias';

  return (
    <div
      style={{
        padding: '10px 12px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 8,
        display: 'flex',
        alignItems: 'center',
        gap: 11,
        cursor: 'grab',
        opacity: isAvailable ? 1 : 0.5,
      }}
    >
      <GripVertical size={14} className="text-text-dark-tertiary" />
      <WorkerAvatar name={employee.employee_name} size={32} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="flex items-baseline justify-between gap-2">
          <span
            className="text-sm font-medium text-text-dark-primary truncate"
            title={employee.employee_name}
          >
            {employee.employee_name}
          </span>
          <span
            className="text-xs tabular-nums font-semibold shrink-0"
            style={{ color: `var(--${tone})` }}
          >
            ★ {score !== null ? score.toFixed(1) : '—'}
          </span>
        </div>
        <div className="flex items-center justify-between gap-2 text-[11px] mt-1">
          <span className="text-text-dark-secondary truncate">
            {employee.job_title ?? '—'}
          </span>
          <span
            style={{
              color: isAvailable ? 'var(--green)' : 'var(--fg-3)',
            }}
          >
            ● {statusLabel}
          </span>
        </div>
      </div>
    </div>
  );
}

function DispatchRowZip({ order }: { order: ActiveOrder }) {
  const hull = parseInt(order.hull ?? '0', 10) || 0;
  const clientCode = HULL_CLIENT[hull];
  const clientFlag = clientCode ? CLIENT_FLAGS[clientCode] : '';
  const status = deriveBoatStatus(order.transport_date, order.phase);
  const statusColor = {
    on_time: 'green',
    at_risk: 'yellow',
    late: 'red',
    curing: 'gray',
    completed: 'blue',
  }[status];
  const dx = order.transport_date
    ? Math.max(
        0,
        Math.round(
          (new Date(order.transport_date).getTime() -
            new Date().setHours(0, 0, 0, 0)) /
            (1000 * 60 * 60 * 24),
        ),
      )
    : null;

  return (
    <div
      style={{
        padding: '14px 16px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderLeft: `3px solid var(--${statusColor})`,
        borderRadius: 8,
        display: 'grid',
        gridTemplateColumns: '180px 1fr auto',
        gap: 14,
        alignItems: 'center',
      }}
    >
      <div>
        <div className="text-sm font-semibold text-text-dark-primary">
          {order.product_type} #{hull || '—'}{' '}
          <span style={{ marginLeft: 4 }}>{clientFlag}</span>
        </div>
        <div className="text-[11px] text-text-dark-secondary mt-0.5 truncate">
          {order.product_name}
        </div>
        <div className="mt-1.5">
          <ZipStatusBadge status={status} size="sm" />
        </div>
      </div>

      <div>
        <div
          className="text-[11px] text-text-dark-tertiary uppercase tracking-wider mb-1.5"
          style={{ letterSpacing: 0.4 }}
        >
          {order.phase ?? '—'}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '8px 10px',
            background: 'var(--bg-2)',
            border: '1px dashed var(--bd-2)',
            borderRadius: 6,
            minHeight: 42,
          }}
        >
          <span className="text-xs text-text-dark-tertiary">
            Arraste um operador para aqui
          </span>
        </div>
      </div>

      <div style={{ textAlign: 'right' }}>
        <div className="text-[11px] text-text-dark-tertiary">Expedição</div>
        <div className="text-sm font-medium text-text-dark-primary mt-0.5 tabular-nums">
          {order.transport_date
            ? `${order.transport_date.slice(8, 10)}/${order.transport_date.slice(5, 7)}`
            : '—'}
        </div>
        <div className="text-[11px] text-text-dark-secondary mt-0.5">
          {dx !== null ? `D−${dx}` : ''}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// FocusBanner — preserve from previous (Risco/Simulador/Formação share dashboard)
// ═══════════════════════════════════════════════════════════════════════════

function FocusBanner({ focus }: { focus: 'risco' | 'simulador' | 'formacao' }) {
  const labels = {
    risco: {
      title: 'Tab Risco',
      hint: 'Painel completo abaixo: foca em RiskHeatmap (skill × operador) + SPOFs + DependencyGraph + CascadeImpact.',
    },
    simulador: {
      title: 'Tab Simulador',
      hint: 'Painel completo abaixo: foca em WorkforceSimulator (what-if ausência) + ScenarioComparisonMatrix.',
    },
    formacao: {
      title: 'Tab Formação',
      hint: 'Painel completo abaixo: foca em TrainingRecommendation (planos sugeridos por skill gap).',
    },
  };
  const f = labels[focus];
  return (
    <div className="mx-2 mb-3 flex items-start gap-2 px-3 py-2 rounded-md bg-primary-500/5 border border-primary-500/20">
      <Info size={14} className="shrink-0 mt-0.5 text-primary-300" />
      <div className="flex-1 text-xs">
        <span className="font-semibold text-primary-300">{f.title}</span>
        <span className="text-text-dark-secondary"> · {f.hint}</span>
      </div>
    </div>
  );
}
