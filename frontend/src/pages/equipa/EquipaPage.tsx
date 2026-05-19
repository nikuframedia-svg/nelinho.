/**
 * EquipaPage — Equipa (shell · Q.60.T).
 *
 * As 3 tabs (Lista/Pares/Amanhã) foram decompostas para ./tabs/. Tipos,
 * helpers e primitivas partilhadas em ./equipaShared.
 */
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Users, GitBranch, CalendarRange, RefreshCw } from 'lucide-react';
import { PageHeader, Tabs } from '../../components/dark';
import { employeesApi, workforceEmployeesApi, type QualityScoreResult } from '../../lib/api';
import { WorkerProfile, type WorkerProfileEmployee } from '../../components/equipa/WorkerProfile';
import { type RawEmployee, type EnrichedEmployee, tierFromHire } from './equipaShared';
import { ListaTab, ComparePanel } from './tabs/ListaTab';
import { ParesTab } from './tabs/ParesTab';
import { AmanhaTab } from './tabs/AmanhaTab';

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
