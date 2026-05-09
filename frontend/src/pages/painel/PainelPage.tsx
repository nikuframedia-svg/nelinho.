/**
 * PainelPage — homepage portada do nelo (1).zip pages-1.jsx:PainelPage.
 *
 * Substitui Dashboard.tsx + OpsInboxPage.tsx + DecisionsPage.tsx +
 * plan/TimelinePage.tsx + improve/SuggestionsPage.tsx (todos absorvidos
 * em secções/panels desta página).
 *
 * Layout do zip (4 áreas):
 *   1. PageHeader (título + subtítulo + Atualizar/Filtros/Pedir-ao-Copilot)
 *   2. KPI grid 4 cards (€/dia, Concluídos, Em risco, Alertas activos) com
 *      Sparkline (quando há série histórica) e TrustBadge
 *   3. Grid 2-col: Alertas activos · 5 (AlertRow list) | Timeline aprovação
 *   4. Grid 2:1: Actividade ao vivo (LiveActivityFeed wrapped) | Trust sources
 *
 * ZERO MOCKS: dados reais via TanStack Query; empty/error states explícitos.
 * Sem sparklines fake — se backend não devolver série, KPICard render sem.
 *
 * Sprint Q.18.ZIP.B.
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  RefreshCw,
  Filter,
  Sparkles,
  Euro,
  CheckCircle2,
  AlertTriangle,
  Bell,
  ArrowRight,
  Activity,
  Inbox,
} from 'lucide-react';
import {
  PageHeader,
  KPICard,
  Panel,
  AlertRow,
  TrustBadge,
  Tabs,
  scoreToGrade,
  type KPIStatus,
  type AlertKind,
} from '../../components/dark';
import { LiveActivityFeed } from '../../components/activity/LiveActivityFeed';
import { ceoDashboardApi, decisionsApi, dqaApi } from '../../lib/api';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES — alguns derivados de tipos partial em ceoDashboardApi/dqaApi
// ═══════════════════════════════════════════════════════════════════════════════

interface AlertRowFromApi {
  alert_id?: string | number;
  severity?: 'critical' | 'high' | 'medium' | 'low' | string;
  title?: string;
  message?: string;
  source?: string;
  created_at?: string;
  meta?: string;
}

interface TrustComponentFromApi {
  name: string;
  score: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

function severityToKindLocal(sev?: string): AlertKind {
  switch (sev) {
    case 'critical':
    case 'high':
      return 'danger';
    case 'medium':
      return 'warning';
    case 'low':
      return 'info';
    default:
      return 'neutral';
  }
}

function relativeTime(iso?: string): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const diffMs = Date.now() - date.getTime();
  const min = Math.floor(diffMs / 60_000);
  if (min < 1) return 'agora';
  if (min < 60) return `há ${min} min`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `há ${hr}h`;
  return `há ${Math.floor(hr / 24)}d`;
}

function statusForCount(count: number, threshold: number): KPIStatus {
  if (count === 0) return 'neutral';
  if (count <= threshold) return 'yellow';
  return 'red';
}

// ═══════════════════════════════════════════════════════════════════════════════
// COPILOT TRIGGER — pede ao copilot via custom event que CopilotFab escuta
// ═══════════════════════════════════════════════════════════════════════════════

function askCopilot(query: string) {
  window.dispatchEvent(
    new CustomEvent('copilot:open', { detail: { query } })
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// BACKLOG BY CLIENT PANEL — Q.18.ZIP Onda 4 (endpoint existing sub-utilizado)
// ═══════════════════════════════════════════════════════════════════════════════

function BacklogByClientPanel({ refreshKey }: { refreshKey: number }) {
  const navigate = useNavigate();
  const backlogQuery = useQuery({
    queryKey: ['painel', 'backlog-by-client', refreshKey],
    queryFn: () => ceoDashboardApi.backlogByClient({ limit: 8 }),
    staleTime: 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const items: any[] = useMemo(() => {
    const data: any = backlogQuery.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    return data.items ?? [];
  }, [backlogQuery.data]);

  if (backlogQuery.isError || (backlogQuery.data && items.length === 0)) {
    return null; // Não polui o Painel se não há dados
  }

  return (
    <Panel
      title="Backlog por cliente"
      badge={items.length}
      action={
        <button
          type="button"
          onClick={() => navigate('/relatorios')}
          className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-text-dark-secondary hover:text-text-dark-primary hover:bg-white/5 transition-colors"
        >
          Ver mais <ArrowRight size={12} />
        </button>
      }
      flush
    >
      {backlogQuery.isLoading ? (
        <div className="px-4 py-4 text-center text-xs text-text-dark-tertiary">
          A carregar backlog…
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b border-white/[0.06]">
              <tr className="text-left text-[10px] uppercase tracking-wider text-text-dark-tertiary">
                <th className="px-3 py-2 font-semibold">Cliente</th>
                <th className="px-3 py-2 font-semibold text-right">Encomendas</th>
                <th className="px-3 py-2 font-semibold text-right">Valor €</th>
                <th className="px-3 py-2 font-semibold">Próximo prazo</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, 8).map((row, idx) => (
                <tr
                  key={row.client_name ?? row.id ?? idx}
                  className="border-b border-white/[0.04] hover:bg-white/[0.02]"
                >
                  <td className="px-3 py-2 text-text-dark-primary truncate max-w-[200px]">
                    {row.client_name ?? row.client ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-text-dark-secondary">
                    {row.orders_count ?? row.count ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-text-dark-secondary">
                    {row.total_value_eur !== undefined
                      ? `€${Math.round(row.total_value_eur).toLocaleString('pt-PT')}`
                      : '—'}
                  </td>
                  <td className="px-3 py-2 text-text-dark-tertiary tabular-nums">
                    {row.earliest_deadline
                      ? new Date(row.earliest_deadline).toLocaleDateString('pt-PT')
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// INBOX PANEL — Q.18.ZIP.M.2
// ═══════════════════════════════════════════════════════════════════════════════

const INBOX_TAB_IDS = ['pending', 'accepted', 'rejected', 'all'] as const;
type InboxTabId = (typeof INBOX_TAB_IDS)[number];

// Backend DecisionStatus enum (src/governance/models.py:58):
//   proposed/pending_approval/approved/rejected/executing/executed/...
// Inbox "Pendentes" = aguardam aprovação humana → PENDING_APPROVAL.
const STATUS_BY_TAB: Record<InboxTabId, string | undefined> = {
  pending: 'PENDING_APPROVAL',
  accepted: 'EXECUTED',
  rejected: 'REJECTED',
  all: undefined,
};

function InboxPanel({ refreshKey }: { refreshKey: number }) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<InboxTabId>('pending');

  const counts = useQuery({
    queryKey: ['painel', 'inbox', 'counts', refreshKey],
    queryFn: async () => {
      // Faz 4 queries em paralelo para counts (tolerante a falhas)
      const fetch = async (status?: string) => {
        try {
          const r: any = await decisionsApi.list({ status, page_size: 1 });
          return r?.total ?? r?.count ?? r?.items?.length ?? 0;
        } catch {
          return 0;
        }
      };
      const [pending, accepted, rejected, all] = await Promise.all([
        fetch('PENDING'),
        fetch('EXECUTED'),
        fetch('REJECTED'),
        fetch(undefined),
      ]);
      return { pending, accepted, rejected, all };
    },
    staleTime: 30_000,
    retry: 0,
  });

  const list = useQuery({
    queryKey: ['painel', 'inbox', 'list', tab, refreshKey],
    queryFn: async () => {
      const status = STATUS_BY_TAB[tab];
      try {
        return (await decisionsApi.list({ status, page_size: 6 })) as any;
      } catch (err) {
        return null;
      }
    },
    staleTime: 15_000,
    retry: 0,
  });

  const items: any[] = useMemo(() => {
    const data: any = list.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    return data.items ?? data.decisions ?? [];
  }, [list.data]);

  const tabsConfig = [
    { id: 'pending', label: 'Pendentes', count: counts.data?.pending },
    { id: 'accepted', label: 'Aceites', count: counts.data?.accepted },
    { id: 'rejected', label: 'Rejeitadas', count: counts.data?.rejected },
    { id: 'all', label: 'Tudo', count: counts.data?.all },
  ];

  return (
    <Panel
      title="Inbox de decisões"
      badge={counts.data?.pending ?? '—'}
      action={
        <button
          type="button"
          onClick={() => navigate('/configuracao?tab=auditoria')}
          className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-text-dark-secondary hover:text-text-dark-primary hover:bg-white/5 transition-colors"
        >
          Histórico
        </button>
      }
      flush
    >
      <div className="px-2 pt-2">
        <Tabs
          variant="pills"
          tabs={tabsConfig}
          value={tab}
          onChange={(v) => setTab(v as InboxTabId)}
        />
      </div>
      <div className="px-2 py-3">
        {list.isLoading ? (
          <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
            A carregar decisões…
          </div>
        ) : list.isError || list.data === null ? (
          <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
            <Inbox size={20} className="mx-auto mb-2 opacity-50" />
            Endpoint /v1/decisions indisponível.
            <br />
            <span className="text-text-dark-secondary">
              Quando wired, sugestões CPO aparecem aqui.
            </span>
          </div>
        ) : items.length === 0 ? (
          <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
            <Inbox size={20} className="mx-auto mb-2 opacity-50" />
            {tab === 'pending'
              ? 'Sem decisões pendentes. Tudo decidido!'
              : tab === 'accepted'
              ? 'Sem decisões aceites no período.'
              : tab === 'rejected'
              ? 'Sem decisões rejeitadas no período.'
              : 'Sem decisões registadas.'}
          </div>
        ) : (
          <div className="flex flex-col divide-y divide-white/[0.04]">
            {items.slice(0, 6).map((d, idx) => (
              <button
                key={d.id ?? d.decision_id ?? idx}
                type="button"
                onClick={() => navigate('/configuracao?tab=auditoria')}
                className="text-left px-3 py-2 hover:bg-white/[0.03] transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="text-sm text-text-dark-primary truncate">
                    {d.title ?? d.summary ?? d.decision_type ?? '(Sem título)'}
                  </span>
                  <span className="shrink-0 text-[10px] uppercase tracking-wider text-text-dark-tertiary">
                    {d.status ?? d.decision_status ?? ''}
                  </span>
                </div>
                {d.created_at ? (
                  <span className="text-[10px] text-text-dark-tertiary tabular-nums">
                    {new Date(d.created_at).toLocaleString('pt-PT')}
                  </span>
                ) : null}
              </button>
            ))}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════════

export default function PainelPage() {
  const navigate = useNavigate();
  const [refreshKey, setRefreshKey] = useState(0);

  // ─── Queries paralelas, cada uma independente ───
  const otdQuery = useQuery({
    queryKey: ['painel', 'otd', refreshKey],
    queryFn: () => ceoDashboardApi.otd({ window_days: 7 }),
    staleTime: 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const fpyQuery = useQuery({
    queryKey: ['painel', 'fpy', refreshKey],
    queryFn: () => ceoDashboardApi.firstPassYield({ window_days: 7 }),
    staleTime: 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const alertsQuery = useQuery({
    queryKey: ['painel', 'alerts', refreshKey],
    queryFn: () => ceoDashboardApi.activeAlerts({ limit: 8 }),
    staleTime: 30_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const expeditionsQuery = useQuery({
    queryKey: ['painel', 'expeditions', refreshKey],
    queryFn: () => ceoDashboardApi.expeditionsNextNDays({ horizon_days: 7 }),
    staleTime: 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const trustQuery = useQuery({
    queryKey: ['painel', 'trust', refreshKey],
    queryFn: () => dqaApi.trustIndex({ scope: 'factory' }),
    staleTime: 5 * 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  // ─── Derivações para KPIs ───
  const alertsItems = useMemo<AlertRowFromApi[]>(() => {
    const data: any = alertsQuery.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.items)) return data.items;
    if (Array.isArray(data.alerts)) return data.alerts;
    return [];
  }, [alertsQuery.data]);

  const expeditionsAtRisk = useMemo(() => {
    const data: any = expeditionsQuery.data;
    if (!data?.items) return 0;
    return data.items.filter((it: any) => it.risk === 'over_capacity' || it.risk === 'near_capacity').length;
  }, [expeditionsQuery.data]);

  const otdPct = (otdQuery.data as any)?.otd_pct ?? null;
  const fpyPct = (fpyQuery.data as any)?.fpy_pct ?? null;

  // Backend /v1/dqa/trust-index devolve { composite: 0..1, components:
  // { completeness: 0..1, validity: 0..1, ... }, weights: { ... } }.
  // Aceita ambos `composite` (canónico) e `trust_index` (legacy) por defesa.
  const trustScore = (trustQuery.data as any)?.composite
    ?? (trustQuery.data as any)?.trust_index
    ?? null;
  const trustGrade = trustScore !== null ? scoreToGrade(trustScore) : undefined;

  const trustComponents = useMemo<TrustComponentFromApi[]>(() => {
    const data: any = trustQuery.data;
    if (!data) return [];
    if (Array.isArray(data.components)) return data.components;
    if (data.components && typeof data.components === 'object') {
      const weights = data.weights ?? {};
      return Object.entries(data.components)
        .filter(([, score]) => score !== null && score !== undefined)
        .map(([name, score]) => ({
          name,
          score: Number(score),
          weight: weights[name],
        }));
    }
    return [];
  }, [trustQuery.data]);

  // ─── Refresh universal ───
  const handleRefresh = () => setRefreshKey((k) => k + 1);

  return (
    <div>
      <PageHeader
        title="Painel"
        subtitle="VISÃO GERAL · TURNO DE HOJE"
        actions={
          <>
            <button
              type="button"
              onClick={handleRefresh}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
              title="Atualizar dados"
            >
              <RefreshCw size={13} />
              Atualizar
            </button>
            <button
              type="button"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-dark-700 text-text-dark-secondary hover:bg-dark-600 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
              disabled
              title="Em breve — filtros globais"
            >
              <Filter size={13} />
              Filtros
            </button>
            <button
              type="button"
              onClick={() => askCopilot('O que devo focar hoje no painel?')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-xs font-medium transition-colors"
            >
              <Sparkles size={13} />
              Pedir ao Copilot
            </button>
          </>
        }
      />

      <div className="px-6 py-4 space-y-4">
        {/* ═══ KPI GRID ═══ */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            label="OTD (7 dias)"
            icon={<Euro size={14} />}
            value={otdPct === null ? '—' : (otdPct * 100).toFixed(0)}
            unit="%"
            target="100"
            status={
              otdPct === null
                ? 'neutral'
                : otdPct >= 0.95
                ? 'green'
                : otdPct >= 0.85
                ? 'yellow'
                : 'red'
            }
            description="Entregas no prazo · janela 7 dias"
            trust={trustGrade}
            onClick={() => navigate('/relatorios')}
          />
          <KPICard
            label="Qualidade 1ª passagem"
            icon={<CheckCircle2 size={14} />}
            value={fpyPct === null ? '—' : (fpyPct * 100).toFixed(0)}
            unit="%"
            target="95"
            status={
              fpyPct === null
                ? 'neutral'
                : fpyPct >= 0.85
                ? 'green'
                : fpyPct >= 0.70
                ? 'yellow'
                : 'red'
            }
            description="Sem retrabalho · 7 dias"
            trust={trustGrade}
            onClick={() => navigate('/qualidade')}
          />
          <KPICard
            label="Expedições em risco"
            icon={<AlertTriangle size={14} />}
            value={expeditionsAtRisk}
            unit="lotes"
            status={statusForCount(expeditionsAtRisk, 1)}
            description="Próximos 7 dias"
            onClick={() => navigate('/expedicao')}
          />
          <KPICard
            label="Alertas activos"
            icon={<Bell size={14} />}
            value={alertsItems.length}
            unit="aviso"
            status={statusForCount(alertsItems.length, 2)}
            description={alertsItems.length === 0 ? 'Tudo calmo' : 'Carregar para ver lista'}
          />
        </div>

        {/* ═══ ROW: Alertas + Timeline ═══ */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Panel
            title="Alertas activos"
            badge={alertsItems.length}
            action={
              <button
                type="button"
                onClick={() => navigate('/qualidade')}
                className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs text-text-dark-secondary hover:text-text-dark-primary hover:bg-white/5 transition-colors"
              >
                Ver tudo <ArrowRight size={12} />
              </button>
            }
            flush
          >
            {alertsQuery.isLoading ? (
              <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
                A carregar alertas…
              </div>
            ) : alertsQuery.isError ? (
              <div className="px-4 py-6 text-center text-xs text-danger">
                Erro a carregar alertas — clica em Atualizar.
              </div>
            ) : alertsItems.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
                Sem alertas activos. Tudo calmo no chão de fábrica.
              </div>
            ) : (
              <div>
                {alertsItems.slice(0, 6).map((a, idx) => (
                  <AlertRow
                    key={`${a.alert_id ?? idx}`}
                    kind={severityToKindLocal(a.severity)}
                    title={a.title ?? a.message ?? '(Sem título)'}
                    meta={
                      [a.source?.toUpperCase(), relativeTime(a.created_at)]
                        .filter(Boolean)
                        .join(' · ')
                    }
                    onClick={() => navigate('/qualidade')}
                  />
                ))}
              </div>
            )}
          </Panel>

          {/* Q.18.ZIP.M.2 — Inbox melhorada com filter tabs */}
          <InboxPanel refreshKey={refreshKey} />
        </div>

        {/* fecho do grid 2-col */}
        <div className="hidden">{/* spacer */}
        </div>

        {/* ═══ Q.18.ZIP Onda 4 — Backlog por cliente (endpoint existing sub-utilizado) ═══ */}
        <BacklogByClientPanel refreshKey={refreshKey} />

        {/* ═══ ROW: Activity feed + Trust sources ═══ */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <Panel
              title="Actividade ao vivo"
              action={
                <span className="inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-success">
                  <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
                  AO VIVO
                </span>
              }
              flush
              bodyClassName="p-0"
            >
              <LiveActivityFeed maxItems={6} showHeader={false} compact />
            </Panel>
          </div>

          <Panel
            title="Trust index — fontes"
            badge={trustGrade}
            flush
          >
            {trustQuery.isLoading ? (
              <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
                A calcular trust…
              </div>
            ) : trustQuery.isError ? (
              <div className="px-4 py-6 text-center text-xs text-danger">
                Erro a calcular Trust Index.
              </div>
            ) : trustComponents.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-text-dark-tertiary">
                Sem componentes de Trust visíveis.
                <br />
                <button
                  type="button"
                  onClick={() => navigate('/configuracao?tab=trust')}
                  className="text-accent-400 hover:underline mt-1 inline-flex items-center gap-1"
                >
                  Configurar Trust Index
                  <ArrowRight size={11} />
                </button>
              </div>
            ) : (
              <div className="px-4 py-3 space-y-3">
                {trustComponents.map((c) => {
                  const grade = scoreToGrade(c.score);
                  const pctW = `${Math.round(c.score * 100)}%`;
                  const barColor =
                    c.score >= 0.85
                      ? 'bg-success'
                      : c.score >= 0.70
                      ? 'bg-warning'
                      : 'bg-danger';
                  return (
                    <div key={c.name} className="flex items-center gap-3">
                      <div className="flex-1 text-xs text-text-dark-secondary truncate">
                        {c.name}
                      </div>
                      <div className="w-20 h-1.5 bg-dark-900 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${barColor} transition-all duration-300`}
                          style={{ width: pctW }}
                        />
                      </div>
                      <TrustBadge grade={grade} size="xs" />
                    </div>
                  );
                })}
                <div className="border-t border-white/[0.06] pt-2 mt-2">
                  <button
                    type="button"
                    onClick={() => navigate('/configuracao?tab=trust')}
                    className="text-[10px] text-text-dark-tertiary hover:text-text-dark-secondary inline-flex items-center gap-1"
                  >
                    <Activity size={10} /> Ver detalhes Trust v2
                  </button>
                </div>
              </div>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
