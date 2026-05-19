/**
 * EquipaPage — reconstrução fiel do protótipo NELO (page-equipa.jsx).
 *
 * Sprint Q.52.H · Onda 1 · Track T4.
 *
 * Tabs:
 *   • Operadores         — 4 KPIs + tabela densa ordenável com filtros,
 *     ComparePanel (até 3 lado a lado), perfil 5 sub-tabs num Sheet.
 *   • Pares & Cobertura  — matriz de co-aptidão de Laminagem (derivada
 *     das skill-matrix reais) + SPOFs + recomendações de formação.
 *   • Amanhã & Risco     — simulador "e se faltar" por operador.
 *
 * Endpoints reais (plano Q.52.H):
 *   - GET  /v1/core/employees                       (employeesApi.list)
 *   - GET  /v1/workforce/employees/{id}/quality-score · skill-matrix ·
 *          level-summary · history
 *   - PATCH .../skills                              (toggle de skill)
 *   - GET  /v1/workforce/training-recommendations   (workforceApi)
 *   - GET  /v1/workforce/risks/spof                 (equipaApi)
 *   - POST /v1/workforce/simulate/absence           (equipaApi)
 *
 * ZERO MOCKS — secções sem dados mostram empty state honesto.
 */

import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Users,
  GitBranch,
  CalendarRange,
  Search,
  ChevronUp,
  ChevronDown,
  Shield,
  Sparkles,
  RefreshCw,
  X,
} from 'lucide-react';
import {
  PageHeader,
  Tabs,
  KPIBig,
  EmptyState,
  NeloWorkerAvatar,
} from '../../components/dark';
import {
  employeesApi,
  workforceEmployeesApi,
  type QualityScoreResult,
  type SkillMatrixResult,
} from '../../lib/api';
import { workforceApi } from '../../lib/workforceApi';
import { equipaApi } from '../../components/equipa/equipaApi';
import {
  WorkerProfile,
  type WorkerProfileEmployee,
} from '../../components/equipa/WorkerProfile';
import type {
  TrainingRecommendation,
  SimulationResult,
} from '../../components/workforce/types';

// ─── Tipos ──────────────────────────────────────────────────────────────────

interface RawEmployee {
  id: string;
  employee_code: string;
  employee_name: string;
  status: string;
  hire_date: string | null;
  job_title: string | null;
  department: string | null;
}

type Tier = '>12m' | '<12m' | '<5m';

