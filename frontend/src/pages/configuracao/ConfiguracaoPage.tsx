/**
 * ConfiguracaoPage — reconstrução fiel do design NELO (page-configuracao.jsx).
 *
 * 12 tabs top-level: aprendizagem · custos · scheduling · routing · cura ·
 * moldes · alertas · trust · sistema · governança · aprovisionamento ·
 * custos-metas. Cada parâmetro mostra valor, quem definiu, quando, e botão
 * reset ao default. ZERO MOCKS — cada secção liga a um endpoint real:
 *
 *   • aprendizagem — GET /v1/governance/learning/{rules,weights}
 *   • custos       — GET /v1/core/rates/* + GET /v1/profit/energy/real (PARTIAL)
 *   • scheduling   — GET/PATCH /v1/config/planning (pesos fitness CPO)
 *   • routing      — GET/PATCH /v1/config/planning (queue/buffer)
 *   • cura         — GET/PATCH /v1/plan/phase-gaps (16 transições)
 *   • moldes       — GET/PATCH /v1/config/mold (health weights)
 *   • alertas      — GET/PATCH /v1/config/quality (thresholds de alerta)
 *   • trust        — GET /v1/dqa/trust-index + GET/PATCH /v1/config/trust
 *   • sistema      — GET/PATCH /v1/config/system (idioma, moeda)
 *   • governança   — GET/PATCH /v1/config/governance (auto-aprovação) [Q.53.J]
 *   • aprovision.  — GET/PATCH /v1/config/supply (ROP, alertas rutura) [Q.53.J]
 *   • custos-metas — GET/PATCH /v1/config/cost (throughput, margem)    [Q.53.J]
 *
 * Respostas PARTIAL (energy/real sem sensores) → empty state honesto via
 * useHonestEmptyState. Sprint Q.52.P + Q.53.J.
 */

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings,
  Brain,
  Euro,
  CalendarClock,
  Route,
  Beaker,
  Hammer,
  Bell,
  ShieldCheck,
  Globe,
  Loader2,
  Save,
  RotateCcw,
  Target,
  Zap,
  TriangleAlert,
  Scale,
  PackageSearch,
  Coins,
} from 'lucide-react';
import {
  PageHeader,
  Tabs,
  KPIBig,
  DarkBadge,
  EmptyState,
} from '../../components/dark';
import {
  configApi,
  ratesApi,
  phaseGapsApi,
  learningApi,
  dqaApi,
  apiFetch,
  type ConfigDataType,
  type ConfigCategoryValues,
  type PhaseGap,
} from '../../lib/api';
import { useHonestEmptyState } from '../../hooks/useHonestEmptyState';
import { useToastContext } from '../../components/ToastProvider';

// ─── Tabs ───────────────────────────────────────────────────────────────────

const TAB_IDS = [
  'aprendizagem',
  'custos',
  'scheduling',
  'routing',
  'cura',
  'moldes',
  'alertas',
  'trust',
  'sistema',
  // Q.53.J — categorias de config que já existem no backend mas não tinham aba.
  'governanca',
  'aprovisionamento',
  'custos-metas',
] as const;
type TabId = (typeof TAB_IDS)[number];

function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

const TABS = [
  { id: 'aprendizagem', label: 'Aprendizagem', icon: <Brain size={13} /> },
  { id: 'custos', label: 'Custos', icon: <Euro size={13} /> },
  { id: 'scheduling', label: 'Scheduling', icon: <CalendarClock size={13} /> },
  { id: 'routing', label: 'Routing', icon: <Route size={13} /> },
  { id: 'cura', label: 'Cura/Secagem', icon: <Beaker size={13} /> },
  { id: 'moldes', label: 'Moldes', icon: <Hammer size={13} /> },
  { id: 'alertas', label: 'Alertas', icon: <Bell size={13} /> },
  { id: 'trust', label: 'Trust', icon: <ShieldCheck size={13} /> },
  { id: 'sistema', label: 'Sistema', icon: <Globe size={13} /> },
  { id: 'governanca', label: 'Governança', icon: <Scale size={13} /> },
  {
    id: 'aprovisionamento',
    label: 'Aprovisionamento',
    icon: <PackageSearch size={13} />,
  },
  { id: 'custos-metas', label: 'Metas de custo', icon: <Coins size={13} /> },
];

// ─── Card / SectionHeader (geometria do design NELO) ─────────────────────────

function ConfigCard({
  children,
  className = '',
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={className}
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 14,
        overflow: 'hidden',
      }}
    >
      {children}
    </div>
  );
}

