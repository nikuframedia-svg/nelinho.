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

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart3,
  RefreshCw,
  AlertTriangle,
  Sparkles,
  Database,
  Plus,
  X,
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

  // Valores das measures escolhidas (ad-hoc, period agregado).
  const myCardsQuery = useQuery({
    queryKey: cubeKeys.measureCards(selection),
    queryFn: () =>
      cubeApi.measureCards(selection.map((m) => ({ measure: m, period: 'none' as const }))),
    enabled: selection.length > 0,
    refetchInterval: 60_000,
    refetchOnWindowFocus: false,
  });

  const cards = dashQuery.data?.cards ?? [];
  const charts = dashQuery.data?.charts ?? [];
  const myCards = myCardsQuery.data?.cards ?? [];
  const catalog = catalogQuery.data?.measures ?? [];

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
            if (!card) {
              return <DarkCard key={name} className="h-[92px] animate-pulse" />;
            }
            return <MyKpiCard key={name} card={card} onRemove={() => removeMeasure(name)} />;
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
          {cards.map((card) => (
            <KpiCard key={card.key} card={card} />
          ))}
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

function MyKpiCard({ card, onRemove }: { card: CubeDashboardCard; onRemove: () => void }) {
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
          <DarkBadge variant="neutral">sem dados</DarkBadge>
        )}
      </div>
    </DarkCard>
  );
}

// ── Card de KPI (destaque curado) ───────────────────────────────────────────

function KpiCard({ card }: { card: CubeDashboardCard }) {
  const hasData = card.status === 'ok' && card.value !== null;

  return (
    <DarkCard className="relative group">
      <div className="flex items-start justify-between gap-2 mb-1">
        <span className="text-xs font-medium text-fg-2 leading-tight">{card.label}</span>
        {!hasData && <DarkBadge variant="neutral">sem dados</DarkBadge>}
      </div>
      <div className="flex items-baseline gap-1 mt-1.5">
        {hasData ? (
          <span className="text-2xl font-bold text-fg-0 tabular-nums">{formatValue(card)}</span>
        ) : (
          <span className="text-sm text-fg-3">—</span>
        )}
      </div>
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
