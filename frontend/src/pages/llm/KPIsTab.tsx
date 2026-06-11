/**
 * KPIsTab — tab KPIs da LLMPage (Q.R: ligada ao Cube)
 * ===================================================
 *
 * Mostra as MEASURES REAIS do Cube (operações NELO via marts) em vez do
 * caminho legacy /v1/profit/kpis/* (quase vazio). Duas camadas:
 *
 *   • Destaques — 7 cards curados + 4 gráficos (GET /cube/dashboard-dev,
 *     determinístico, sem LLM).
 *   • Os meus indicadores — picker sobre TODAS as measures do contrato
 *     (GET /cube/measures-dev) com valores ad-hoc (POST /cube/measure-cards-dev).
 *     A selecção persiste em localStorage (preferência de UI, não estado de
 *     servidor).
 *
 * Degradação honesta: uma measure cujo mart ainda não está populado mostra
 * "sem dados" — nunca valores inventados. ZERO MOCKS.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3,
  RefreshCw,
  AlertTriangle,
  Sparkles,
  Database,
  Plus,
  X,
  Info,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkButton, DarkBadge, DarkSearchInput } from '../../components/dark';
import { LineChart, BarChart } from '../../components/charts';
import { cubeApi } from '../../lib/api';
import type {
  CubeDashboardCard,
  CubeDashboardChart,
  CubeMeasureCatalogEntry,
} from '../../lib/api';
import { cubeKeys } from '../../lib/api/keys';
import { OtdHeatmap } from './OtdHeatmap';

// ── Selecção persistida (preferência de UI, não estado de servidor) ─────────

const SELECTION_STORAGE_KEY = 'kpis.cube.selection';

function loadSelection(): string[] {
  try {
    const raw = localStorage.getItem(SELECTION_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((x): x is string => typeof x === 'string')
      : [];
  } catch {
    return [];
  }
}

function prettifyDomain(domain: string): string {
  return domain.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

// ── Formatação ────────────────────────────────────────────────────────────

function formatValue(card: CubeDashboardCard): string {
  if (card.value === null) return '—';
  const v = card.value;
  if (card.unit === '%') return `${(v * 100).toFixed(2)}%`; // ratio measure → %
  if (card.unit === '€') return `${v.toLocaleString('pt-PT', { maximumFractionDigits: 0 })} €`;
  return Number.isInteger(v)
    ? v.toLocaleString('pt-PT')
    : v.toLocaleString('pt-PT', { maximumFractionDigits: 2 });
}

const COLORS = ['#4ea7c1', '#7bb274', '#c9a72a', '#b97fc9', '#d6845a', '#5aa9d6'];

// Q.173.AL — mapa dos cards curados (backend _CARD_SPECS): key → measure canónico.
// Estático porque o conjunto curado só muda com deploy.
const DASHBOARD_CARD_MEASURE: Record<string, string> = {
  ofs_produzidas_hoje: 'producao_ofs_fechadas_dia.total',
  ofs_em_curso: 'producao_ofs_em_curso.total',
  taxa_defeitos: 'qualidade.taxa_defeitos',
  facturacao_mes: 'comercial_facturacao.total',
  consumo_custo_mes: 'consumo_material.custo',
  backlog: 'planeamento_backlog.total',
  lead_time_p50: 'producao_lead_time_of.lead_time_p50',
  ofs_expedidas_mes: 'logistica_ofs_expedidas.total',
};

// Cards curados sem período temporal: mostram "todo o histórico do espelho".
const ALL_TIME_KEYS = new Set(['taxa_defeitos', 'lead_time_p50', 'ofs_em_curso', 'backlog']);

// ── Componente principal ─────────────────────────────────────────────────

export function KPIsTab() {
  const dashQuery = useQuery({
    queryKey: cubeKeys.dashboard(),
    queryFn: () => cubeApi.dashboard(),
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });

  const [selection, setSelection] = useState<string[]>(loadSelection);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(SELECTION_STORAGE_KEY, JSON.stringify(selection));
    } catch {
      /* localStorage indisponível (modo privado) — selecção fica só em memória */
    }
  }, [selection]);

  // Catálogo das measures (estático — lê só o contrato no backend).
  const catalogQuery = useQuery({
    queryKey: cubeKeys.measures(),
    queryFn: () => cubeApi.measures(),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
  const catalog = catalogQuery.data?.measures ?? [];
  const catalogByName = useMemo(
    () => new Map(catalog.map((e) => [e.name, e])),
    [catalog],
  );

  // Self-heal: quando o catálogo carrega, descarta indicadores guardados que já
  // não existem no contrato — evita pedir uma measure desconhecida (que daria
  // 422 no backend e rebentava o painel "Os meus indicadores" inteiro).
  useEffect(() => {
    if (catalog.length === 0) return;
    setSelection((prev) => {
      const valid = prev.filter((m) => catalogByName.has(m));
      return valid.length === prev.length ? prev : valid;
    });
  }, [catalog.length, catalogByName]);

  // Período por measure: temporais (têm dim `tempo`) → último mês completo;
  // snapshot/total → agregado. Nunca mostrar o total-de-sempre como "agora".
  const requestItems = useMemo(
    () =>
      selection
        .filter((m) => catalogByName.has(m)) // nunca pedir measure fora do contrato (sem 422)
        .map((m) => ({
          measure: m,
          period: (catalogByName.get(m)?.supports_period ? 'last_month' : 'none') as
            | 'none'
            | 'last_month',
        })),
    [selection, catalogByName],
  );

  // Valores das measures escolhidas (só depois do catálogo, p/ o self-heal correr).
  const myCardsQuery = useQuery({
    queryKey: cubeKeys.measureCards(requestItems.map((i) => `${i.measure}:${i.period}`)),
    queryFn: () => cubeApi.measureCards(requestItems),
    enabled: selection.length > 0 && catalog.length > 0,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });

  const cards = dashQuery.data?.cards ?? [];
  const charts = dashQuery.data?.charts ?? [];
  const myCards = myCardsQuery.data?.cards ?? [];

  const toggleMeasure = (name: string) =>
    setSelection((prev) =>
      prev.includes(name) ? prev.filter((m) => m !== name) : [...prev, name],
    );
  const removeMeasure = (name: string) =>
    setSelection((prev) => prev.filter((m) => m !== name));

  const refreshAll = () => {
    dashQuery.refetch();
    catalogQuery.refetch();
    if (selection.length > 0) myCardsQuery.refetch();
  };
  const isFetchingAny =
    dashQuery.isFetching || myCardsQuery.isFetching || catalogQuery.isFetching;

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Sistema' }, { label: 'LLM' }, { label: 'KPIs' }]}
      title="KPIs"
      subtitle="Indicadores reais do Cube (operações NELO) · actualização a cada 60s"
      icon={<BarChart3 className="h-6 w-6" />}
      actions={
        <DarkButton
          variant="ghost"
          icon={<RefreshCw size={13} className={isFetchingAny ? 'animate-spin' : ''} />}
          onClick={refreshAll}
        >
          Actualizar
        </DarkButton>
      }
    >
      {/* Estado de erro global do dashboard */}
      {dashQuery.isError && (
        <DarkCard className="mb-5 border-danger/30 bg-danger/5">
          <div className="flex items-center gap-3">
            <AlertTriangle size={18} className="text-danger shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-fg-1">Falha ao carregar o dashboard do Cube</p>
              <p className="text-xs text-fg-3 mt-0.5">
                {(dashQuery.error as Error)?.message ?? 'Erro desconhecido'}
              </p>
            </div>
            <DarkButton variant="ghost" icon={<RefreshCw size={13} />} onClick={() => dashQuery.refetch()}>
              Tentar novamente
            </DarkButton>
          </div>
        </DarkCard>
      )}

      {/* ── Os meus indicadores (picker sobre o catálogo completo) ── */}
      <div className="flex items-center justify-between gap-3 mb-2">
        <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3">
          Os meus indicadores
        </p>
        <DarkButton
          variant="ghost"
          icon={<Plus size={13} />}
          onClick={() => setPickerOpen((v) => !v)}
        >
          Adicionar indicador
        </DarkButton>
      </div>

      {pickerOpen && (
        <MeasurePicker
          entries={catalog}
          isLoading={catalogQuery.isLoading}
          isError={catalogQuery.isError}
          selected={selection}
          onToggle={toggleMeasure}
          onClose={() => setPickerOpen(false)}
        />
      )}

      {myCardsQuery.isError && (
        <DarkCard className="mb-4 border-danger/30 bg-danger/5">
          <div className="flex items-center gap-3">
            <AlertTriangle size={18} className="text-danger shrink-0" />
            <p className="text-xs text-fg-3 flex-1 min-w-0">
              Falha ao carregar os valores escolhidos: {(myCardsQuery.error as Error)?.message ?? 'erro'}
            </p>
            <DarkButton variant="ghost" icon={<RefreshCw size={13} />} onClick={() => myCardsQuery.refetch()}>
              Tentar novamente
            </DarkButton>
          </div>
        </DarkCard>
      )}

      {selection.length === 0 ? (
        <DarkCard className="mb-7 border-dashed border-bd-2 bg-bg-1">
          <div className="flex flex-col items-center justify-center text-center gap-2 py-6">
            <BarChart3 className="h-7 w-7 text-fg-3" />
            <p className="text-sm font-medium text-fg-2">Ainda não escolheste indicadores</p>
            <p className="text-xs text-fg-3 max-w-sm leading-relaxed">
              Usa <span className="text-fg-1 font-medium">Adicionar indicador</span> para escolher
              entre {catalog.length > 0 ? catalog.length : 'os'} indicadores reais do Cube. A tua
              escolha fica guardada neste dispositivo.
            </p>
          </div>
        </DarkCard>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-7">
          {selection.map((name) => {
            const card = myCards.find((c) => c.key === name);
            const entry = catalogByName.get(name);
            const periodLabel = entry?.supports_period ? 'mês passado' : undefined;
            if (!card) {
              // Enquanto carrega: skeleton. Já carregou mas não veio (erro do
              // mart / acima do limite): card honesto, não "pulse" eterno.
              if (myCardsQuery.isLoading || myCardsQuery.isFetching) {
                return <DarkCard key={name} className="h-[92px] animate-pulse" />;
              }
              return (
                <UnavailableKpiCard
                  key={name}
                  label={entry?.label ?? name}
                  onRemove={() => removeMeasure(name)}
                />
              );
            }
            return (
              <MyKpiCard
                key={name}
                card={card}
                periodLabel={periodLabel}
                onRemove={() => removeMeasure(name)}
              />
            );
          })}
        </div>
      )}

      {/* ── Destaques (conjunto curado) ── */}
      <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-2">
        Destaques
      </p>
      {dashQuery.isLoading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-7">
          {Array.from({ length: 7 }).map((_, i) => (
            <DarkCard key={i} className="h-[92px] animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-7">
          {cards.map((card) => {
            const measureName = DASHBOARD_CARD_MEASURE[card.key];
            const catalogEntry = measureName ? catalogByName.get(measureName) : undefined;
            return (
              <KpiCard
                key={card.key}
                card={card}
                catalogEntry={catalogEntry}
                isAllTime={ALL_TIME_KEYS.has(card.key)}
              />
            );
          })}
        </div>
      )}

      {/* Gráficos */}
      <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-2">
        Gráficos
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-7">
        {dashQuery.isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <DarkCard key={i} className="h-[260px] animate-pulse" />
            ))
          : charts.map((chart, i) => <ChartCard key={chart.key} chart={chart} color={COLORS[i % COLORS.length]} />)}
      </div>

      {/* Q.118.K — mapa de calor OTD (produto × semana) */}
      <OtdHeatmap />
    </DarkPageLayout>
  );
}

