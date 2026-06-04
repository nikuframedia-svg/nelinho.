/**
 * EquipaNiveisTab — /configuracoes › Equipa · Q.140.E
 *
 * Nível INDEPENDENTE por (pessoa × sector) + ordem de preferência por sector.
 * Uma pessoa multi-funcional pode ser 3.0 na Pintura e 1.5 na Laminagem.
 *
 * - Selector de sector (7 grupos de área) → ranking inverso (só aptos).
 * - Cada linha tem o nível efectivo EDITÁVEL (override manual, meio-passo).
 * - Clicar num colaborador abre os seus 7 níveis por sector (independentes).
 *
 * Dados 100% reais (factory_raw via SectorPreferenceService). ZERO MOCKS:
 * estados empty/error explícitos, nunca dados inventados.
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ChevronRight, Info } from 'lucide-react';
import { DarkCard, DarkBadge, DarkSelect, EmptyState } from '../../../components/dark';
import { SkeletonLoader } from '../../../components/ui/Skeleton';
import { workforceApi, type SectorRankingRow } from '../../../lib/workforceApi';
import { sectorKeys, operatorsKeys } from '../../../lib/api/keys';
import { useToastContext } from '../../../components/ToastProvider';

const LEVEL_LABELS: Record<string, string> = {
  '3.0': 'Top',
  '2.5': 'Avançado',
  '2.0': 'Médio',
  '1.5': 'Em progresso',
  '1.0': 'Em formação',
};

const LEVEL_OPTIONS = [
  { value: '3.0', label: '3.0 · Top' },
  { value: '2.5', label: '2.5 · Avançado' },
  { value: '2.0', label: '2.0 · Médio' },
  { value: '1.5', label: '1.5 · Em progresso' },
  { value: '1.0', label: '1.0 · Em formação' },
];

function levelText(n: number | null): string {
  if (n == null) return '—';
  const key = n.toFixed(1);
  return `${key} · ${LEVEL_LABELS[key] ?? ''}`.trim();
}

function sourceBadge(source: string) {
  switch (source) {
    case 'override':
      return <DarkBadge variant="accent" size="sm">Manual</DarkBadge>;
    case 'derived':
      return <DarkBadge variant="info" size="sm">Histórico</DarkBadge>;
    case 'erp_seed':
      return <DarkBadge variant="neutral" size="sm">ERP</DarkBadge>;
    default:
      return <DarkBadge variant="neutral" size="sm">—</DarkBadge>;
  }
}

export function EquipaNiveisTab() {
  const queryClient = useQueryClient();
  const toast = useToastContext();
  const [sector, setSector] = useState<string | null>(null);
  const [openEmployee, setOpenEmployee] = useState<string | null>(null);

  const sectorsQuery = useQuery({
    queryKey: sectorKeys.list(),
    queryFn: () => workforceApi.listSectors(),
  });

  // Q.159 — contagem canónica de "operadores ativos" (E_ACTIVO + últimos 2
  // meses, ~107) + quebra por área. Read-only.
  const operatorsQuery = useQuery({
    queryKey: operatorsKeys.summary(),
    queryFn: () => workforceApi.getOperatorsSummary(),
    staleTime: 10 * 60_000,
  });

  // Selecciona o 1º sector assim que a lista chega.
  const sectors = sectorsQuery.data?.sectors ?? [];
  const activeSector = sector ?? sectors[0] ?? null;

  const rankingQuery = useQuery({
    queryKey: sectorKeys.ranking(activeSector ?? ''),
    queryFn: () => workforceApi.getSectorRanking(activeSector as string, 200),
    enabled: !!activeSector,
  });

  const setLevel = useMutation({
    mutationFn: (vars: { employeeId: string; areaGroup: string; nivel: number }) =>
      workforceApi.setSectorLevel(
        vars.employeeId,
        vars.areaGroup,
        vars.nivel,
        'Atribuição manual via /configuracoes',
      ),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: sectorKeys.ranking(vars.areaGroup) });
      queryClient.invalidateQueries({ queryKey: sectorKeys.employeeLevels(vars.employeeId) });
      toast.success('Nível actualizado.');
    },
    onError: () => toast.error('Não foi possível guardar o nível.'),
  });

  const operators = operatorsQuery.data;
  const topAreas = (operators?.by_area ?? []).slice(0, 6);

  return (
    <div className="space-y-5">
      {/* Q.159 — contagem de operadores ativos (regra EXATA: E_ACTIVO + últimos
          2 meses). É a definição que o CPO e os dropdowns de atribuição usam. */}
      {operators && operators.count > 0 && (
        <DarkCard
          title={`${operators.count} operadores ativos`}
          subtitle={`Trabalharam nos últimos ${Math.round(operators.window_days / 30)} meses · regra usada pelo planeador e pelos dropdowns`}
        >
          <div className="flex flex-wrap gap-2">
            {topAreas.map((a) => (
              <span
                key={a.area}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 text-xs text-slate-300"
                title={`${a.ops} operadores ativos com trabalho recente em ${a.area}`}
              >
                <span className="font-semibold text-white">{a.ops}</span>
                {a.area}
              </span>
            ))}
            {(operators.by_area.length > topAreas.length) && (
              <span className="inline-flex items-center px-2.5 py-1 rounded-lg bg-slate-800/50 text-xs text-slate-400">
                +{operators.by_area.length - topAreas.length} áreas
              </span>
            )}
          </div>
          <p className="mt-2 text-[11px] text-text-dark-secondary">
            Uma pessoa conta em várias áreas (polivalência) — a soma por área é maior que o total.
          </p>
        </DarkCard>
      )}

      {/* Cabeçalho explicativo */}
      <div className="flex items-start gap-3 bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
        <Info size={16} className="text-accent flex-shrink-0 mt-0.5" />
        <div className="text-xs text-text-dark-secondary leading-relaxed">
          Nível <strong>independente por sector</strong> (3.0 = melhor, 1.0 = em formação).
          A coluna <em>Nível</em> é editável — o valor manual sobrepõe-se ao derivado do
          histórico real. A ordem da lista é a <strong>preferência</strong> do sector
          (nível, depois experiência e recência). O planeador (CPO) usa esta ordem ao
          escolher quem faz cada operação, sempre dentro de quem é apto.
        </div>
      </div>

      {/* Selector de sector */}
      {sectorsQuery.isLoading ? (
        <SkeletonLoader className="h-10" />
      ) : sectorsQuery.isError ? (
        <EmptyState
          mascot={false}
          icon={<AlertTriangle size={28} />}
          title="Erro a carregar sectores"
          hint="Verifica a ligação à API (/v1/workforce/sectors)."
        />
      ) : (
        <div className="flex flex-wrap gap-2">
          {sectors.map((s) => (
            <button
              key={s}
              onClick={() => { setSector(s); setOpenEmployee(null); }}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                activeSector === s
                  ? 'bg-accent text-white'
                  : 'bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Ranking do sector activo */}
      {activeSector && (
        <DarkCard
          title={`Ranking — ${activeSector}`}
          subtitle={
            rankingQuery.data
              ? `${rankingQuery.data.total} colaborador(es) apto(s)`
              : undefined
          }
        >
          {rankingQuery.isLoading ? (
            <SkeletonLoader className="h-48" />
          ) : rankingQuery.isError ? (
            <EmptyState
              mascot={false}
              icon={<AlertTriangle size={28} />}
              title="Erro a carregar o ranking"
              hint="Tenta outro sector ou verifica a API."
            />
          ) : !rankingQuery.data || rankingQuery.data.ranking.length === 0 ? (
            <EmptyState
              title="Sem histórico neste sector"
              hint="Nenhum colaborador trabalhou ainda neste sector — nada a ordenar."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-text-dark-tertiary border-b border-slate-700/50">
                    <th className="py-2 pr-2 w-10">#</th>
                    <th className="py-2 pr-2">Colaborador</th>
                    <th className="py-2 pr-2 w-44">Nível</th>
                    <th className="py-2 pr-2 w-24">Origem</th>
                    <th className="py-2 pr-2 text-right w-20">Ops</th>
                    <th className="py-2 pr-2 text-right w-20">Defeitos</th>
                    <th className="py-2 pr-2 text-right w-24">Recência</th>
                  </tr>
                </thead>
                <tbody>
                  {rankingQuery.data.ranking.map((row: SectorRankingRow) => (
                    <tr
                      key={row.employee_id}
                      className="border-b border-slate-800/60 hover:bg-slate-800/30"
                    >
                      <td className="py-2 pr-2 text-text-dark-tertiary">{row.rank}</td>
                      <td className="py-2 pr-2">
                        <button
                          onClick={() =>
                            setOpenEmployee(
                              openEmployee === row.employee_id ? null : row.employee_id,
                            )
                          }
                          className="flex items-center gap-1 text-white hover:text-accent transition-colors"
                        >
                          <ChevronRight
                            size={13}
                            className={`transition-transform ${
                              openEmployee === row.employee_id ? 'rotate-90' : ''
                            }`}
                          />
                          {row.employee_name ?? row.employee_code}
                        </button>
                        {openEmployee === row.employee_id && (
                          <EmployeeSectorBreakdown
                            employeeId={row.employee_id}
                            onSetLevel={(area, nivel) =>
                              setLevel.mutate({ employeeId: row.employee_id, areaGroup: area, nivel })
                            }
                            saving={setLevel.isPending}
                          />
                        )}
                      </td>
                      <td className="py-2 pr-2">
                        <DarkSelect
                          options={LEVEL_OPTIONS}
                          value={
                            row.effective_level != null ? row.effective_level.toFixed(1) : ''
                          }
                          placeholder="Atribuir…"
                          disabled={setLevel.isPending}
                          onChange={(e) =>
                            setLevel.mutate({
                              employeeId: row.employee_id,
                              areaGroup: activeSector,
                              nivel: parseFloat(e.target.value),
                            })
                          }
                        />
                      </td>
                      <td className="py-2 pr-2">{sourceBadge(row.source)}</td>
                      <td className="py-2 pr-2 text-right text-text-dark-secondary">
                        {row.ops_total}
                      </td>
                      <td className="py-2 pr-2 text-right text-text-dark-secondary">
                        {row.defects}
                      </td>
                      <td className="py-2 pr-2 text-right text-text-dark-secondary">
                        {row.recency_days != null ? `${row.recency_days}d` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DarkCard>
      )}
    </div>
  );
}

/** Os 7 níveis por sector de um colaborador — mostra a independência por sector. */
function EmployeeSectorBreakdown({
  employeeId,
  onSetLevel,
  saving,
}: {
  employeeId: string;
  onSetLevel: (areaGroup: string, nivel: number) => void;
  saving: boolean;
}) {
  const { data, isLoading, isError } = useQuery({
    queryKey: sectorKeys.employeeLevels(employeeId),
    queryFn: () => workforceApi.getEmployeeSectorLevels(employeeId),
  });

  if (isLoading) return <SkeletonLoader className="h-24 mt-2" />;
  if (isError || !data)
    return (
      <p className="mt-2 text-xs text-amber-400">Erro a carregar níveis por sector.</p>
    );

  return (
    <div className="mt-2 ml-4 grid grid-cols-2 gap-1.5 rounded-lg bg-slate-900/50 p-3">
      {data.sectors.map((s) => (
        <div
          key={s.area_group}
          className={`flex items-center justify-between gap-2 rounded px-2 py-1 ${
            s.apt ? 'bg-slate-800/60' : 'opacity-50'
          }`}
        >
          <span className="text-xs text-text-dark-secondary">{s.area_group}</span>
          {s.apt ? (
            <div className="flex items-center gap-2">
              <span className="text-xs text-white tabular-nums">
                {levelText(s.effective_level)}
              </span>
              {sourceBadge(s.source)}
              <DarkSelect
                options={LEVEL_OPTIONS}
                value={s.effective_level != null ? s.effective_level.toFixed(1) : ''}
                placeholder="—"
                disabled={saving}
                onChange={(e) => onSetLevel(s.area_group, parseFloat(e.target.value))}
              />
            </div>
          ) : (
            <span className="text-xs text-text-dark-tertiary">sem experiência</span>
          )}
        </div>
      ))}
    </div>
  );
}

export default EquipaNiveisTab;
