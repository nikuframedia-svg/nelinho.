// EquipaPage · ListaTab (Q.60.T). ZERO MOCKS — endpoints reais.
import { useMemo, useState } from 'react';
import { Users, GitBranch, Search, X } from 'lucide-react';
import { KPIBig, EmptyState, NeloWorkerAvatar } from '../../../components/dark';
import { type QualityScoreResult } from '../../../lib/api';
import { type WorkerProfileEmployee } from '../../../components/equipa/WorkerProfile';
import { LevelBadge, LevelScaleLegend } from '../../../components/equipa/LevelScale';
import { qualityToLevel, type Tier, type EnrichedEmployee, TIER_TONE, scoreTone, type SortKey, SortHeader, FilterSelect, Tag } from '../equipaShared';

export function ListaTab({
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
        case 'nivel':
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
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
            <LevelScaleLegend />
            <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              {filtered.length} de {employees.length}
            </span>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 720 }}>
            <thead>
              <tr style={{ background: 'var(--bg-2)' }}>
                <SortHeader label="Operador" col="name" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} />
                <SortHeader label="Skill principal" col={null} />
                <SortHeader label="Tier" col="tier" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} align="right" />
                <SortHeader label="Score" col="score" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} align="right" />
                <SortHeader label="Nível" col="nivel" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} align="right" />
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
                    <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                      {w.score !== null ? (
                        <LevelBadge level={qualityToLevel(w.score)} />
                      ) : (
                        <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>—</span>
                      )}
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

export function ComparePanel({
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
      label: 'Nível (1–3)',
      value: (e) =>
        e.score !== null ? qualityToLevel(e.score).toFixed(1) : '—',
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

export function ComparePanelRow({
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