function SectionHeader({
  icon,
  title,
  subtitle,
}: {
  icon?: React.ReactNode;
  title: string;
  subtitle?: string;
}) {
  return (
    <div className="flex items-center gap-2.5">
      {icon ? <span style={{ color: 'var(--fg-3)' }}>{icon}</span> : null}
      <div>
        <div className="text-[13px] font-semibold text-text-dark-primary">
          {title}
        </div>
        {subtitle ? (
          <div className="text-[11px] text-text-dark-tertiary mt-0.5">
            {subtitle}
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ─── Painel genérico de chaves de configuração (ConfigStore) ─────────────────
// Cada chave: valor editável + proveniência (quem/quando) + reset ao default.

interface ConfigKeyRow {
  key: string;
  label: string;
  hint: string;
  // Q.53.J — `currency` adicionado para a aba Custos (metas em €).
  dataType: Extract<ConfigDataType, 'int' | 'float' | 'bool' | 'string' | 'currency'>;
}

function parseConfigValue(row: ConfigKeyRow, raw: string): unknown {
  if (raw === '') return null;
  switch (row.dataType) {
    case 'int':
      return Number.parseInt(raw, 10);
    case 'float':
    case 'currency':
      return Number.parseFloat(raw);
    case 'bool':
      return raw === 'true' || raw === '1';
    default:
      return raw;
  }
}

function ConfigKeysPanel({
  title,
  subtitle,
  icon,
  category,
  rows,
  hint,
}: {
  title: string;
  subtitle: string;
  icon?: React.ReactNode;
  category: string;
  rows: ConfigKeyRow[];
  hint?: string;
}) {
  const queryClient = useQueryClient();
  const toast = useToastContext();

  const { data, isLoading, error } = useQuery<ConfigCategoryValues>({
    queryKey: ['config', category],
    queryFn: () => configApi.listCategory(category),
    staleTime: 60_000,
  });

  const [edits, setEdits] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!data) return;
    const next: Record<string, string> = {};
    for (const row of rows) {
      const raw = data.values[row.key];
      next[row.key] = raw == null ? '' : String(raw);
    }
    setEdits((prev) => ({ ...next, ...prev }));
  }, [data, rows]);

  const saveMutation = useMutation({
    mutationFn: (
      changes: Array<{ key: string; value: unknown; dataType: ConfigKeyRow['dataType'] }>,
    ) =>
      configApi.bulkSet(
        changes.map((c) => ({
          category,
          key: c.key,
          value: c.value,
          data_type: c.dataType,
        })),
      ),
    onSuccess: () => {
      toast.success('Configuração gravada.');
      queryClient.invalidateQueries({ queryKey: ['config', category] });
    },
    onError: (err) => toast.error(`Erro: ${(err as Error).message}`),
  });

  const resetMutation = useMutation({
    mutationFn: (key: string) => configApi.resetToDefault(category, key),
    onSuccess: () => {
      toast.success('Reset ao default aplicado.');
      queryClient.invalidateQueries({ queryKey: ['config', category] });
    },
    onError: (err) => toast.error(`Reset falhou: ${(err as Error).message}`),
  });

  const handleSave = () => {
    const changes = rows.flatMap((row) => {
      const raw = edits[row.key] ?? '';
      if (raw === '') return [];
      const parsed = parseConfigValue(row, raw);
      if (parsed === null) return [];
      if (typeof parsed === 'number' && Number.isNaN(parsed)) return [];
      if (data?.values[row.key] === parsed) return [];
      return [{ key: row.key, value: parsed, dataType: row.dataType }];
    });
    if (changes.length === 0) {
      toast.info('Nada para guardar.');
      return;
    }
    saveMutation.mutate(changes);
  };

  return (
    <ConfigCard>
      <div
        style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
      >
        <SectionHeader icon={icon} title={title} subtitle={subtitle} />
      </div>
      <div className="p-[18px]">
        {hint ? (
          <p className="text-[11px] text-text-dark-tertiary mb-4 italic leading-relaxed">
            {hint}
          </p>
        ) : null}
        {isLoading ? (
          <div className="flex items-center justify-center py-10">
            <Loader2 size={22} className="text-accent-500 animate-spin" />
          </div>
        ) : error ? (
          <p className="text-sm text-status-red py-3">
            Falha ao carregar: {(error as Error).message}
          </p>
        ) : (
          <>
            <div className="space-y-3.5">
              {rows.map((row) => {
                const current = data?.values[row.key];
                const defaultRender =
                  current === undefined || current === null
                    ? '—'
                    : String(current);
                return (
                  <div
                    key={row.key}
                    className="grid grid-cols-[1fr_140px_90px] items-center gap-3 py-1"
                  >
                    <div>
                      <div className="text-[12.5px] text-text-dark-primary">
                        {row.label}
                      </div>
                      <div className="text-[10.5px] text-text-dark-tertiary mt-0.5">
                        {row.hint} · actual{' '}
                        <span className="tabular-nums text-text-dark-secondary">
                          {defaultRender}
                        </span>
                      </div>
                    </div>
                    <input
                      type={
                        row.dataType === 'bool' || row.dataType === 'string'
                          ? 'text'
                          : 'number'
                      }
                      value={edits[row.key] ?? ''}
                      placeholder={
                        row.dataType === 'bool' ? 'true | false' : '—'
                      }
                      onChange={(e) =>
                        setEdits((s) => ({ ...s, [row.key]: e.target.value }))
                      }
                      className="w-full px-2.5 py-1.5 rounded-md text-[12px] tabular-nums bg-white text-slate-900 placeholder:text-slate-400 border border-bd-2 focus:outline-none focus:border-accent-500"
                    />
                    <button
                      type="button"
                      onClick={() => resetMutation.mutate(row.key)}
                      disabled={resetMutation.isPending}
                      className="inline-flex items-center justify-center gap-1 px-2 py-1.5 rounded-md text-[11px] text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary disabled:opacity-50 transition-colors"
                    >
                      <RotateCcw size={11} />
                      Reset
                    </button>
                  </div>
                );
              })}
            </div>
            <div className="flex justify-end pt-4">
              <button
                type="button"
                onClick={handleSave}
                disabled={saveMutation.isPending}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-[12px] font-medium disabled:opacity-50 transition-colors"
              >
                {saveMutation.isPending ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <Save size={13} />
                )}
                Guardar
              </button>
            </div>
            <p className="text-[10.5px] text-text-dark-tertiary mt-3">
              Cada chave grava um audit row em{' '}
              <code>tenant_configuration.{category}.*</code> (quem · quando ·
              valor anterior). O Reset repõe o default seeded.
            </p>
          </>
        )}
      </div>
    </ConfigCard>
  );
}

// ═══ Tab Aprendizagem ════════════════════════════════════════════════════════