// ── Picker de measures (catálogo agrupado por domínio, pesquisável) ─────────

function MeasurePicker({
  entries,
  isLoading,
  isError,
  selected,
  onToggle,
  onClose,
}: {
  entries: CubeMeasureCatalogEntry[];
  isLoading: boolean;
  isError: boolean;
  selected: string[];
  onToggle: (name: string) => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState('');
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  const groups = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = q
      ? entries.filter(
          (e) =>
            e.label.toLowerCase().includes(q) ||
            e.name.toLowerCase().includes(q) ||
            e.domain.toLowerCase().includes(q),
        )
      : entries;
    const byDomain = new Map<string, CubeMeasureCatalogEntry[]>();
    for (const e of filtered) {
      const list = byDomain.get(e.domain) ?? [];
      list.push(e);
      byDomain.set(e.domain, list);
    }
    return Array.from(byDomain.entries()); // já ordenado por domínio pela API
  }, [entries, search]);

  return (
    <DarkCard className="mb-4">
      <div className="flex items-center justify-between gap-3 mb-3">
        <DarkSearchInput
          containerClassName="flex-1"
          placeholder="Pesquisar indicador (ex: cura, faturação, defeitos)…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClear={() => setSearch('')}
          autoFocus
        />
        <DarkButton variant="ghost" icon={<X size={13} />} onClick={onClose}>
          Fechar
        </DarkButton>
      </div>

      {isError ? (
        <div className="flex items-center gap-3 py-4">
          <AlertTriangle size={18} className="text-danger shrink-0" />
          <p className="text-sm text-fg-2">Falha ao carregar o catálogo de indicadores.</p>
        </div>
      ) : isLoading ? (
        <p className="text-sm text-fg-3 py-4 text-center">A carregar catálogo…</p>
      ) : groups.length === 0 ? (
        <p className="text-sm text-fg-3 py-4 text-center">
          Nenhum indicador corresponde a “{search}”.
        </p>
      ) : (
        <div className="max-h-[360px] overflow-y-auto pr-1 space-y-4">
          {groups.map(([domain, items]) => (
            <div key={domain}>
              <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-1.5">
                {prettifyDomain(domain)} <span className="text-fg-3/70">· {items.length}</span>
              </p>
              <div className="space-y-1">
                {items.map((e) => {
                  const isSel = selectedSet.has(e.name);
                  return (
                    <button
                      key={e.name}
                      type="button"
                      onClick={() => onToggle(e.name)}
                      className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg border text-left transition-colors ${
                        isSel
                          ? 'border-accent/40 bg-accent/10'
                          : 'border-bd-1 bg-bg-1 hover:border-bd-2'
                      }`}
                    >
                      <span className="flex items-center gap-2 min-w-0">
                        <span className="text-sm text-fg-1 truncate">{e.label}</span>
                        {e.unit && <DarkBadge variant="neutral">{e.unit}</DarkBadge>}
                      </span>
                      {isSel ? (
                        <DarkBadge variant="success">Adicionado</DarkBadge>
                      ) : (
                        <Plus size={14} className="text-fg-3 shrink-0" />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </DarkCard>
  );
}

// ── Card de KPI escolhido (com remover) ─────────────────────────────────────

function MyKpiCard({
  card,
  periodLabel,
  onRemove,
}: {
  card: CubeDashboardCard;
  periodLabel?: string;
  onRemove: () => void;
}) {
  const hasData = card.status === 'ok' && card.value !== null;

  return (
    <DarkCard className="relative">
      <button
        type="button"
        title="Remover indicador"
        onClick={onRemove}
        className="absolute top-2 right-2 text-fg-3 hover:text-danger transition-colors"
      >
        <X size={13} />
      </button>
      <div className="flex items-start gap-2 mb-1 pr-5">
        <span className="text-xs font-medium text-fg-2 leading-tight">{card.label}</span>
      </div>
      <div className="flex items-baseline gap-2 mt-1.5">
        {hasData ? (
          <span className="text-2xl font-bold text-fg-0 tabular-nums">{formatValue(card)}</span>
        ) : (
          <DarkBadge variant="neutral">
            {card.status === 'error' ? 'indisponível' : 'sem dados'}
          </DarkBadge>
        )}
      </div>
      {hasData && periodLabel && (
        <span className="mt-1 block text-[10px] uppercase tracking-wide text-fg-3">
          {periodLabel}
        </span>
      )}
    </DarkCard>
  );
}

// Indicador escolhido cujo valor não veio (mart inexistente / acima do limite):
// estado honesto e removível, em vez de um skeleton que carrega para sempre.
function UnavailableKpiCard({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <DarkCard className="relative">
      <button
        type="button"
        title="Remover indicador"
        onClick={onRemove}
        className="absolute top-2 right-2 text-fg-3 hover:text-danger transition-colors"
      >
        <X size={13} />
      </button>
      <div className="flex items-start gap-2 mb-1 pr-5">
        <span className="text-xs font-medium text-fg-2 leading-tight">{label}</span>
      </div>
      <div className="flex items-baseline gap-2 mt-1.5">
        <DarkBadge variant="neutral">indisponível</DarkBadge>
      </div>
    </DarkCard>
  );
}

// ── Card de KPI (destaque curado) ───────────────────────────────────────────

function KpiCard({
  card,
  catalogEntry,
  isAllTime,
}: {
  card: CubeDashboardCard;
  catalogEntry?: CubeMeasureCatalogEntry;
  isAllTime?: boolean;
}) {
  const hasData = card.status === 'ok' && card.value !== null;
  const [tipOpen, setTipOpen] = useState(false);
  const tipRef = useRef<HTMLDivElement>(null);

  // Fecha ao clicar fora
  useEffect(() => {
    if (!tipOpen) return;
    function handleClick(e: MouseEvent) {
      if (tipRef.current && !tipRef.current.contains(e.target as Node)) {
        setTipOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [tipOpen]);

  const hasInfo = !!(catalogEntry?.sql || catalogEntry?.sql_table || isAllTime);

  return (
    <DarkCard className="relative group">
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="text-xs font-medium text-fg-2 leading-tight pr-5">{card.label}</span>
        {!hasData && <DarkBadge variant="neutral">sem dados</DarkBadge>}
      </div>
      <div className="flex items-baseline gap-1 mt-1.5">
        {hasData ? (
          <span className="text-2xl font-bold text-fg-0 tabular-nums">{formatValue(card)}</span>
        ) : (
          <span className="text-sm text-fg-3">—</span>
        )}
      </div>
      {/* Subtítulo all-time */}
      {isAllTime && hasData && (
        <span className="mt-1 block text-[10px] uppercase tracking-wide text-fg-3">
          todo o histórico do espelho
        </span>
      )}

      {/* Ícone ⓘ com tooltip de fórmula+tabela */}
      {hasInfo && (
        <div ref={tipRef} className="absolute top-2 right-2">
          <button
            type="button"
            title="Ver fórmula e fonte"
            onClick={() => setTipOpen((v) => !v)}
            className="text-fg-3 hover:text-accent transition-colors"
          >
            <Info size={13} />
          </button>
          {tipOpen && (
            <div
              className="absolute right-0 top-6 z-20 w-64 rounded-lg border border-bd-2 bg-bg-0 shadow-lg p-3 flex flex-col gap-2"
              style={{ fontSize: 11 }}
            >
              {catalogEntry?.sql_table && (
                <div>
                  <span className="text-[9.5px] uppercase tracking-wide text-fg-3 font-semibold">Tabela</span>
                  <p className="font-mono text-fg-1 mt-0.5">{catalogEntry.sql_table}</p>
                </div>
              )}
              {catalogEntry?.sql && (
                <div>
                  <span className="text-[9.5px] uppercase tracking-wide text-fg-3 font-semibold">Fórmula SQL</span>
                  <button
                    type="button"
                    title="Copiar fórmula"
                    onClick={() => navigator.clipboard.writeText(catalogEntry.sql).catch(() => {})}
                    className="w-full text-left font-mono text-fg-1 mt-0.5 hover:text-accent transition-colors break-all"
                  >
                    {catalogEntry.sql}
                  </button>
                </div>
              )}
              {isAllTime && (
                <div>
                  <span className="text-[9.5px] uppercase tracking-wide text-fg-3 font-semibold">Período</span>
                  <p className="text-fg-1 mt-0.5">todo o histórico do espelho</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <button
        type="button"
        title="Investigar a causa via copiloto"
        className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity text-fg-3 hover:text-accent"
        onClick={() =>
          window.dispatchEvent(
            new CustomEvent('copilot:open', {
              detail: {
                query: hasData
                  ? `Porque está a ${card.label} em ${formatValue(card)}? Investiga a causa.`
                  : `Porque é que a ${card.label} não tem dados? Investiga.`,
              },
            }),
          )
        }
      >
        <Sparkles size={14} />
      </button>
    </DarkCard>
  );
}

// ── Card de gráfico ──────────────────────────────────────────────────────

function ChartCard({ chart, color }: { chart: CubeDashboardChart; color: string }) {
  const data = chart.series
    .filter((p): p is { x: string; y: number } => p.y !== null)
    .map((p) => ({ name: p.x, value: p.y }));

  return (
    <DarkCard>
      <div className="flex items-center justify-between gap-2 mb-3">
        <h3 className="text-sm font-semibold text-fg-1">{chart.label}</h3>
        {chart.status !== 'ok' && <DarkBadge variant="neutral">sem dados</DarkBadge>}
      </div>
      {data.length > 0 ? (
        <div className="rounded-lg border border-bd-1 bg-bg-1 p-2">
          {chart.kind === 'line' ? (
            <LineChart data={data} height={220} color={color} showGrid showArea />
          ) : (
            <BarChart data={data} height={220} color={color} showGrid />
          )}
        </div>
      ) : (
        <div
          className="rounded-lg border border-dashed border-bd-2 bg-bg-1 flex flex-col items-center justify-center gap-2 text-center px-6"
          style={{ minHeight: 220 }}
        >
          <Database className="h-7 w-7 text-fg-3" />
          <p className="text-sm font-medium text-fg-2">Sem dados para este indicador</p>
          <p className="text-xs text-fg-3 max-w-xs leading-relaxed">
            O mart correspondente ainda não está populado. Corre o ETL (mirror NELO +
            setup_marts) para ver a série.
          </p>
        </div>
      )}
    </DarkCard>
  );
}