interface EnrichedEmployee extends RawEmployee {
  tier: Tier;
  score: number | null;
  err: number | null;
  ops: number | null;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function tierFromHire(hire: string | null): Tier {
  if (!hire) return '<5m';
  const months = (Date.now() - new Date(hire).getTime()) / (1000 * 60 * 60 * 24 * 30);
  if (months >= 12) return '>12m';
  if (months >= 5) return '<12m';
  return '<5m';
}

const TIER_TONE: Record<Tier, string> = {
  '>12m': 'green',
  '<12m': 'yellow',
  '<5m': 'red',
};

function scoreTone(score: number | null): string {
  if (score === null) return 'fg-3';
  if (score >= 8) return 'green';
  if (score >= 6.5) return 'yellow';
  if (score >= 5) return 'orange';
  return 'red';
}

// ═══════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════

type TabId = 'lista' | 'pares' | 'amanha';

export default function EquipaPage() {
  const [tab, setTab] = useState<TabId>('lista');
  const [selected, setSelected] = useState<WorkerProfileEmployee | null>(null);
  const [comparing, setComparing] = useState<string[]>([]);

  const employeesQuery = useQuery({
    queryKey: ['equipa', 'employees'],
    queryFn: async () => {
      const raw = (await employeesApi.list({ limit: 200 })) as RawEmployee[];
      return raw;
    },
    staleTime: 60_000,
    retry: 0,
  });
  const employees = useMemo(
    () => employeesQuery.data ?? [],
    [employeesQuery.data],
  );

  // Quality scores em paralelo — score / erro / ops por operador.
  const statsQuery = useQuery({
    queryKey: ['equipa', 'quality-scores', employees.map((e) => e.id).join(',')],
    queryFn: async () => {
      const entries = await Promise.all(
        employees.map(async (e) => {
          try {
            return [e.id, await workforceEmployeesApi.qualityScore(e.id)] as const;
          } catch {
            return [e.id, null] as const;
          }
        }),
      );
      return new Map<string, QualityScoreResult | null>(entries);
    },
    enabled: employees.length > 0,
    staleTime: 60_000,
    retry: 0,
  });

  const enriched: EnrichedEmployee[] = useMemo(() => {
    const stats = statsQuery.data;
    return employees.map((e) => {
      const s = stats?.get(e.id) ?? null;
      return {
        ...e,
        tier: tierFromHire(e.hire_date),
        score: s?.score ?? null,
        err: s?.defect_rate ?? null,
        ops: s?.operations ?? null,
      };
    });
  }, [employees, statsQuery.data]);

  const toggleCompare = (id: string) => {
    setComparing((prev) =>
      prev.includes(id)
        ? prev.filter((x) => x !== id)
        : prev.length >= 3
          ? prev
          : [...prev, id],
    );
  };

  const tabs = [
    { id: 'lista', label: 'Operadores', icon: <Users size={13} /> },
    { id: 'pares', label: 'Pares & Cobertura', icon: <GitBranch size={13} /> },
    { id: 'amanha', label: 'Amanhã & Risco', icon: <CalendarRange size={13} /> },
  ];

  return (
    <div>
      <PageHeader
        title="Equipa"
        subtitle="Operadores · tabela filtrável · pares de Laminagem · simulador de ausência"
        helpId="operadores"
        actions={
          <button
            type="button"
            onClick={() => employeesQuery.refetch()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
          >
            <RefreshCw size={13} />
            Atualizar
          </button>
        }
      />

      <div className="px-6 pt-2">
        <Tabs tabs={tabs} value={tab} onChange={(id) => setTab(id as TabId)} />
      </div>

      <div className="px-6 py-4 page-enter">
        {tab === 'lista' && (
          <ListaTab
            employees={enriched}
            isLoading={employeesQuery.isLoading || statsQuery.isLoading}
            isError={employeesQuery.isError}
            comparing={comparing}
            onSelect={setSelected}
            onCompare={toggleCompare}
          />
        )}
        {tab === 'pares' && <ParesTab employees={enriched} />}
        {tab === 'amanha' && <AmanhaTab employees={enriched} />}
      </div>

      <WorkerProfile
        employee={selected}
        onClose={() => setSelected(null)}
        onCompare={(id) => {
          toggleCompare(id);
          setSelected(null);
        }}
      />
      <ComparePanel
        ids={comparing}
        employees={enriched}
        stats={statsQuery.data}
        onRemove={toggleCompare}
        onClose={() => setComparing([])}
      />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ListaTab — KPIs + tabela densa ordenável
// ═══════════════════════════════════════════════════════════════════════════

type SortKey = 'name' | 'tier' | 'score' | 'err' | 'ops' | 'status';

function ListaTab({
  employees,
  isLoading,
  isError,
  comparing,
  onSelect,
  onCompare,
}: {
  employees: EnrichedEmployee[];
  isLoading: boolean;
  isError: boolean;
  comparing: string[];
  onSelect: (e: WorkerProfileEmployee) => void;
  onCompare: (id: string) => void;
}) {
  const [sortBy, setSortBy] = useState<SortKey>('score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [search, setSearch] = useState('');
  const [tierFilter, setTierFilter] = useState<'all' | Tier>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'inactive'>('all');

  const toggleSort = (col: SortKey) => {
    if (sortBy === col) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    else {
      setSortBy(col);
      setSortDir('desc');
    }
  };

  const filtered = useMemo(() => {
    const rows = employees.filter((e) => {
      if (tierFilter !== 'all' && e.tier !== tierFilter) return false;
      if (statusFilter === 'active' && e.status !== 'ACTIVE') return false;
      if (statusFilter === 'inactive' && e.status === 'ACTIVE') return false;
      if (search && !e.employee_name.toLowerCase().includes(search.toLowerCase()))
        return false;
      return true;
    });
    rows.sort((a, b) => {
      let cmp = 0;
      switch (sortBy) {
        case 'name':
          cmp = a.employee_name.localeCompare(b.employee_name);
          break;
        case 'tier':
          cmp = a.tier.localeCompare(b.tier);
          break;
        case 'status':
          cmp = a.status.localeCompare(b.status);
          break;
        case 'score':
          cmp = (a.score ?? -1) - (b.score ?? -1);
          break;
        case 'err':
          cmp = (a.err ?? 999) - (b.err ?? 999);
          break;
        case 'ops':
          cmp = (a.ops ?? -1) - (b.ops ?? -1);
          break;
      }
      return sortDir === 'desc' ? -cmp : cmp;
    });
    return rows;
  }, [employees, search, tierFilter, statusFilter, sortBy, sortDir]);

  // KPIs
  const totalActive = employees.filter((e) => e.status === 'ACTIVE').length;
  const validScores = employees.filter((e) => e.score !== null);
  const avgScore =
    validScores.length > 0
      ? validScores.reduce((s, e) => s + (e.score ?? 0), 0) / validScores.length
      : null;
  const tierExp = employees.filter((e) => e.tier === '>12m').length;
  const validErr = employees.filter((e) => e.err !== null);
  const avgErr =
    validErr.length > 0
      ? validErr.reduce((s, e) => s + (e.err ?? 0), 0) / validErr.length
      : null;

  if (isLoading) {
    return (
      <div className="px-4 py-12 text-center text-xs text-text-dark-tertiary">
        A carregar operadores…
      </div>
    );
  }
  if (isError) {
    return (
      <div className="px-4 py-12 text-center text-xs text-danger">
        Erro a carregar /v1/core/employees.
      </div>
    );
  }
  if (employees.length === 0) {
    return (
      <EmptyState
        title="Sem operadores registados"
        hint="Adiciona operadores no ERP MAR-KAYAKS."
        icon={<Users size={32} />}
      />
    );
  }

  return (
    <div className="space-y-4">
      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        <KPIBig
          label="Operadores activos"
          value={totalActive}
          unit={`/ ${employees.length}`}
          context={
            totalActive === employees.length
              ? 'Todos disponíveis'
              : `${employees.length - totalActive} ausentes`
          }
          accent="accent"
        />
        <KPIBig
          label="Score médio"
          value={avgScore !== null ? avgScore.toFixed(1) : '—'}
          prefix="★"
          context={
            avgScore !== null
              ? 'Derivado de operações + retrabalho'
              : 'Sem operações registadas'
          }
          status={avgScore !== null && avgScore >= 7 ? 'green' : 'yellow'}
          accent="green"
        />
        <KPIBig
          label="Tier >12m"
          value={tierExp}
          context="Operadores séniores"
          status="green"
          accent="green"
        />
        <KPIBig
          label="Taxa de erro média"
          value={avgErr !== null ? (avgErr * 100).toFixed(1) : '—'}
          unit="%"
          context={avgErr !== null ? 'Varia muito por tier' : 'Sem rework registado'}
          status={avgErr !== null && avgErr < 0.05 ? 'green' : 'yellow'}
          accent="red"
        />
      </div>

      {/* Tabela */}
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          overflow: 'hidden',
        }}
      >
        {/* Filtros */}
        <div
          style={{
            padding: '10px 14px',
            borderBottom: '1px solid var(--bd-1)',
            background: 'var(--bg-2)',
            display: 'flex',
            gap: 8,
            alignItems: 'center',
            flexWrap: 'wrap',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '4px 10px',
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 6,
              minWidth: 200,
            }}
          >
            <Search size={11} color="var(--fg-3)" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Procurar nome…"
              className="text-slate-900 placeholder:text-slate-400"
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: 'var(--fg-0)',
                fontSize: 11.5,
              }}
            />
          </div>
          <FilterSelect
            value={tierFilter}
            onChange={(v) => setTierFilter(v as 'all' | Tier)}
            options={[
              { value: 'all', label: 'Todos os tiers' },
              { value: '>12m', label: '>12m' },
              { value: '<12m', label: '<12m' },
              { value: '<5m', label: '<5m' },
            ]}
          />
          <FilterSelect
            value={statusFilter}
            onChange={(v) => setStatusFilter(v as 'all' | 'active' | 'inactive')}
            options={[
              { value: 'all', label: 'Todos os estados' },
              { value: 'active', label: 'Activos' },
              { value: 'inactive', label: 'Inactivos' },
            ]}
          />
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--fg-3)' }}>
            {filtered.length} de {employees.length}
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
            <thead>
              <tr style={{ background: 'var(--bg-2)' }}>
                <SortHeader label="Operador" col="name" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} />
                <SortHeader label="Skill principal" col={null} />
                <SortHeader label="Tier" col="tier" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} align="right" />
                <SortHeader label="Score" col="score" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} align="right" />
                <SortHeader label="Erro" col="err" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} align="right" />
                <SortHeader label="Ops" col="ops" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} align="right" />
                <SortHeader label="Estado" col="status" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} align="right" />
                <SortHeader label="" col={null} align="right" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((w) => {
                const isComparing = comparing.includes(w.id);
                const tone = scoreTone(w.score);
                return (
                  <tr
                    key={w.id}
                    onClick={() =>
                      onSelect({ id: w.id, name: w.employee_name, tier: w.tier })
                    }
                    className="cursor-pointer transition-colors hover:bg-white/[0.03]"
                    style={{
                      borderBottom: '1px solid var(--bd-1)',
                      background: isComparing ? 'var(--accent-bg)' : 'transparent',
                      boxShadow: `inset 3px 0 0 0 var(--${TIER_TONE[w.tier]})`,
                    }}
                  >
                    <td style={{ padding: '10px 14px' }}>
                      <div className="flex items-center gap-2.5">
                        <NeloWorkerAvatar worker={{ name: w.employee_name }} size={26} />
                        <div>
                          <div
                            style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}
                          >
                            {w.employee_name}
                          </div>
                          <div style={{ fontSize: 10, color: 'var(--fg-3)' }}>
                            {w.employee_code}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td
                      style={{ padding: '10px 14px', fontSize: 11.5, color: 'var(--fg-1)' }}
                    >
                      {w.job_title ?? '—'}
                    </td>
                    <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                      <Tag tone={TIER_TONE[w.tier]}>{w.tier}</Tag>
                    </td>
                    <td
                      className="tabular"
                      style={{
                        padding: '10px 14px',
                        textAlign: 'right',
                        fontSize: 12,
                        color: `var(--${tone})`,
                        fontWeight: 600,
                      }}
                    >
                      {w.score !== null ? `★${w.score.toFixed(1)}` : '—'}
                    </td>
                    <td
                      className="tabular"
                      style={{
                        padding: '10px 14px',
                        textAlign: 'right',
                        fontSize: 11.5,
                        color:
                          w.err !== null && w.err > 0.1 ? 'var(--red)' : 'var(--fg-1)',
                      }}
                    >
                      {w.err !== null ? `${(w.err * 100).toFixed(1)}%` : '—'}
                    </td>
                    <td
                      className="tabular"
                      style={{
                        padding: '10px 14px',
                        textAlign: 'right',
                        fontSize: 11,
                        color: 'var(--fg-2)',
                      }}
                    >
                      {w.ops !== null ? w.ops.toLocaleString('pt-PT') : '—'}
                    </td>
                    <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                      <span
                        style={{
                          fontSize: 11.5,
                          color:
                            w.status === 'ACTIVE' ? 'var(--green)' : 'var(--fg-3)',
                        }}
                      >
                        {w.status === 'ACTIVE' ? '● Activo' : '○ Inactivo'}
                      </span>
                    </td>
                    <td
                      style={{ padding: '10px 14px', textAlign: 'right' }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        type="button"
                        onClick={() => onCompare(w.id)}
                        title="Comparar"
                        style={{
                          width: 26,
                          height: 26,
                          borderRadius: 6,
                          background: isComparing ? 'var(--blue-bg)' : 'transparent',
                          border: `1px solid ${isComparing ? 'var(--blue-bd)' : 'var(--bd-1)'}`,
                          color: isComparing ? 'var(--blue)' : 'var(--fg-3)',
                          cursor: 'pointer',
                          display: 'inline-grid',
                          placeItems: 'center',
                        }}
                      >
                        <GitBranch size={11} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ─── ComparePanel — até 3 operadores lado a lado ────────────────────────────

function ComparePanel({
  ids,
  employees,
  stats,
  onRemove,
  onClose,
}: {
  ids: string[];
  employees: EnrichedEmployee[];
  stats: Map<string, QualityScoreResult | null> | undefined;
  onRemove: (id: string) => void;
  onClose: () => void;
}) {
  if (ids.length === 0) return null;
  const selected = ids
    .map((id) => employees.find((e) => e.id === id))
    .filter((e): e is EnrichedEmployee => !!e);
  if (selected.length === 0) return null;

  const rows: Array<{
    label: string;
    value: (e: EnrichedEmployee) => string;
    color?: (e: EnrichedEmployee) => string;
  }> = [
    { label: 'Skill principal', value: (e) => e.job_title ?? '—' },
    {
      label: 'Score',
      value: (e) => (e.score !== null ? `★${e.score.toFixed(1)}` : '—'),
      color: (e) => `var(--${scoreTone(e.score)})`,
    },
    {
      label: 'Taxa de erro',
      value: (e) => (e.err !== null ? `${(e.err * 100).toFixed(1)}%` : '—'),
      color: (e) => (e.err !== null && e.err > 0.1 ? 'var(--red)' : 'var(--fg-0)'),
    },
    { label: 'Tier', value: (e) => e.tier },
    {
      label: 'Operações',
      value: (e) => {
        const s = stats?.get(e.id);
        return s ? s.operations.toLocaleString('pt-PT') : '—';
      },
    },
    {
      label: 'Defeitos',
      value: (e) => {
        const s = stats?.get(e.id);
        return s ? String(s.defects) : '—';
      },
    },
  ];

  return (
    <div
      className="anim-up"
      style={{
        position: 'fixed',
        bottom: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        width: 'min(94vw, 880px)',
        zIndex: 100,
      }}
    >
      <div
        style={{
          background: 'rgba(18,18,22,0.96)',
          backdropFilter: 'blur(20px)',
          border: '1px solid var(--bd-3)',
          borderRadius: 'var(--r-lg)',
          boxShadow: 'var(--shadow-3)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            borderBottom: '1px solid var(--bd-1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <GitBranch size={13} color="var(--accent)" />
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-0)' }}>
              Comparar {selected.length} operadores
            </span>
            <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>· até 3 lado a lado</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar comparação"
            style={{
              width: 24,
              height: 24,
              borderRadius: 6,
              background: 'transparent',
              border: 'none',
              color: 'var(--fg-2)',
              cursor: 'pointer',
              display: 'grid',
              placeItems: 'center',
            }}
          >
            <X size={12} />
          </button>
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: `180px repeat(${selected.length}, 1fr)`,
          }}
        >
          <div style={{ background: 'var(--bg-2)', borderRight: '1px solid var(--bd-1)' }} />
          {selected.map((e) => (
            <div
              key={e.id}
              style={{
                padding: '10px 14px',
                borderRight: '1px solid var(--bd-1)',
                background: 'var(--bg-2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <NeloWorkerAvatar
                worker={{ name: e.employee_name, score: e.score ?? undefined, tier: e.tier }}
                size={28}
                showName
                showScore
              />
              <button
                type="button"
                onClick={() => onRemove(e.id)}
                aria-label={`Remover ${e.employee_name}`}
                style={{
                  width: 18,
                  height: 18,
                  borderRadius: 4,
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--fg-3)',
                  cursor: 'pointer',
                  display: 'grid',
                  placeItems: 'center',
                }}
              >
                <X size={10} />
              </button>
            </div>
          ))}
          {rows.map((r) => (
            <ComparePanelRow key={r.label} row={r} selected={selected} />
          ))}
        </div>
      </div>
    </div>
  );
}

function ComparePanelRow({
  row,
  selected,
}: {
  row: {
    label: string;
    value: (e: EnrichedEmployee) => string;
    color?: (e: EnrichedEmployee) => string;
  };
  selected: EnrichedEmployee[];
}) {
  return (
    <>
      <div
        style={{
          padding: '8px 14px',
          borderTop: '1px solid var(--bd-1)',
          borderRight: '1px solid var(--bd-1)',
          background: 'var(--bg-1)',
          fontSize: 11,
          color: 'var(--fg-3)',
        }}
      >
        {row.label}
      </div>
      {selected.map((e) => (
        <div
          key={e.id}
          style={{
            padding: '8px 14px',
            borderTop: '1px solid var(--bd-1)',
            borderRight: '1px solid var(--bd-1)',
          }}
        >
          <span
            className="tabular"
            style={{
              fontSize: 12.5,
              color: row.color ? row.color(e) : 'var(--fg-0)',
              fontWeight: 500,
            }}
          >
            {row.value(e)}
          </span>
        </div>
      ))}
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// ParesTab — matriz de co-aptidão de Laminagem + SPOFs + formação
// ═══════════════════════════════════════════════════════════════════════════

function ParesTab({ employees }: { employees: EnrichedEmployee[] }) {
  // Skill-matrix de cada operador → quem está apto a Laminagem.
  const matricesQuery = useQuery({
    queryKey: ['equipa', 'pares', 'matrices', employees.map((e) => e.id).join(',')],
    queryFn: async () => {
      const entries = await Promise.all(
        employees.map(async (e) => {
          try {
            return [e.id, await workforceEmployeesApi.skillMatrix(e.id)] as const;
          } catch {
            return [e.id, null] as const;
          }
        }),
      );
      return new Map<string, SkillMatrixResult | null>(entries);
    },
    enabled: employees.length > 0,
    staleTime: 120_000,
    retry: 0,
  });

  const spofQuery = useQuery({
    queryKey: ['equipa', 'pares', 'spof'],
    queryFn: () => equipaApi.spofs(8),
    staleTime: 120_000,
    retry: 0,
  });

  // Laminadores = operadores aptos a uma fase cujo nome contém "lamina".
  const laminadores = useMemo(() => {
    const data = matricesQuery.data;
    if (!data) return [];
    return employees.filter((e) => {
      const m = data.get(e.id);
      return (
        m?.phases.some(
          (p) =>
            p.can_do &&
            (p.phase_name ?? '').toLowerCase().includes('lamina'),
        ) ?? false
      );
    });
  }, [employees, matricesQuery.data]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 14 }}>
      {/* Matriz de co-aptidão */}
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionHeader
          icon={<GitBranch size={14} />}
          title="Pares de Laminagem · co-aptidão"
          subtitle="Operadores aptos à mesma fase de Laminagem podem formar par — verde = ambos séniores"
        />
        {matricesQuery.isLoading ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            A carregar skill-matrix…
          </div>
        ) : laminadores.length < 2 ? (
          <div style={{ padding: 24, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            Sem laminadores suficientes para uma matriz de pares.
          </div>
        ) : (
          <PairMatrix laminadores={laminadores} />
        )}
      </div>

      {/* SPOFs + formação */}
      <div className="space-y-3">
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-lg)',
            padding: 18,
          }}
        >
          <SectionHeader
            icon={<Shield size={14} />}
            title="Single Points of Failure"
            subtitle="Fases que dependem de um só operador apto"
          />
          {spofQuery.isLoading ? (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
              A carregar SPOFs…
            </div>
          ) : spofQuery.isError ? (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--danger)', fontSize: 12 }}>
              Erro a carregar /v1/workforce/risks/spof.
            </div>
          ) : !spofQuery.data || spofQuery.data.length === 0 ? (
            <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
              Sem SPOFs detectados — cobertura suficiente.
            </div>
          ) : (
            spofQuery.data.map((rec) => <SpofCard key={rec.id} rec={rec} />)
          )}
        </div>
      </div>
    </div>
  );
}

function PairMatrix({ laminadores }: { laminadores: EnrichedEmployee[] }) {
  // Score de par derivado dos dados reais: tier + taxa de erro.
  const pairScore = (a: EnrichedEmployee, b: EnrichedEmployee): number | null => {
    if (a.id === b.id) return null;
    let s = 5;
    if (a.tier === '>12m' && b.tier === '>12m') s += 2.5;
    else if (a.tier === '<5m' || b.tier === '<5m') s -= 1.8;
    else s += 0.8;
    if (a.err !== null && b.err !== null) {
      const diff = Math.abs(a.err - b.err);
      if (diff < 0.02) s += 0.7;
      if (diff > 0.1) s -= 0.9;
    }
    return Math.max(0, Math.min(10, s));
  };
  const tone = (s: number) => (s >= 7.5 ? 'green' : s >= 6 ? 'yellow' : 'red');

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th />
            {laminadores.map((w) => (
              <th
                key={w.id}
                style={{
                  padding: '4px 3px',
                  fontSize: 9.5,
                  color: 'var(--fg-3)',
                  fontWeight: 500,
                  whiteSpace: 'nowrap',
                  height: 56,
                }}
              >
                <span style={{ display: 'inline-block', transform: 'rotate(-40deg)' }}>
                  {w.employee_name.split(/\s+/)[0]}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {laminadores.map((a) => (
            <tr key={a.id}>
              <td
                style={{
                  padding: '3px 8px',
                  fontSize: 10.5,
                  color: 'var(--fg-1)',
                  whiteSpace: 'nowrap',
                  textAlign: 'right',
                }}
              >
                {a.employee_name.split(/\s+/)[0]}
              </td>
              {laminadores.map((b) => {
                const s = pairScore(a, b);
                if (s === null) {
                  return (
                    <td
                      key={b.id}
                      style={{ width: 30, height: 30, background: 'var(--bg-3)' }}
                    />
                  );
                }
                const t = tone(s);
                return (
                  <td
                    key={b.id}
                    title={`${a.employee_name} + ${b.employee_name}: ${s.toFixed(1)}/10`}
                    style={{
                      width: 30,
                      height: 30,
                      textAlign: 'center',
                      background: `var(--${t}-bg)`,
                      border: `1px solid var(--${t}-bd)`,
                      fontSize: 10,
                      fontWeight: 600,
                      color: `var(--${t})`,
                      fontFamily: 'monospace',
                    }}
                  >
                    {s.toFixed(1)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div
        style={{
          marginTop: 12,
          display: 'flex',
          gap: 14,
          fontSize: 10.5,
          color: 'var(--fg-3)',
        }}
      >
        <LegendDot tone="green" label="Excelente par (>7.5)" />
        <LegendDot tone="yellow" label="OK (6-7.5)" />
        <LegendDot tone="red" label="Evitar (<6)" />
      </div>
    </div>
  );
}

function LegendDot({ tone, label }: { tone: string; label: string }) {
  return (
    <span>
      <span
        style={{
          display: 'inline-block',
          width: 10,
          height: 10,
          background: `var(--${tone})`,
          borderRadius: 2,
          marginRight: 5,
          verticalAlign: 'middle',
        }}
      />
      {label}
    </span>
  );
}

function SpofCard({ rec }: { rec: TrainingRecommendation }) {
  return (
    <div
      style={{
        padding: 11,
        background: 'var(--red-bg)',
        border: '1px solid var(--red-bd)',
        borderRadius: 'var(--r-sm)',
        marginBottom: 8,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 4,
        }}
      >
        <span style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
          {rec.targetPhase.name}
        </span>
        <span style={{ fontSize: 10.5, color: 'var(--red)' }}>
          ⚠ -{rec.expectedImpact.riskReduction.toFixed(0)}pp risco
        </span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--fg-2)', marginBottom: 6 }}>
        Formar <strong>{rec.employee.name}</strong> elimina o ponto único de falha
      </div>
      {rec.reasoning.length > 0 ? (
        <div
          style={{
            fontSize: 11,
            color: 'var(--fg-1)',
            padding: '5px 9px',
            background: 'var(--bg-1)',
            borderRadius: 4,
            display: 'flex',
            alignItems: 'center',
            gap: 5,
          }}
        >
          <Sparkles size={10} color="var(--accent)" />
          {rec.reasoning[0]}
        </div>
      ) : null}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// AmanhaTab — simulador de ausência por operador
// ═══════════════════════════════════════════════════════════════════════════

function AmanhaTab({ employees }: { employees: EnrichedEmployee[] }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const trainingQuery = useQuery({
    queryKey: ['equipa', 'amanha', 'training'],
    queryFn: () => workforceApi.getTrainingRecommendations(8),
    staleTime: 120_000,
    retry: 0,
  });

  const simQuery = useQuery({
    queryKey: ['equipa', 'amanha', 'simulate', selectedId],
    queryFn: () => equipaApi.simulateAbsence(selectedId as string),
    enabled: !!selectedId,
    retry: 0,
  });

  const activeEmployees = employees.filter((e) => e.status === 'ACTIVE');

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
      {/* Simulador de ausência */}
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionHeader
          icon={<CalendarRange size={14} />}
          title="E se faltar amanhã?"
          subtitle="Escolhe um operador para simular a ausência"
        />
        <div style={{ marginBottom: 12 }}>
          <select
            value={selectedId ?? ''}
            onChange={(e) => setSelectedId(e.target.value || null)}
            style={{
              width: '100%',
              padding: '8px 10px',
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-2)',
              borderRadius: 'var(--r-sm)',
              color: 'var(--fg-0)',
              fontSize: 12.5,
              outline: 'none',
            }}
          >
            <option value="">Selecciona um operador…</option>
            {activeEmployees.map((e) => (
              <option key={e.id} value={e.id}>
                {e.employee_name} · {e.tier}
              </option>
            ))}
          </select>
        </div>
        {!selectedId ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            Escolhe um operador acima para ver o impacto da ausência.
          </div>
        ) : simQuery.isLoading ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            A simular…
          </div>
        ) : simQuery.isError ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--danger)', fontSize: 12 }}>
            Erro a simular a ausência.
          </div>
        ) : simQuery.data ? (
          <AbsenceImpact sim={simQuery.data} />
        ) : null}
      </div>

      {/* Recomendações de formação */}
      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionHeader
          icon={<Sparkles size={14} />}
          title="Recomendações de formação"
          subtitle="Ordenadas por impacto na redução de risco"
        />
        {trainingQuery.isLoading ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            A carregar recomendações…
          </div>
        ) : trainingQuery.isError ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--danger)', fontSize: 12 }}>
            Erro a carregar /v1/workforce/training-recommendations.
          </div>
        ) : !trainingQuery.data || trainingQuery.data.length === 0 ? (
          <div style={{ padding: 16, textAlign: 'center', color: 'var(--fg-3)', fontSize: 12 }}>
            Sem recomendações de formação de momento.
          </div>
        ) : (
          trainingQuery.data.map((rec) => (
            <div
              key={rec.id}
              style={{
                padding: 11,
                background: 'var(--bg-2)',
                border: '1px solid var(--bd-1)',
                borderRadius: 'var(--r-sm)',
                marginBottom: 8,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                }}
              >
                <span style={{ fontSize: 12, color: 'var(--fg-0)', fontWeight: 500 }}>
                  {rec.employee.name} → {rec.targetPhase.name}
                </span>
                <Tag
                  tone={
                    rec.priority === 'critical'
                      ? 'red'
                      : rec.priority === 'high'
                        ? 'orange'
                        : 'yellow'
                  }
                >
                  {rec.priority}
                </Tag>
              </div>
              <div style={{ fontSize: 11, color: 'var(--fg-2)', marginTop: 4 }}>
                {rec.reasoning[0] ?? '—'} · {rec.estimatedCost.hours}h estimadas
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function AbsenceImpact({ sim }: { sim: SimulationResult }) {
  const metrics: Array<{ label: string; baseline: number; simulated: number; worseUp: boolean }> = [
    {
      label: 'SPOFs',
      baseline: sim.baseline.spofCount,
      simulated: sim.simulated.spofCount,
      worseUp: true,
    },
    {
      label: 'Fases em risco',
      baseline: sim.baseline.phasesAtRisk,
      simulated: sim.simulated.phasesAtRisk,
      worseUp: true,
    },
    {
      label: 'Score de risco médio',
      baseline: Math.round(sim.baseline.avgRiskScore),
      simulated: Math.round(sim.simulated.avgRiskScore),
      worseUp: true,
    },
  ];
  return (
    <div className="space-y-3">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {metrics.map((m) => {
          const delta = m.simulated - m.baseline;
          const worse = m.worseUp ? delta > 0 : delta < 0;
          return (
            <div
              key={m.label}
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: '9px 12px',
                background: 'var(--bg-2)',
                borderRadius: 'var(--r-sm)',
              }}
            >
              <span style={{ fontSize: 12, color: 'var(--fg-1)' }}>{m.label}</span>
              <span className="tabular" style={{ fontSize: 12.5 }}>
                <span style={{ color: 'var(--fg-3)' }}>{m.baseline}</span>
                <span style={{ color: 'var(--fg-4)', margin: '0 6px' }}>→</span>
                <span
                  style={{
                    color: delta === 0 ? 'var(--fg-1)' : worse ? 'var(--red)' : 'var(--green)',
                    fontWeight: 600,
                  }}
                >
                  {m.simulated}
                </span>
                {delta !== 0 ? (
                  <span
                    style={{
                      color: worse ? 'var(--red)' : 'var(--green)',
                      fontSize: 10.5,
                      marginLeft: 6,
                    }}
                  >
                    ({delta > 0 ? '+' : ''}
                    {delta})
                  </span>
                ) : null}
              </span>
            </div>
          );
        })}
      </div>
      {sim.recommendations.length > 0 ? (
        <div
          style={{
            padding: 11,
            background: 'var(--accent-bg)',
            border: '1px solid var(--accent-bd)',
            borderRadius: 'var(--r-sm)',
            fontSize: 11.5,
            color: 'var(--fg-1)',
          }}
        >
          <Sparkles
            size={11}
            color="var(--accent)"
            style={{ verticalAlign: 'middle', marginRight: 6 }}
          />
          {sim.recommendations[0]}
        </div>
      ) : null}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Bits visuais partilhados
// ═══════════════════════════════════════════════════════════════════════════

function SortHeader({
  label,
  col,
  sortBy,
  sortDir,
  onSort,
  align = 'left',
}: {
  label: string;
  col: SortKey | null;
  sortBy?: SortKey;
  sortDir?: 'asc' | 'desc';
  onSort?: (col: SortKey) => void;
  align?: 'left' | 'right';
}) {
  const isActive = col !== null && sortBy === col;
  return (
    <th
      style={{
        padding: '10px 14px',
        textAlign: align,
        borderBottom: '1px solid var(--bd-1)',
      }}
    >
      {col && onSort ? (
        <button
          type="button"
          onClick={() => onSort(col)}
          style={{
            background: 'transparent',
            border: 'none',
            color: isActive ? 'var(--fg-0)' : 'var(--fg-3)',
            fontSize: 10.5,
            fontWeight: 600,
            letterSpacing: 0.4,
            textTransform: 'uppercase',
            cursor: 'pointer',
            padding: 0,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
          }}
        >
          {label}
          {isActive ? (
            sortDir === 'desc' ? (
              <ChevronDown size={11} />
            ) : (
              <ChevronUp size={11} />
            )
          ) : null}
        </button>
      ) : (
        <span
          style={{
            fontSize: 10.5,
            fontWeight: 600,
            letterSpacing: 0.4,
            textTransform: 'uppercase',
            color: 'var(--fg-3)',
          }}
        >
          {label}
        </span>
      )}
    </th>
  );
}

function FilterSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        padding: '5px 8px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 6,
        color: 'var(--fg-1)',
        fontSize: 11.5,
        outline: 'none',
      }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function Tag({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span
      style={{
        fontSize: 9.5,
        padding: '2px 7px',
        background: `var(--${tone}-bg)`,
        border: `1px solid var(--${tone}-bd)`,
        borderRadius: 4,
        color: `var(--${tone})`,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: 0.3,
      }}
    >
      {children}
    </span>
  );
}

function SectionHeader({
  icon,
  title,
  subtitle,
}: {
  icon: ReactNode;
  title: string;
  subtitle?: string;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: 'var(--accent)' }}>{icon}</span>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-0)' }}>
          {title}
        </span>
      </div>
      {subtitle ? (
        <div style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 3 }}>
          {subtitle}
        </div>
      ) : null}
    </div>
  );
}