function AprendizagemTab() {
  const rulesQ = useQuery({
    queryKey: ['config-learning', 'rules'],
    queryFn: () => learningApi.rules(),
    staleTime: 60_000,
    retry: false,
  });
  const weightsQ = useQuery({
    queryKey: ['config-learning', 'weights'],
    queryFn: () => learningApi.weights(),
    staleTime: 60_000,
    retry: false,
  });

  const rules = rulesQ.data;
  const weights = weightsQ.data;

  const confirmed = rules?.by_status?.confirmed ?? 0;
  const detected = rules?.by_status?.detected ?? 0;
  const rejected = rules?.by_status?.rejected ?? 0;
  const totalRules = confirmed + detected + rejected;
  const rejectionRate = totalRules > 0 ? (rejected / totalRules) * 100 : 0;

  const weightRows = useMemo(() => {
    if (!weights?.current_weights) return [];
    return Object.entries(weights.current_weights).map(([key, learned]) => ({
      key: key.replace(/^w_/, ''),
      learned,
      def: weights.default_weights?.[key] ?? 0,
    }));
  }, [weights]);

  return (
    <div className="space-y-3.5">
      <div className="grid grid-cols-4 gap-3">
        <KPIBig
          label="Regras confirmadas"
          value={confirmed}
          status="accent"
          accent="accent"
        />
        <KPIBig label="Em revisão" value={detected} status="yellow" accent="yellow" />
        <KPIBig label="Rejeitadas" value={rejected} status="gray" />
        <KPIBig
          label="Taxa de rejeição"
          value={Math.round(rejectionRate)}
          unit="%"
          context="das regras aprendidas alguma vez detectadas"
          status={rejectionRate < 20 ? 'green' : 'orange'}
        />
      </div>

      <ConfigCard>
        <div
          style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
        >
          <SectionHeader
            icon={<Target size={14} />}
            title="Pesos da fitness · aprendidos vs default"
            subtitle="Como o CPO pondera cada objectivo — ajustado pelas decisões reais"
          />
        </div>
        <div className="p-[18px]">
          {weightsQ.isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={20} className="text-accent-500 animate-spin" />
            </div>
          ) : weightRows.length === 0 ? (
            <EmptyState
              title="Sem pesos aprendidos"
              hint={
                weights?.reason ??
                'Quando o sistema observar decisões suficientes, ajusta os pesos automaticamente. Até lá, usa os defaults NELO.'
              }
            />
          ) : (
            <div className="flex flex-col gap-3">
              {weightRows.map((w) => {
                const diff = w.learned - w.def;
                return (
                  <div key={w.key}>
                    <div className="flex justify-between items-baseline mb-1.5">
                      <span className="text-[12px] text-text-dark-secondary capitalize">
                        {w.key}
                      </span>
                      <span className="tabular-nums text-[11px] text-text-dark-tertiary">
                        default{' '}
                        <span className="text-text-dark-secondary">
                          {w.def.toFixed(2)}
                        </span>{' '}
                        → aprendido{' '}
                        <span
                          className="font-semibold"
                          style={{
                            color:
                              diff > 0.001
                                ? 'var(--green)'
                                : diff < -0.001
                                  ? 'var(--red)'
                                  : 'var(--fg-1)',
                          }}
                        >
                          {w.learned.toFixed(2)}
                        </span>
                      </span>
                    </div>
                    <div
                      style={{
                        position: 'relative',
                        height: 5,
                        background: 'var(--bd-1)',
                        borderRadius: 3,
                      }}
                    >
                      <div
                        style={{
                          position: 'absolute',
                          inset: '0 auto 0 0',
                          width: `${Math.min(100, w.def * 250)}%`,
                          background: 'var(--bd-3)',
                          borderRadius: 3,
                        }}
                      />
                      <div
                        style={{
                          position: 'absolute',
                          inset: '0 auto 0 0',
                          width: `${Math.min(100, w.learned * 250)}%`,
                          background: 'var(--accent)',
                          borderRadius: 3,
                          opacity: 0.85,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
              <p className="text-[10.5px] text-text-dark-tertiary mt-1">
                Treinado com{' '}
                <span className="text-text-dark-secondary">
                  {weights?.pairs_used ?? 0}
                </span>{' '}
                pares ·{' '}
                {weights?.trained_at
                  ? new Date(weights.trained_at).toLocaleString('pt-PT')
                  : 'nunca treinado'}{' '}
                · gerir promote/rollback de adapters em Aprendi → Camadas.
              </p>
            </div>
          )}
        </div>
      </ConfigCard>
    </div>
  );
}

// ═══ Tab Custos ══════════════════════════════════════════════════════════════

interface RateRow {
  id?: string;
  phase_code?: string;
  phase?: string;
  machine_code?: string;
  category?: string;
  rate_per_hour?: number;
  cost_per_hour?: number;
  hourly_rate?: number;
  amount?: number;
  effective_date?: string;
  updated_at?: string;
}

interface EnergyRealRow {
  phase?: string;
  phase_code?: string;
  std_kwh?: number;
  real_kwh?: number;
  std_eur?: number;
  real_eur?: number;
  kwh_standard?: number;
  kwh_real?: number;
}

function rateValue(r: RateRow): number | null {
  const v = r.rate_per_hour ?? r.cost_per_hour ?? r.hourly_rate ?? r.amount;
  return typeof v === 'number' ? v : null;
}

function unwrapList<T>(d: unknown): T[] {
  if (Array.isArray(d)) return d as T[];
  if (d && typeof d === 'object') {
    const o = d as Record<string, unknown>;
    if (Array.isArray(o.items)) return o.items as T[];
    if (Array.isArray(o.data)) return o.data as T[];
    if (Array.isArray(o.rates)) return o.rates as T[];
  }
  return [];
}

function CustosTab() {
  const laborQ = useQuery({
    queryKey: ['rates', 'labor'],
    queryFn: () => ratesApi.laborRates.list(),
    staleTime: 60_000,
    retry: false,
  });
  const machineQ = useQuery({
    queryKey: ['rates', 'machine'],
    queryFn: () => ratesApi.machineRates.list(),
    staleTime: 60_000,
    retry: false,
  });
  const overheadQ = useQuery({
    queryKey: ['rates', 'overhead'],
    queryFn: () => ratesApi.overheadRates.list(),
    staleTime: 60_000,
    retry: false,
  });
  const energyQ = useQuery({
    queryKey: ['profit', 'energy-real'],
    queryFn: () => apiFetch<unknown>('/v1/profit/energy/real'),
    staleTime: 60_000,
    retry: false,
  });

  const honest = useHonestEmptyState(energyQ.data);
  const labor = unwrapList<RateRow>(laborQ.data);
  const machine = unwrapList<RateRow>(machineQ.data);
  const overhead = unwrapList<RateRow>(overheadQ.data);
  const energyRows = honest.degraded ? [] : unwrapList<EnergyRealRow>(energyQ.data);

  const rateGroups: Array<{ title: string; rows: RateRow[]; loading: boolean }> = [
    { title: 'Mão de obra (€/hora)', rows: labor, loading: laborQ.isLoading },
    { title: 'Máquina (€/hora)', rows: machine, loading: machineQ.isLoading },
    { title: 'Overhead', rows: overhead, loading: overheadQ.isLoading },
  ];

  return (
    <div className="space-y-3.5">
      {rateGroups.map((g) => (
        <ConfigCard key={g.title}>
          <div
            style={{
              padding: '14px 18px',
              borderBottom: '1px solid var(--bd-1)',
            }}
          >
            <SectionHeader
              icon={<Euro size={14} />}
              title={g.title}
              subtitle="core.*_rates · cada valor com data efectiva"
            />
          </div>
          <div className="p-[18px]">
            {g.loading ? (
              <div className="flex items-center justify-center py-6">
                <Loader2 size={20} className="text-accent-500 animate-spin" />
              </div>
            ) : g.rows.length === 0 ? (
              <EmptyState
                  title="Sem tarifas registadas"
                hint="Adiciona tarifas em Configuração → Dados-mestre. As tarifas alimentam o cálculo de COGS por barco."
              />
            ) : (
              <div className="space-y-1">
                {g.rows.map((r, i) => {
                  const v = rateValue(r);
                  return (
                    <div
                      key={r.id ?? i}
                      className="grid grid-cols-[1fr_120px_120px] items-center gap-3 py-2 text-[12px]"
                      style={{
                        borderBottom:
                          i < g.rows.length - 1
                            ? '1px solid var(--bd-1)'
                            : 'none',
                      }}
                    >
                      <span className="text-text-dark-secondary">
                        {r.phase ??
                          r.phase_code ??
                          r.machine_code ??
                          r.category ??
                          '—'}
                      </span>
                      <span className="tabular-nums text-text-dark-primary font-semibold text-right">
                        {v !== null ? `€${v.toFixed(2)}` : '—'}
                      </span>
                      <span className="text-text-dark-tertiary text-[10.5px] text-right">
                        {r.effective_date ?? r.updated_at ?? ''}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </ConfigCard>
      ))}

      <ConfigCard>
        <div
          style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
        >
          <SectionHeader
            icon={<Zap size={14} />}
            title="Energia real vs standard"
            subtitle="IOT_SENSOR_DATA · potência trifásica por fase"
          />
        </div>
        <div className="p-[18px]">
          {energyQ.isLoading ? (
            <div className="flex items-center justify-center py-6">
              <Loader2 size={20} className="text-accent-500 animate-spin" />
            </div>
          ) : honest.degraded ? (
            <EmptyState
              title="Sem leituras de energia"
              hint={honest.reason}
            />
          ) : energyRows.length === 0 ? (
            <EmptyState
              title="Sem dados de energia"
              hint="O endpoint /v1/profit/energy/real ainda não devolveu leituras para este período."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse min-w-[560px]">
                <thead>
                  <tr>
                    {['Fase', 'kWh standard', 'kWh real', 'Δ kWh'].map((h) => (
                      <th
                        key={h}
                        className="text-[10.5px] uppercase tracking-wide font-semibold text-text-dark-tertiary py-2 px-2.5"
                        style={{
                          textAlign: h === 'Fase' ? 'left' : 'right',
                          borderBottom: '1px solid var(--bd-1)',
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {energyRows.map((r, i) => {
                    const std = r.std_kwh ?? r.kwh_standard ?? 0;
                    const real = r.real_kwh ?? r.kwh_real ?? 0;
                    const d = real - std;
                    return (
                      <tr
                        key={i}
                        style={{
                          borderBottom:
                            i < energyRows.length - 1
                              ? '1px solid var(--bd-1)'
                              : 'none',
                        }}
                      >
                        <td className="py-2 px-2.5 text-[12px] text-text-dark-secondary">
                          {r.phase ?? r.phase_code ?? '—'}
                        </td>
                        <td className="py-2 px-2.5 text-[12px] tabular-nums text-text-dark-tertiary text-right">
                          {std}
                        </td>
                        <td className="py-2 px-2.5 text-[12px] tabular-nums text-text-dark-primary text-right">
                          {real}
                        </td>
                        <td
                          className="py-2 px-2.5 text-[12px] tabular-nums text-right font-semibold"
                          style={{
                            color: d > 0 ? 'var(--red)' : 'var(--green)',
                          }}
                        >
                          {d > 0 ? '+' : ''}
                          {d}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </ConfigCard>
    </div>
  );
}

// ═══ Tab Cura/Secagem ════════════════════════════════════════════════════════

function CuraTab() {
  const queryClient = useQueryClient();
  const toast = useToastContext();
  const { data, isLoading, error } = useQuery({
    queryKey: ['phase-gaps'],
    queryFn: () => phaseGapsApi.list(),
    staleTime: 60_000,
  });

  const gaps: PhaseGap[] = data?.items ?? [];
  const [edits, setEdits] = useState<Record<string, string>>({});

  const keyOf = (g: PhaseGap) => `${g.from_phase_code}→${g.to_phase_code}`;

  const updateMutation = useMutation({
    mutationFn: (payload: {
      from: string;
      to: string;
      min_gap_hours: number;
      reason: string;
    }) =>
      phaseGapsApi.update(payload.from, payload.to, {
        min_gap_hours: payload.min_gap_hours,
        reason: payload.reason,
      }),
    onSuccess: () => {
      toast.success('Transição de cura actualizada.');
      queryClient.invalidateQueries({ queryKey: ['phase-gaps'] });
    },
    onError: (err) => toast.error(`Erro: ${(err as Error).message}`),
  });

  const handleSave = (g: PhaseGap) => {
    const raw = edits[keyOf(g)] ?? '';
    const parsed = Number.parseFloat(raw);
    if (raw === '' || Number.isNaN(parsed)) {
      toast.info('Indica um valor numérico válido.');
      return;
    }
    if (parsed === g.min_gap_hours) {
      toast.info('Nada para guardar.');
      return;
    }
    const reason = window.prompt(
      'Porque é que estás a alterar este tempo de cura? (mínimo 10 caracteres)',
    );
    if (!reason || reason.trim().length < 10) {
      toast.error('Razão obrigatória — mínimo 10 caracteres.');
      return;
    }
    updateMutation.mutate({
      from: g.from_phase_code,
      to: g.to_phase_code,
      min_gap_hours: parsed,
      reason: reason.trim(),
    });
  };

  return (
    <ConfigCard>
      <div
        style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
      >
        <SectionHeader
          icon={<Beaker size={14} />}
          title="Cura / Secagem · transições min_gap_hours"
          subtitle="Não são filas — são química. Cura de resina e secagem de tinta têm tempos mínimos físicos."
        />
      </div>
      <div className="p-[18px]">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="text-accent-500 animate-spin" />
          </div>
        ) : error ? (
          <p className="text-sm text-status-red py-3">
            Falha ao carregar: {(error as Error).message}
          </p>
        ) : gaps.length === 0 ? (
          <EmptyState
            title="Sem transições de cura"
            hint="O seed NELO_CURING_GAPS_SEED tem 16 transições. Se a lista está vazia, corre o bootstrap."
          />
        ) : (
          <div className="space-y-2">
            {gaps.map((g) => (
              <div
                key={keyOf(g)}
                className="grid grid-cols-[1fr_120px_90px_90px] items-center gap-3 py-2"
                style={{ borderBottom: '1px solid var(--bd-1)' }}
              >
                <div>
                  <div className="text-[12.5px] text-text-dark-primary">
                    {g.from_phase_code} → {g.to_phase_code}
                  </div>
                  <div className="text-[10.5px] text-text-dark-tertiary mt-0.5">
                    {g.reason ?? 'sem nota'} ·{' '}
                    {g.n_observations != null
                      ? `${g.n_observations} obs.`
                      : 'seed'}
                  </div>
                </div>
                <input
                  type="number"
                  step="0.5"
                  defaultValue={g.min_gap_hours}
                  onChange={(e) =>
                    setEdits((s) => ({ ...s, [keyOf(g)]: e.target.value }))
                  }
                  className="w-full px-2.5 py-1.5 rounded-md text-[12px] tabular-nums bg-white text-slate-900 placeholder:text-slate-400 border border-bd-2 focus:outline-none focus:border-accent-500"
                />
                <DarkBadge
                  variant={g.source === 'db' ? 'accent' : 'neutral'}
                  size="sm"
                >
                  {g.source === 'db' ? 'editado' : 'seed'}
                </DarkBadge>
                <button
                  type="button"
                  onClick={() => handleSave(g)}
                  disabled={updateMutation.isPending}
                  className="inline-flex items-center justify-center gap-1 px-2 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-[11px] font-medium disabled:opacity-50 transition-colors"
                >
                  <Save size={11} />
                  Guardar
                </button>
              </div>
            ))}
            <p className="text-[10.5px] text-text-dark-tertiary mt-2">
              Cada alteração exige razão ≥10 caracteres e grava audit. O CPO
              apanha o novo valor no próximo <code>/v1/plan/cpo/schedule</code>.
            </p>
          </div>
        )}
      </div>
    </ConfigCard>
  );
}

// ═══ Tab Trust ═══════════════════════════════════════════════════════════════

function TrustTab() {
  const trustQ = useQuery({
    queryKey: ['dqa', 'trust-index', 'global'],
    queryFn: () => dqaApi.trustIndex(),
    staleTime: 60_000,
    retry: false,
  });

  const ti = trustQ.data as
    | {
        trust_index?: number;
        score?: number;
        grade?: string;
        components?: Record<string, number>;
        component_scores?: Record<string, number>;
      }
    | undefined;
  const score = ti?.trust_index ?? ti?.score ?? null;
  const components = ti?.components ?? ti?.component_scores ?? {};

  return (
    <div className="space-y-3.5">
      <div className="grid grid-cols-3 gap-3">
        <KPIBig
          label="Trust Index global"
          value={score != null ? Math.round(score * 100) : '—'}
          unit={score != null ? '%' : undefined}
          context="confiança nos dados que alimentam o solver"
          status={
            score == null
              ? 'gray'
              : score >= 0.75
                ? 'green'
                : score >= 0.6
                  ? 'yellow'
                  : 'red'
          }
        />
        <KPIBig
          label="Grade"
          value={ti?.grade ?? '—'}
          status="accent"
        />
        <KPIBig
          label="Componentes"
          value={Object.keys(components).length}
          context="7 componentes ponderados (C/V/F/K/P/A/E)"
          status="gray"
        />
      </div>

      <ConfigCard>
        <div
          style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
        >
          <SectionHeader
            icon={<ShieldCheck size={14} />}
            title="Componentes do Trust Index"
            subtitle="GET /v1/dqa/trust-index — score por componente"
          />
        </div>
        <div className="p-[18px]">
          {trustQ.isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={20} className="text-accent-500 animate-spin" />
            </div>
          ) : Object.keys(components).length === 0 ? (
            <EmptyState
              title="Sem componentes de trust"
              hint="O Trust Index v2 calcula 7 componentes. Se a lista está vazia, o snapshot ainda não correu."
            />
          ) : (
            <div className="flex flex-col gap-2.5">
              {Object.entries(components).map(([name, val]) => (
                <div key={name}>
                  <div className="flex justify-between text-[12px] mb-1">
                    <span className="text-text-dark-secondary capitalize">
                      {name}
                    </span>
                    <span className="tabular-nums text-text-dark-primary font-semibold">
                      {Math.round(val * 100)}%
                    </span>
                  </div>
                  <div
                    style={{
                      height: 5,
                      background: 'var(--bd-1)',
                      borderRadius: 3,
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min(100, val * 100)}%`,
                        height: '100%',
                        background:
                          val >= 0.75
                            ? 'var(--green)'
                            : val >= 0.6
                              ? 'var(--yellow)'
                              : 'var(--red)',
                        borderRadius: 3,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </ConfigCard>

      <ConfigKeysPanel
        title="Pesos e gates do Trust Index"
        subtitle="Blueprint v2.0 §4.5 · 7 componentes + 5 gates"
        icon={<ShieldCheck size={14} />}
        category="trust"
        rows={TRUST_KEYS}
        hint="Componentes (peso): C/V/F/K/P/A/E somam 1.0. Gates: 0.50 (solver-only), 0.60 (P90), 0.70 (auto-reorder), 0.75 (auto-commit), 0.80 (quality disposition)."
      />
    </div>
  );
}

// ─── Conjuntos de chaves de configuração (ConfigStore) ───────────────────────

const SCHEDULING_KEYS: ConfigKeyRow[] = [
  {
    key: 'fitness.weight.makespan',
    label: 'Peso fitness — makespan',
    hint: 'Default 0.20 — mede o tempo total do horizonte',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.tardiness_transport',
    label: 'Peso fitness — tardiness transporte',
    hint: 'Default 0.25 — datas de transporte são king (PL14)',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.idle_operators',
    label: 'Peso fitness — idle operadores',
    hint: 'Default 0.15 — penaliza operadores parados',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.setup_time',
    label: 'Peso fitness — setup time',
    hint: 'Default 0.15 — tempo de troca de molde/cor',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.quality_risk',
    label: 'Peso fitness — quality risk',
    hint: 'Default 0.10 — mean P(erro) das operações',
    dataType: 'float',
  },
  {
    key: 'fitness.weight.throughput_eur_day',
    label: 'Peso fitness — throughput €/dia',
    hint: 'Default 0.15 — negativado internamente',
    dataType: 'float',
  },
  {
    key: 'cpo.total_budget_s',
    label: 'CPO budget total (s)',
    hint: 'Tempo end-to-end do cascade (Blueprint §5.5: 60s alvo)',
    dataType: 'float',
  },
  {
    key: 'cpo.gen_count',
    label: 'GA gerações',
    hint: 'Blueprint v2.0 exige 200',
    dataType: 'int',
  },
];

const ROUTING_KEYS: ConfigKeyRow[] = [
  {
    key: 'queue_time.median_h',
    label: 'Mediana queue inter-fase (h)',
    hint: 'PL22 — 5.2h mediana entre fases consecutivas',
    dataType: 'float',
  },
  {
    key: 'queue_time.p90_h',
    label: 'P90 queue inter-fase (h)',
    hint: 'PL22 — 69.2h, buffer maior quando TI < 0.60',
    dataType: 'float',
  },
  {
    key: 'buffer.post_desmolde_h',
    label: 'Buffer pós-Desmolde (h)',
    hint: 'PL21 — 4h, Desmolde é o ponto QC de facto',
    dataType: 'float',
  },
  {
    key: 'laminagem.require_pair',
    label: 'Laminagem exige par',
    hint: 'WF11 — 88.5% histórico. true=obrigatório',
    dataType: 'bool',
  },
  {
    key: 'laminagem.require_chefe',
    label: 'Par obrigatoriamente com chefe',
    hint: 'true=par tem de incluir um senior',
    dataType: 'bool',
  },
];

const MOLD_KEYS: ConfigKeyRow[] = [
  {
    key: 'maintenance_threshold_cycles',
    label: 'Threshold manutenção (ciclos)',
    hint: 'H2 — pending CEO. ≤0 desliga MOLD_MAINT_DUE',
    dataType: 'int',
  },
  {
    key: 'health_weight.cycles',
    label: 'Peso health — ciclos',
    hint: 'Default 0.40 — soma com os outros pesos = 1.0',
    dataType: 'float',
  },
  {
    key: 'health_weight.defects_90d',
    label: 'Peso health — defeitos 90d',
    hint: 'Default 0.20',
    dataType: 'float',
  },
  {
    key: 'health_weight.days_since_maint',
    label: 'Peso health — dias desde manutenção',
    hint: 'Default 0.20',
    dataType: 'float',
  },
  {
    key: 'health_weight.rework_rate',
    label: 'Peso health — taxa de retrabalho',
    hint: 'Default 0.20',
    dataType: 'float',
  },
  {
    key: 'health.red_threshold',
    label: 'Health score → vermelho',
    hint: 'Default 40 — abaixo bloqueia uso do molde',
    dataType: 'int',
  },
  {
    key: 'health.yellow_threshold',
    label: 'Health score → amarelo',
    hint: 'Default 70',
    dataType: 'int',
  },
];

const ALERTAS_KEYS: ConfigKeyRow[] = [
  {
    key: 'risk_alert_threshold',
    label: 'Threshold P(erro) para alerta',
    hint: 'QA07 — alerta preventivo quando P(erro) > threshold. Default 0.40',
    dataType: 'float',
  },
  {
    key: 'rework_buffer_pct.sanding_water',
    label: 'Buffer Lixagem água (%)',
    hint: 'QA11 — 20% (taxa real 49.2%)',
    dataType: 'float',
  },
  {
    key: 'rework_buffer_pct.sanding_polish',
    label: 'Buffer Lixagem polimento (%)',
    hint: 'QA11 — 20% (taxa real 41.3%)',
    dataType: 'float',
  },
  {
    key: 'rework_buffer_pct.painting_finishing',
    label: 'Buffer Pintura Acabamento (%)',
    hint: 'QA11 — 18% (taxa real 42.4%)',
    dataType: 'float',
  },
  {
    key: 'skill_bottleneck_threshold',
    label: 'Skill bottleneck (workers aptos)',
    hint: 'WF12 — fases com < N workers aptos viram bottleneck',
    dataType: 'int',
  },
];

const TRUST_KEYS: ConfigKeyRow[] = [
  { key: 'weights.completeness', label: 'Peso C — Completeness', hint: 'Default 0.15', dataType: 'float' },
  { key: 'weights.validity', label: 'Peso V — Validity', hint: 'Default 0.20', dataType: 'float' },
  { key: 'weights.freshness', label: 'Peso F — Freshness', hint: 'Default 0.15', dataType: 'float' },
  { key: 'weights.consistency', label: 'Peso K — Consistency', hint: 'Default 0.20', dataType: 'float' },
  { key: 'weights.provenance', label: 'Peso P — Provenance', hint: 'Default 0.15', dataType: 'float' },
  { key: 'weights.anomaly', label: 'Peso A — Anomaly', hint: 'Default 0.10', dataType: 'float' },
  { key: 'weights.evidence', label: 'Peso E — Evidence', hint: 'Default 0.05', dataType: 'float' },
  { key: 'gates.auto_commit', label: 'Gate 4 — auto-commit', hint: 'TI<0.75 → human approval', dataType: 'float' },
  { key: 'gates.quality_disposition', label: 'Gate 5 — quality disposition', hint: 'TI<0.80 → quality moves bloqueados', dataType: 'float' },
];

const SYSTEM_KEYS: ConfigKeyRow[] = [
  {
    key: 'language',
    label: 'Idioma da interface',
    hint: 'pt-PT canónico. en-US/de-DE diferidos',
    dataType: 'string',
  },
  {
    key: 'format.currency',
    label: 'Moeda de apresentação',
    hint: 'EUR — afecta a formatação de valores',
    dataType: 'string',
  },
  {
    key: 'theme',
    label: 'Tema visual',
    hint: 'dark — tema único de produção',
    dataType: 'string',
  },
];

// ═══ Q.53.J — categorias de config governance / supply / cost ════════════════
// As linhas mapeiam 1:1 os seeds de src/core/services/default_configs.py.

const GOVERNANCA_KEYS: ConfigKeyRow[] = [
  {
    key: 'auto_approval.reschedule_order.enabled',
    label: 'Auto-aprovar reagendamentos',
    hint: 'WG07 — auto-aprova mudanças de plano baratas de risco baixo',
    dataType: 'bool',
  },
  {
    key: 'auto_approval.reschedule_order.risk_ceiling',
    label: 'Tecto de risco — reagendamento',
    hint: 'Só decisões até este nível auto-aprovam (LOW/MEDIUM/HIGH)',
    dataType: 'string',
  },
  {
    key: 'auto_approval.stock_adjustment.enabled',
    label: 'Auto-aprovar ajustes de stock',
    hint: 'Auto-aprova ajustes de stock dentro do tecto de risco',
    dataType: 'bool',
  },
  {
    key: 'auto_approval.stock_adjustment.risk_ceiling',
    label: 'Tecto de risco — ajuste de stock',
    hint: 'Nível máximo que auto-aprova ajustes de stock',
    dataType: 'string',
  },
  {
    key: 'auto_approval.model_promotion.enabled',
    label: 'Auto-aprovar promoção de modelos ML',
    hint: 'Auto-aprova a promoção de modelos ML de risco baixo',
    dataType: 'bool',
  },
  {
    key: 'auto_approval.model_promotion.risk_ceiling',
    label: 'Tecto de risco — promoção de modelos',
    hint: 'Nível máximo que auto-aprova promoção de modelos',
    dataType: 'string',
  },
  {
    key: 'timeline.hide_low_risk_default',
    label: 'Esconder risco baixo por defeito',
    hint: 'WG08 — anti-fadiga: esconde decisões LOW na timeline',
    dataType: 'bool',
  },
  {
    key: 'timeline.max_per_user_shown',
    label: 'Máx. itens por revisor',
    hint: 'WG08 — limita itens visíveis por revisor para evitar sobrecarga',
    dataType: 'int',
  },
];

const APROVISIONAMENTO_KEYS: ConfigKeyRow[] = [
  {
    key: 'safety_multiplier',
    label: 'Multiplicador de segurança',
    hint: 'MR05 — multiplicador sobre os pontos de encomenda calculados',
    dataType: 'float',
  },
  {
    key: 'stockout_critical_days',
    label: 'Dias críticos até rutura',
    hint: 'Abaixo deste nº de dias dispara MATERIAL_STOCKOUT_IMMINENT',
    dataType: 'int',
  },
  {
    key: 'adjust.auto_approve_threshold_qty',
    label: 'Limite de ajuste sem aprovação',
    hint: '|qty_delta| acima exige aprovação de governança (MR06/ST01)',
    dataType: 'float',
  },
];

const CUSTOS_METAS_KEYS: ConfigKeyRow[] = [
  {
    key: 'target.throughput_eur_day_min',
    label: 'Meta mínima de throughput/dia',
    hint: 'CS05 — Blueprint v2.0 §2.8 alvo €30K/dia',
    dataType: 'currency',
  },
  {
    key: 'target.throughput_eur_day_max',
    label: 'Meta máxima de throughput/dia',
    hint: 'Topo da banda de meta diária (€35K/dia)',
    dataType: 'currency',
  },
  {
    key: 'margin_default',
    label: 'Margem por defeito',
    hint: 'Margem fallback quando ProductPricing.sale_value falta (ex: 1.40)',
    dataType: 'float',
  },
  {
    key: 'target.unit_value_eur',
    label: 'Valor por encomenda',
    hint: 'Q.8 — €/encomenda para estimativas de backlog (€35K ÷ 14.9 barcos)',
    dataType: 'currency',
  },
];

// ═══ Página ══════════════════════════════════════════════════════════════════

export default function ConfiguracaoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'aprendizagem';

  const handleTabChange = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', id);
    setSearchParams(next, { replace: true });
  };

  return (
    <div>
      <PageHeader
        title="Configuração"
        subtitle="Parâmetros, regras e aprendizagem — cada valor com quem definiu, quando e botão reset"
        icon={<Settings size={18} />}
        helpId="definicoes"
      />

      <div className="px-6 pt-3">
        <Tabs
          tabs={TABS}
          value={activeTab}
          onChange={handleTabChange}
          sticky
        />
      </div>

      <div className="px-6 py-5 page-enter">
        {activeTab === 'aprendizagem' && <AprendizagemTab />}

        {activeTab === 'custos' && <CustosTab />}

        {activeTab === 'scheduling' && (
          <ConfigKeysPanel
            title="Scheduling / CPO"
            subtitle="Pesos da fitness do solver · Blueprint v2.0 §5.5"
            icon={<CalendarClock size={14} />}
            category="planning"
            rows={SCHEDULING_KEYS}
            hint="Os pesos definem como o CPO compara alternativas. Devem somar ≈1.0 — o motor renormaliza defensivamente. Override do gestor SEMPRE ganha sobre regras aprendidas."
          />
        )}

        {activeTab === 'routing' && (
          <ConfigKeysPanel
            title="Routing"
            subtitle="Filas inter-fase e regras de par · Plan v4 §3"
            icon={<Route size={14} />}
            category="planning"
            rows={ROUTING_KEYS}
            hint="Os tempos de fila vêm do histórico real (PL22). O par obrigatório na Laminagem é o axioma dual-resource (88.5%)."
          />
        )}

        {activeTab === 'cura' && <CuraTab />}

        {activeTab === 'moldes' && (
          <ConfigKeysPanel
            title="Moldes"
            subtitle="Health score e manutenção · Plan v4 §3.5"
            icon={<Hammer size={14} />}
            category="mold"
            rows={MOLD_KEYS}
            hint="Os pesos health_weight.* devem somar 1.0. O threshold de manutenção é H2 do plano (placeholder pending CEO)."
          />
        )}

        {activeTab === 'alertas' && (
          <ConfigKeysPanel
            title="Alertas"
            subtitle="Thresholds de risco e buffers de retrabalho · QA07/QA11"
            icon={<Bell size={14} />}
            category="quality"
            rows={ALERTAS_KEYS}
            hint="Os buffers de retrabalho espelham as taxas reais (Lixagem água 49.2%, Pintura Acab. 42.4%, Lixagem polimento 41.3%)."
          />
        )}

        {activeTab === 'trust' && <TrustTab />}

        {activeTab === 'sistema' && (
          <ConfigKeysPanel
            title="Sistema"
            subtitle="Idioma, moeda e formatos · Plan v4 §11.1"
            icon={<Globe size={14} />}
            category="system"
            rows={SYSTEM_KEYS}
            hint="O frontend usa PT-PT directamente nos componentes. Suporte i18n completo (en-US, de-DE) está diferido."
          />
        )}

        {activeTab === 'governanca' && (
          <ConfigKeysPanel
            title="Governança & auto-aprovação"
            subtitle="Quando o sistema decide sozinho vs quando pede aprovação humana"
            icon={<Scale size={14} />}
            category="governance"
            rows={GOVERNANCA_KEYS}
            hint="Os axiomas Spelke e o write-gate continuam a aplicar-se: estas chaves só controlam o que auto-aprova dentro do tecto de risco, nunca contornam o gate de aprovação humana."
          />
        )}

        {activeTab === 'aprovisionamento' && (
          <ConfigKeysPanel
            title="Aprovisionamento"
            subtitle="Pontos de encomenda, alertas de rutura e limites de ajuste de stock"
            icon={<PackageSearch size={14} />}
            category="supply"
            rows={APROVISIONAMENTO_KEYS}
            hint="Afetam o detetor de rutura e o cálculo de ROP — não tocam no stock real do ERP NELO."
          />
        )}

        {activeTab === 'custos-metas' && (
          <ConfigKeysPanel
            title="Metas de custo"
            subtitle="Metas de throughput diário, margem e valor por encomenda"
            icon={<Coins size={14} />}
            category="cost"
            rows={CUSTOS_METAS_KEYS}
            hint="A CoeficienteX é dinheiro (€) — estas metas alimentam o módulo de lucro, nunca o scheduler."
          />
        )}

        {(activeTab === 'scheduling' ||
          activeTab === 'routing' ||
          activeTab === 'moldes' ||
          activeTab === 'alertas') && (
          <div className="mt-3 flex items-start gap-2 px-1">
            <TriangleAlert size={13} className="text-status-yellow mt-0.5" />
            <p className="text-[11px] text-text-dark-tertiary leading-relaxed">
              Alterações de parâmetros do solver só entram em vigor no próximo
              ciclo de scheduling. Os 7 axiomas Spelke são imovíveis e não são
              editáveis por aqui.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
