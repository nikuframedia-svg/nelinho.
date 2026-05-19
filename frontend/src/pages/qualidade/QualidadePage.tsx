/**
 * QualidadePage — página "Qualidade" · Q.52.I.
 *
 * Reconstrução fiel do protótipo NELO.html (page-qualidade.jsx): 10
 * tabs — Resumo, Predições, Mapa do casco, Erros, Moldes, Retrabalho,
 * Aderência, Diagnóstico, OEE, Custos vs Ganhos.
 *
 * ZERO MOCKS — cada tab liga a endpoints REAIS:
 *   /v1/quality/{dashboard,first-pass-yield,by-supplier,by-lot,
 *               workers/ranking,rework,root-cause,impact}
 *   /v1/profit/oee?group_by=phase · /v1/plan/molds/{*}
 * Endpoints sem fonte (defect-zones, plan/adherence, curing-validation,
 * risco preditivo por barco, ROI de qualidade) degradam com empty state
 * honesto via useHonestEmptyState — nunca placeholder.
 *
 * Átomos da Onda 0 (KPIBig, OEERing, RiskBadge) reutilizados; primitivas
 * locais (Card, SectionHeader, MiniBar, HullHeatmap, Banner) em
 * components/qualidade/QualidadeBits.tsx.
 */

import { useMemo, useState } from 'react';
import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import {
  ShieldCheck,
  AlertCircle,
  Wrench,
  Repeat,
  Brain,
  Activity,
  TrendingUp,
  Layers,
  Target,
  Euro,
  RefreshCw,
} from 'lucide-react';
import {
  PageHeader,
  Tabs,
  KPIBig,
  OEERing,
  EmptyState,
} from '../../components/dark';
import {
  Card,
  SectionHeader,
  MiniBar,
  Banner,
} from '../../components/qualidade/QualidadeBits';
import { useHonestEmptyState } from '../../hooks/useHonestEmptyState';
import {
  apiFetch,
  moldsApi,
  employeesApi,
  qualityReworkApi,
  type Mold,
  type ReworkCreatePayload,
} from '../../lib/api';

// ─── Tabs ────────────────────────────────────────────────────────────────

const TAB_IDS = [
  'resumo',
  'predicoes',
  'mapa',
  'erros',
  'moldes',
  'retrabalho',
  'aderencia',
  'diagnostico',
  'oee',
  'custos',
] as const;
type TabId = (typeof TAB_IDS)[number];

function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

// ─── Tipos das respostas REAIS ──────────────────────────────────────────

interface QualityDashboardItem {
  key: string;
  events: number;
  share_pct: number;
}
interface QualityDashboardResponse {
  group_by: string;
  window: { from: string; to: string };
  total_events: number;
  items: QualityDashboardItem[];
}

interface ReworkRow {
  id: string;
  of_id: string;
  error_code: string;
  error_description: string | null;
  phase_id_causer: string | null;
  causer_employee_id: string | null;
  detected_at: string | null;
  resolved_at: string | null;
  cost_estimate_eur: number | null;
}

interface OeeItem {
  group_value: string;
  availability: number;
  performance: number;
  quality: number;
  oee: number;
  sample_size: number;
  sample_excluded: number;
}
interface OeeResponse {
  date_from: string;
  date_to: string;
  group_by: string;
  overall: OeeItem;
  breakdown: OeeItem[];
}

interface SupplierLotRow {
  supplier_id?: string;
  lot_id?: string;
  events: number;
}
interface SupplierLotResponse {
  items: SupplierLotRow[];
  count: number;
}

// ─── Página ─────────────────────────────────────────────────────────────

export default function QualidadePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'resumo';

  const tabs = useMemo(
    () => [
      { id: 'resumo', label: 'Resumo', icon: <ShieldCheck size={13} /> },
      { id: 'predicoes', label: 'Predições', icon: <Brain size={13} /> },
      { id: 'mapa', label: 'Mapa do casco', icon: <Layers size={13} /> },
      { id: 'erros', label: 'Erros', icon: <AlertCircle size={13} /> },
      { id: 'moldes', label: 'Moldes', icon: <Wrench size={13} /> },
      { id: 'retrabalho', label: 'Retrabalho', icon: <Repeat size={13} /> },
      { id: 'aderencia', label: 'Aderência', icon: <Target size={13} /> },
      { id: 'diagnostico', label: 'Diagnóstico', icon: <Brain size={13} /> },
      { id: 'oee', label: 'OEE', icon: <Activity size={13} /> },
      { id: 'custos', label: 'Custos vs Ganhos', icon: <Euro size={13} /> },
    ],
    [],
  );

  const handleTabChange = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', id);
    setSearchParams(next, { replace: true });
  };

  return (
    <div>
      <PageHeader
        icon={<ShieldCheck size={18} />}
        title="Qualidade"
        subtitle="Erros, retrabalho, OEE, diagnóstico causal · ROI de cada acção"
        helpId={activeTab === 'oee' ? 'oee' : 'qualidade'}
        actions={
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex items-center gap-1.5 text-text-dark-secondary hover:text-text-dark-primary transition-colors"
            style={{
              padding: '6px 12px',
              height: 32,
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-2)',
              borderRadius: 9,
              fontSize: 12.5,
            }}
          >
            <RefreshCw size={13} />
            Atualizar
          </button>
        }
      />

      <div style={{ padding: '8px 28px 0 28px' }}>
        <Tabs tabs={tabs} value={activeTab} onChange={handleTabChange} sticky />
      </div>

      <div style={{ padding: '20px 28px' }} className="page-enter">
        {activeTab === 'resumo' && <ResumoTab />}
        {activeTab === 'predicoes' && <PredicoesTab />}
        {activeTab === 'mapa' && <MapaTab />}
        {activeTab === 'erros' && <ErrosTab />}
        {activeTab === 'moldes' && <MoldesTab />}
        {activeTab === 'retrabalho' && <RetrabalhoTab />}
        {activeTab === 'aderencia' && <AderenciaTab />}
        {activeTab === 'diagnostico' && <DiagnosticoTab />}
        {activeTab === 'oee' && <OeeTab />}
        {activeTab === 'custos' && <CustosTab />}
      </div>
    </div>
  );
}

// ─── Hooks de dados partilhados ──────────────────────────────────────────

function useFpy() {
  return useQuery({
    queryKey: ['qualidade', 'fpy'],
    queryFn: () =>
      apiFetch<{
        window_days: number;
        orders_total: number;
        orders_with_rework: number;
        first_pass_yield_pct: number;
      }>('/v1/quality/first-pass-yield?window_days=30'),
    staleTime: 60_000,
    retry: 0,
  });
}

function useReworkList() {
  return useQuery<ReworkRow[]>({
    queryKey: ['qualidade', 'rework'],
    queryFn: () => apiFetch<ReworkRow[]>('/v1/quality/rework?limit=100'),
    staleTime: 60_000,
    retry: 0,
  });
}

function useMolds() {
  return useQuery<Mold[]>({
    queryKey: ['qualidade', 'molds-health'],
    queryFn: () => moldsApi.healthReport({ limit: 30 }),
    staleTime: 60_000,
    retry: 0,
  });
}

// ─── ResumoTab ───────────────────────────────────────────────────────────

function ResumoTab() {
  const fpyQuery = useFpy();
  const reworkQuery = useReworkList();
  const moldsQuery = useMolds();
  const dashboardQuery = useQuery<QualityDashboardResponse>({
    queryKey: ['qualidade', 'dashboard-phase'],
    queryFn: () =>
      apiFetch<QualityDashboardResponse>(
        '/v1/quality/dashboard?group_by=phase&top_n=10',
      ),
    staleTime: 60_000,
    retry: 0,
  });

  const rework = reworkQuery.data ?? [];
  const totalCost = rework.reduce(
    (s, r) => s + (r.cost_estimate_eur ?? 0),
    0,
  );
  const activeErrors = rework.filter((r) => !r.resolved_at).length;
  const molds = moldsQuery.data ?? [];
  const criticalMolds = molds.filter(
    (m) => m.health?.risk_category === 'red',
  ).length;
  const fpy = fpyQuery.data?.first_pass_yield_pct ?? null;

  return (
    <>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <KPIBig
          label="1ª passagem"
          value={fpy !== null ? Number(fpy.toFixed(1)) : '—'}
          unit={fpy !== null ? '%' : undefined}
          context={
            fpy !== null
              ? `${fpyQuery.data?.orders_total ?? 0} ordens (30d)`
              : fpyQuery.isLoading
                ? 'A carregar…'
                : 'Sem ordens concluídas'
          }
          status={fpy === null ? 'gray' : fpy >= 95 ? 'green' : fpy >= 90 ? 'yellow' : 'red'}
          accent={fpy === null ? 'gray' : fpy >= 95 ? 'green' : fpy >= 90 ? 'yellow' : 'red'}
        />
        <KPIBig
          label="Erros activos"
          value={reworkQuery.isLoading ? '—' : activeErrors}
          context={
            reworkQuery.isLoading
              ? 'A carregar…'
              : `${rework.length} registos de retrabalho`
          }
          status={activeErrors > 8 ? 'red' : activeErrors > 0 ? 'orange' : 'green'}
          accent={activeErrors > 8 ? 'red' : activeErrors > 0 ? 'orange' : 'green'}
        />
        <KPIBig
          label="Custo retrabalho"
          value={reworkQuery.isLoading ? '—' : Math.round(totalCost)}
          prefix={reworkQuery.isLoading ? undefined : '€'}
          context="Soma de cost_estimate_eur dos registos"
          status="red"
          accent="red"
        />
        <KPIBig
          label="Moldes críticos"
          value={moldsQuery.isLoading ? '—' : criticalMolds}
          unit={moldsQuery.isLoading ? undefined : `/ ${molds.length}`}
          context={
            moldsQuery.isLoading
              ? 'A carregar…'
              : criticalMolds > 0
                ? 'Moldes com health RED'
                : 'Todos os moldes monitorizados OK'
          }
          status={criticalMolds > 0 ? 'red' : 'green'}
          accent={criticalMolds > 0 ? 'red' : 'green'}
        />
      </div>

      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}
      >
        <Card padding={18}>
          <SectionHeader
            icon={<AlertCircle size={14} />}
            title="Erros recentes"
            subtitle="Retrabalho registado · ReworkEntry"
          />
          {reworkQuery.isLoading ? (
            <LoadingLine />
          ) : rework.length === 0 ? (
            <EmptyState
              size="sm"
              title="Sem retrabalho registado"
              hint="Quando houver registos de retrabalho, aparecem aqui ordenados por data."
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {rework.slice(0, 8).map((e) => (
                <div
                  key={e.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: '8px 10px',
                    background: 'var(--bg-2)',
                    borderRadius: 'var(--r-sm)',
                  }}
                >
                  <span
                    style={{
                      width: 3,
                      height: 24,
                      background: e.resolved_at
                        ? 'var(--green)'
                        : 'var(--red)',
                      borderRadius: 2,
                    }}
                  />
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                      }}
                    >
                      <span
                        style={{
                          fontSize: 12,
                          color: 'var(--fg-0)',
                          fontWeight: 500,
                        }}
                      >
                        {e.of_id}
                      </span>
                      {e.cost_estimate_eur ? (
                        <span
                          className="tabular"
                          style={{ fontSize: 11, color: 'var(--red)' }}
                        >
                          −€{Math.round(e.cost_estimate_eur)}
                        </span>
                      ) : null}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--fg-2)',
                        marginTop: 1,
                      }}
                    >
                      {e.error_description ?? e.error_code} ·{' '}
                      {e.phase_id_causer ?? 'fase n/d'}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card padding={18}>
          <SectionHeader
            icon={<Wrench size={14} />}
            title="Estado dos moldes"
            subtitle="Health report · vermelhos primeiro"
          />
          {moldsQuery.isLoading ? (
            <LoadingLine />
          ) : molds.length === 0 ? (
            <EmptyState
              size="sm"
              title="Sem moldes"
              hint="Quando houver moldes sincronizados, o estado de saúde aparece aqui."
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {molds.slice(0, 8).map((m) => {
                const score = m.health?.score_0_100 ?? 0;
                const tone =
                  m.health?.risk_category === 'red'
                    ? 'red'
                    : m.health?.risk_category === 'yellow'
                      ? 'yellow'
                      : 'green';
                return (
                  <div key={m.id}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'baseline',
                        marginBottom: 5,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 12,
                          color: 'var(--fg-0)',
                          fontWeight: 500,
                        }}
                      >
                        {m.name ?? m.mold_code}
                      </span>
                      <span
                        className="tabular"
                        style={{ fontSize: 11, color: `var(--${tone})` }}
                      >
                        health {score.toFixed(0)}
                      </span>
                    </div>
                    <MiniBar
                      value={score}
                      max={100}
                      color={`var(--${tone})`}
                      height={4}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>

      <Card padding={18} style={{ marginTop: 14 }}>
        <SectionHeader
          icon={<Repeat size={14} />}
          title="Retrabalho por fase"
          subtitle="QualityDashboardService · group_by=phase · 30 dias"
        />
        {dashboardQuery.isLoading ? (
          <LoadingLine />
        ) : (dashboardQuery.data?.items ?? []).length === 0 ? (
          <EmptyState
            size="sm"
            title="Sem retrabalho por fase"
            hint="Não há registos de retrabalho agrupáveis por fase na janela."
          />
        ) : (
          (dashboardQuery.data?.items ?? []).map((it, i, arr) => {
            const tone =
              it.share_pct > 30
                ? 'red'
                : it.share_pct > 15
                  ? 'yellow'
                  : 'green';
            return (
              <div
                key={it.key}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '180px 1fr 90px 70px',
                  alignItems: 'center',
                  gap: 14,
                  padding: '9px 0',
                  borderBottom:
                    i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
                  fontSize: 12,
                }}
              >
                <span style={{ color: 'var(--fg-0)', fontWeight: 500 }}>
                  {it.key}
                </span>
                <MiniBar
                  value={it.share_pct}
                  max={60}
                  color={`var(--${tone})`}
                  height={5}
                />
                <span
                  className="tabular"
                  style={{ color: `var(--${tone})`, fontWeight: 600 }}
                >
                  {it.share_pct.toFixed(1)}%
                </span>
                <span
                  className="tabular"
                  style={{ color: 'var(--fg-2)', textAlign: 'right' }}
                >
                  {it.events} ev.
                </span>
              </div>
            );
          })
        )}
      </Card>
    </>
  );
}

// ─── PredicoesTab ────────────────────────────────────────────────────────

function PredicoesTab() {
  // O risco preditivo de defeito por barco precisa de um endpoint de
  // orquestração ML que ainda não existe (gap Q.53). Empty state honesto.
  return (
    <Card padding={20}>
      <SectionHeader
        icon={<Brain size={14} />}
        title="Risco preditivo de defeito por barco"
        subtitle="QualityRiskModel · scoring por barco em produção"
      />
      <EmptyState
        title="Predições por barco ainda não disponíveis"
        hint="O scoring de risco preditivo por barco precisa de um endpoint de orquestração do QualityRiskModel que ainda não está exposto. Até lá, o risco não é mostrado para não inventar números. O modelo continua ligado ao fitness do CPO."
      />
    </Card>
  );
}

// ─── MapaTab ─────────────────────────────────────────────────────────────

function MapaTab() {
  // O mapa de defeitos por zona do casco precisa do endpoint
  // /v1/quality/defect-zones, que ainda não existe. Empty state honesto.
  return (
    <Card padding={20}>
      <SectionHeader
        icon={<Layers size={14} />}
        title="Mapa de defeitos por zona do casco"
        subtitle="OFCH_LOCAL · onde o defeito ocorre, não só quanto"
      />
      <EmptyState
        title="Mapa do casco ainda não disponível"
        hint="A agregação de defeitos por zona do casco (endpoint /v1/quality/defect-zones) ainda não está ligada. Assim que a fonte OFCH_LOCAL for exposta, a silhueta com heatmap aparece aqui."
      />
    </Card>
  );
}

// ─── ErrosTab ────────────────────────────────────────────────────────────

function ErrosTab() {
  const dashboardQuery = useQuery<QualityDashboardResponse>({
    queryKey: ['qualidade', 'dashboard-sku'],
    queryFn: () =>
      apiFetch<QualityDashboardResponse>(
        '/v1/quality/dashboard?group_by=sku&top_n=15',
      ),
    staleTime: 60_000,
    retry: 0,
  });
  const supplierQuery = useQuery<SupplierLotResponse>({
    queryKey: ['qualidade', 'by-supplier'],
    queryFn: () =>
      apiFetch<SupplierLotResponse>('/v1/quality/by-supplier?top_n=10'),
    staleTime: 60_000,
    retry: 0,
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card padding={18}>
        <SectionHeader
          title="Erros por modelo"
          subtitle="QualityDashboardService · group_by=sku · 30 dias"
        />
        {dashboardQuery.isLoading ? (
          <LoadingLine />
        ) : (dashboardQuery.data?.items ?? []).length === 0 ? (
          <EmptyState
            size="sm"
            title="Sem erros por modelo"
            hint="Não há registos de retrabalho agrupáveis por modelo na janela."
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(dashboardQuery.data?.items ?? []).map((it) => {
              const tone =
                it.share_pct > 25
                  ? 'red'
                  : it.share_pct > 12
                    ? 'orange'
                    : 'yellow';
              return (
                <div
                  key={it.key}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '2fr 1fr 90px',
                    alignItems: 'center',
                    gap: 12,
                    padding: '10px 12px',
                    background: 'var(--bg-2)',
                    borderRadius: 'var(--r-sm)',
                  }}
                >
                  <span style={{ fontSize: 12.5, color: 'var(--fg-0)' }}>
                    {it.key}
                  </span>
                  <MiniBar
                    value={it.events}
                    max={Math.max(
                      ...(dashboardQuery.data?.items ?? []).map(
                        (x) => x.events,
                      ),
                      1,
                    )}
                    color={`var(--${tone})`}
                    height={4}
                    label={`${it.events} ocorrências`}
                  />
                  <span
                    className="tabular"
                    style={{
                      fontSize: 12,
                      color: `var(--${tone})`,
                      fontWeight: 600,
                      textAlign: 'right',
                    }}
                  >
                    {it.share_pct.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card padding={18}>
        <SectionHeader
          title="Erros por fornecedor"
          subtitle="SupplierQualityService · top 10"
        />
        {supplierQuery.isLoading ? (
          <LoadingLine />
        ) : (supplierQuery.data?.items ?? []).length === 0 ? (
          <EmptyState
            size="sm"
            title="Sem erros atribuídos a fornecedor"
            hint="Não há registos de retrabalho com fornecedor associado."
          />
        ) : (
          (supplierQuery.data?.items ?? []).map((it, i, arr) => (
            <div
              key={(it.supplier_id ?? '') + i}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 90px',
                alignItems: 'center',
                gap: 12,
                padding: '9px 0',
                borderBottom:
                  i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
                fontSize: 12,
              }}
            >
              <span style={{ color: 'var(--fg-1)' }}>
                {it.supplier_id ?? '—'}
              </span>
              <span
                className="tabular"
                style={{
                  color: 'var(--orange)',
                  fontWeight: 600,
                  textAlign: 'right',
                }}
              >
                {it.events} ev.
              </span>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}

// ─── MoldesTab ───────────────────────────────────────────────────────────

function MoldesTab() {
  const moldsQuery = useMolds();
  const molds = moldsQuery.data ?? [];

  return (
    <>
      <Card padding={18} style={{ marginBottom: 14 }}>
        <SectionHeader
          icon={<Wrench size={14} />}
          title="Saúde dos moldes"
          subtitle="MoldHealthService · ordenado por risco"
        />
      </Card>
      {moldsQuery.isLoading ? (
        <Card padding={18}>
          <LoadingLine />
        </Card>
      ) : molds.length === 0 ? (
        <Card padding={18}>
          <EmptyState
            size="sm"
            title="Sem moldes sincronizados"
            hint="Quando houver moldes na base de dados, o estado de saúde de cada um aparece aqui."
          />
        </Card>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: 10,
          }}
        >
          {molds.map((m) => {
            const score = m.health?.score_0_100 ?? 0;
            const tone =
              m.health?.risk_category === 'red'
                ? 'red'
                : m.health?.risk_category === 'yellow'
                  ? 'yellow'
                  : 'green';
            const label =
              tone === 'red' ? 'Crítico' : tone === 'yellow' ? 'Aviso' : 'OK';
            return (
              <Card key={m.id} padding={14}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    marginBottom: 12,
                  }}
                >
                  <span
                    style={{
                      fontSize: 13,
                      color: 'var(--fg-0)',
                      fontWeight: 600,
                    }}
                  >
                    {m.name ?? m.mold_code}
                  </span>
                  <span
                    style={{
                      padding: '1px 7px',
                      fontSize: 10.5,
                      borderRadius: 999,
                      color: `var(--${tone})`,
                      background: `var(--${tone}-bg)`,
                      border: `1px solid var(--${tone}-bd)`,
                    }}
                  >
                    {label}
                  </span>
                </div>
                <div
                  className="tabular display"
                  style={{
                    fontSize: 22,
                    color: 'var(--fg-0)',
                    fontWeight: 600,
                    marginBottom: 6,
                  }}
                >
                  {score.toFixed(0)}
                  <span
                    style={{
                      fontSize: 12,
                      color: 'var(--fg-3)',
                      fontWeight: 400,
                    }}
                  >
                    /100 health
                  </span>
                </div>
                <MiniBar
                  value={score}
                  max={100}
                  color={`var(--${tone})`}
                  height={4}
                />
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    marginTop: 10,
                    fontSize: 11,
                    color: 'var(--fg-2)',
                  }}
                >
                  <span>
                    Pockets:{' '}
                    <strong style={{ color: 'var(--fg-1)' }}>
                      {m.pocket_count}
                    </strong>
                  </span>
                  <span>
                    Vida:{' '}
                    <strong style={{ color: 'var(--fg-1)' }}>
                      {m.expected_life_cycles ?? '—'}
                    </strong>
                  </span>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}

// ─── RetrabalhoTab ───────────────────────────────────────────────────────

const REWORK_ERROR_CODES = [
  { code: 'RESIN_BUBBLE', label: 'Bolha na resina' },
  { code: 'PAINT_SCRATCH', label: 'Risco na pintura' },
  { code: 'COLAGEM_FAIL', label: 'Falha na colagem' },
  { code: 'LAMINATE_DEFECT', label: 'Defeito de laminagem' },
  { code: 'DIMENSION_OFF', label: 'Dimensão fora de tolerância' },
  { code: 'OTHER', label: 'Outro' },
];
const ROOT_CAUSE_CATEGORIES = [
  'Erro de operador',
  'Molde danificado',
  'Material defeituoso',
  'Procedimento incorreto',
  'Equipamento',
  'Outro',
];

const FIELD_CLASS =
  'mt-1 w-full px-3 py-2 rounded-md text-sm outline-none ' +
  'text-slate-900 placeholder:text-slate-400';
const FIELD_STYLE = {
  background: '#f1f5f9',
  border: '1px solid var(--bd-2)',
} as const;

function RetrabalhoTab() {
  const queryClient = useQueryClient();
  const reworkQuery = useReworkList();
  const rework = reworkQuery.data ?? [];

  const [ofId, setOfId] = useState('');
  const [errorCode, setErrorCode] = useState('');
  const [phaseCauser, setPhaseCauser] = useState('');
  const [rootCause, setRootCause] = useState('');
  const [costEur, setCostEur] = useState('');
  const [description, setDescription] = useState('');
  const [causerEmployeeId, setCauserEmployeeId] = useState('');
  const [saved, setSaved] = useState(false);

  const employeesQuery = useQuery({
    queryKey: ['qualidade', 'rework-employees'],
    queryFn: () => employeesApi.list({ limit: 200 }),
    staleTime: 5 * 60_000,
    retry: 0,
  });
  const employees: { id: string; label: string }[] = useMemo(() => {
    const raw =
      (employeesQuery.data as { data?: unknown } | undefined)?.data ??
      employeesQuery.data;
    if (!Array.isArray(raw)) return [];
    return raw
      .map((e: Record<string, unknown>) => {
        const id = e.id ?? e.employee_id;
        if (!id) return null;
        const name =
          [e.first_name, e.last_name].filter(Boolean).join(' ') ||
          (e.full_name as string) ||
          (e.name as string) ||
          String(id).slice(0, 8);
        return { id: String(id), label: String(name) };
      })
      .filter((x): x is { id: string; label: string } => x !== null);
  }, [employeesQuery.data]);

  const mutation = useMutation({
    mutationFn: (payload: ReworkCreatePayload) =>
      qualityReworkApi.create(payload),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 3_000);
      setOfId('');
      setErrorCode('');
      setPhaseCauser('');
      setRootCause('');
      setCostEur('');
      setDescription('');
      setCauserEmployeeId('');
      queryClient.invalidateQueries({ queryKey: ['qualidade', 'rework'] });
      queryClient.invalidateQueries({
        queryKey: ['qualidade', 'dashboard-phase'],
      });
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!ofId.trim() || !errorCode) return;
    const cost = Number(costEur);
    mutation.mutate({
      of_id: ofId.trim(),
      error_code: errorCode,
      detected_at: new Date().toISOString(),
      phase_id_causer: phaseCauser.trim() || undefined,
      root_cause_category: rootCause || undefined,
      error_description: description.trim() || undefined,
      causer_employee_id: causerEmployeeId || undefined,
      cost_estimate_eur:
        costEur.trim() !== '' && Number.isFinite(cost) ? cost : undefined,
    });
  }

  const disabled = !ofId.trim() || !errorCode || mutation.isPending;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card padding={18}>
        <SectionHeader
          icon={<Repeat size={14} />}
          title="Registar novo retrabalho"
          subtitle="POST /v1/quality/rework · QA01"
        />
        {saved ? (
          <div
            style={{
              padding: '8px 12px',
              marginBottom: 12,
              background: 'var(--green-bg)',
              border: '1px solid var(--green-bd)',
              borderRadius: 'var(--r-sm)',
              color: 'var(--green)',
              fontSize: 12,
            }}
          >
            Retrabalho registado com sucesso.
          </div>
        ) : null}
        {mutation.isError ? (
          <div
            style={{
              padding: '8px 12px',
              marginBottom: 12,
              background: 'var(--red-bg)',
              border: '1px solid var(--red-bd)',
              borderRadius: 'var(--r-sm)',
              color: 'var(--red)',
              fontSize: 12,
            }}
          >
            Não foi possível registar o retrabalho. Tenta de novo.
          </div>
        ) : null}
        <form
          onSubmit={handleSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: 12 }}
        >
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 12,
            }}
          >
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Ordem (OF) *
              </span>
              <input
                type="text"
                value={ofId}
                onChange={(e) => setOfId(e.target.value.toUpperCase())}
                placeholder="OF-12345"
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
                required
              />
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Tipo de defeito *
              </span>
              <select
                value={errorCode}
                onChange={(e) => setErrorCode(e.target.value)}
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
                required
              >
                <option value="">Escolher…</option>
                {REWORK_ERROR_CODES.map((c) => (
                  <option key={c.code} value={c.code}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Fase onde ocorreu
              </span>
              <input
                type="text"
                value={phaseCauser}
                onChange={(e) => setPhaseCauser(e.target.value)}
                placeholder="Ex: Laminagem"
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
              />
            </label>
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 12,
            }}
          >
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Causa-raiz
              </span>
              <select
                value={rootCause}
                onChange={(e) => setRootCause(e.target.value)}
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
              >
                <option value="">Escolher…</option>
                {ROOT_CAUSE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Operador responsável
              </span>
              <select
                value={causerEmployeeId}
                onChange={(e) => setCauserEmployeeId(e.target.value)}
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
              >
                <option value="">Escolher…</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.label}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
                Custo estimado (€)
              </span>
              <input
                type="number"
                value={costEur}
                onChange={(e) => setCostEur(e.target.value)}
                placeholder="0"
                min="0"
                step="0.01"
                className={`${FIELD_CLASS}`}
                style={FIELD_STYLE}
              />
            </label>
          </div>
          <label style={{ display: 'block' }}>
            <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
              Descrição
            </span>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="O que aconteceu…"
              className={`${FIELD_CLASS}`}
              style={FIELD_STYLE}
            />
          </label>
          <div>
            <button
              type="submit"
              disabled={disabled}
              style={{
                padding: '8px 16px',
                height: 36,
                background: disabled ? 'var(--bg-3)' : 'var(--blue)',
                color: disabled ? 'var(--fg-3)' : '#fff',
                border: 'none',
                borderRadius: 9,
                fontSize: 12.5,
                fontWeight: 500,
                cursor: disabled ? 'not-allowed' : 'pointer',
              }}
            >
              {mutation.isPending ? 'A registar…' : 'Registar retrabalho'}
            </button>
          </div>
        </form>
      </Card>

      <Card padding={18}>
        <SectionHeader
          title="Retrabalho registado"
          subtitle={`${rework.length} registos`}
        />
        {reworkQuery.isLoading ? (
          <LoadingLine />
        ) : rework.length === 0 ? (
          <EmptyState
            size="sm"
            title="Sem retrabalho registado"
            hint="Usa o formulário acima para registar o primeiro retrabalho."
          />
        ) : (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '110px 1fr 130px 100px 90px',
                padding: '10px 6px',
                borderBottom: '1px solid var(--bd-1)',
                background: 'var(--bg-2)',
                fontSize: 10.5,
                color: 'var(--fg-3)',
                textTransform: 'uppercase',
                letterSpacing: 0.4,
                fontWeight: 600,
              }}
            >
              <div>OF</div>
              <div>Defeito</div>
              <div>Fase</div>
              <div style={{ textAlign: 'right' }}>Custo</div>
              <div style={{ textAlign: 'right' }}>Estado</div>
            </div>
            {rework.slice(0, 30).map((r, i, arr) => (
              <div
                key={r.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '110px 1fr 130px 100px 90px',
                  alignItems: 'center',
                  padding: '10px 6px',
                  borderBottom:
                    i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
                  fontSize: 12,
                }}
              >
                <span style={{ color: 'var(--fg-0)', fontWeight: 500 }}>
                  {r.of_id}
                </span>
                <span style={{ color: 'var(--fg-2)' }}>
                  {r.error_description ?? r.error_code}
                </span>
                <span style={{ color: 'var(--fg-2)' }}>
                  {r.phase_id_causer ?? '—'}
                </span>
                <span
                  className="tabular"
                  style={{ color: 'var(--red)', textAlign: 'right' }}
                >
                  {r.cost_estimate_eur
                    ? `−€${Math.round(r.cost_estimate_eur)}`
                    : '—'}
                </span>
                <span
                  style={{
                    justifySelf: 'end',
                    fontSize: 10.5,
                    padding: '1px 7px',
                    borderRadius: 999,
                    color: r.resolved_at ? 'var(--green)' : 'var(--orange)',
                    background: r.resolved_at
                      ? 'var(--green-bg)'
                      : 'var(--orange-bg)',
                    border: `1px solid ${r.resolved_at ? 'var(--green-bd)' : 'var(--orange-bd)'}`,
                  }}
                >
                  {r.resolved_at ? 'Resolvido' : 'Aberto'}
                </span>
              </div>
            ))}
          </>
        )}
      </Card>
    </div>
  );
}

// ─── AderenciaTab ────────────────────────────────────────────────────────

function AderenciaTab() {
  // /v1/plan/adherence é PARTIAL — degrada com honestidade.
  const adherenceQuery = useQuery({
    queryKey: ['qualidade', 'adherence'],
    queryFn: () =>
      apiFetch<unknown>('/v1/plan/adherence').catch(() => ({
        status: 'sem_execucao_real',
      })),
    staleTime: 60_000,
    retry: 0,
  });
  const honest = useHonestEmptyState(adherenceQuery.data);

  return (
    <Card padding={20}>
      <SectionHeader
        icon={<Target size={14} />}
        title="Aderência ao plano · ScheduleCommit × OF_FP"
        subtitle="Fecha o ciclo: planeei → aconteceu → aprendi"
      />
      <EmptyState
        title="Aderência ao plano indisponível"
        hint={
          honest.degraded
            ? honest.reason
            : 'O cálculo de aderência (plano vs realizado por fase) ainda não tem execução real registada. Aparece assim que houver ScheduleCommits cruzáveis com OF_FP.'
        }
      />
    </Card>
  );
}

// ─── DiagnosticoTab ──────────────────────────────────────────────────────

function DiagnosticoTab() {
  const [errorCode, setErrorCode] = useState('RESIN_BUBBLE');
  const rootCauseQuery = useQuery({
    queryKey: ['qualidade', 'root-cause', errorCode],
    queryFn: () =>
      apiFetch<Record<string, unknown>>(
        `/v1/quality/root-cause?error_code=${encodeURIComponent(errorCode)}`,
      ),
    staleTime: 60_000,
    retry: 0,
    enabled: errorCode.length > 0,
  });
  const impactQuery = useQuery({
    queryKey: ['qualidade', 'impact', errorCode],
    queryFn: () =>
      apiFetch<Record<string, unknown>>(
        `/v1/quality/impact?error_code=${encodeURIComponent(errorCode)}`,
      ),
    staleTime: 60_000,
    retry: 0,
    enabled: errorCode.length > 0,
  });

  const rc = rootCauseQuery.data;
  const dimensions =
    rc && typeof rc === 'object'
      ? (rc as { dimensions?: Record<string, unknown> }).dimensions
      : undefined;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card padding={18}>
        <SectionHeader
          icon={<Brain size={14} />}
          title="Diagnóstico causal · RootCauseAnalyzer"
          subtitle="Causa comum por dimensão · escolhe o código de erro"
        />
        <label style={{ display: 'block', maxWidth: 280 }}>
          <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
            Código de erro
          </span>
          <select
            value={errorCode}
            onChange={(e) => setErrorCode(e.target.value)}
            className={FIELD_CLASS}
            style={FIELD_STYLE}
          >
            {REWORK_ERROR_CODES.map((c) => (
              <option key={c.code} value={c.code}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
      </Card>

      <Card padding={18}>
        <SectionHeader
          title="Causa-raiz por dimensão"
          subtitle="RootCauseAnalyzer · top causas por fase / molde / operador"
        />
        {rootCauseQuery.isLoading ? (
          <LoadingLine />
        ) : rootCauseQuery.isError ? (
          <EmptyState
            size="sm"
            title="Diagnóstico indisponível"
            hint="O serviço de causa-raiz não respondeu para este código de erro."
          />
        ) : !dimensions || Object.keys(dimensions).length === 0 ? (
          <EmptyState
            size="sm"
            title="Sem dados de causa-raiz"
            hint="Não há retrabalho suficiente com este código de erro para diagnosticar uma causa-raiz."
          />
        ) : (
          <pre
            style={{
              margin: 0,
              fontFamily: 'Geist Mono, ui-monospace, monospace',
              fontSize: 11.5,
              lineHeight: 1.7,
              color: 'var(--fg-1)',
              background: 'var(--bg-2)',
              borderRadius: 'var(--r-sm)',
              padding: 12,
              overflowX: 'auto',
            }}
          >
            {JSON.stringify(dimensions, null, 2)}
          </pre>
        )}
      </Card>

      <Card padding={18}>
        <SectionHeader
          title="Impacto do erro"
          subtitle="ImpactService · custo e horas perdidas"
        />
        {impactQuery.isLoading ? (
          <LoadingLine />
        ) : impactQuery.isError || !impactQuery.data ? (
          <EmptyState
            size="sm"
            title="Sem dados de impacto"
            hint="Não há registos com este código de erro para calcular o impacto."
          />
        ) : (
          <pre
            style={{
              margin: 0,
              fontFamily: 'Geist Mono, ui-monospace, monospace',
              fontSize: 11.5,
              lineHeight: 1.7,
              color: 'var(--fg-1)',
              background: 'var(--bg-2)',
              borderRadius: 'var(--r-sm)',
              padding: 12,
              overflowX: 'auto',
            }}
          >
            {JSON.stringify(impactQuery.data, null, 2)}
          </pre>
        )}
      </Card>
    </div>
  );
}

// ─── OeeTab ──────────────────────────────────────────────────────────────

function OeeTab() {
  const oeeQuery = useQuery<OeeResponse>({
    queryKey: ['qualidade', 'oee-phase'],
    queryFn: () =>
      apiFetch<OeeResponse>('/v1/profit/oee?group_by=phase'),
    staleTime: 5 * 60_000,
    retry: 0,
  });

  const overall = oeeQuery.data?.overall;
  const breakdown = oeeQuery.data?.breakdown ?? [];

  return (
    <>
      <Card padding={20} style={{ marginBottom: 14 }}>
        <SectionHeader
          icon={<TrendingUp size={14} />}
          title="OEE global"
          subtitle="Disponibilidade × Performance × Qualidade · OF_FP"
        />
        {oeeQuery.isLoading ? (
          <LoadingLine />
        ) : !overall ? (
          <EmptyState
            size="sm"
            title="Sem dados de OEE"
            hint="Não há operações suficientes no histórico para calcular o OEE."
          />
        ) : (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 14,
                marginBottom: 16,
              }}
            >
              {[
                { v: overall.oee, l: 'OEE Global' },
                { v: overall.availability, l: 'Disponibilidade' },
                { v: overall.performance, l: 'Performance' },
                { v: overall.quality, l: 'Qualidade' },
              ].map((r) => (
                <div
                  key={r.l}
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <OEERing value={r.v * 100} />
                  <div style={{ fontSize: 11, color: 'var(--fg-2)' }}>
                    {r.l}
                  </div>
                </div>
              ))}
            </div>
            <Banner tone="orange">
              <AlertCircle size={18} color="var(--orange)" />
              <div>
                <div
                  style={{
                    fontSize: 13,
                    color: 'var(--fg-0)',
                    fontWeight: 500,
                  }}
                >
                  OEE calculado de {overall.sample_size} operações reais (
                  {overall.sample_excluded} excluídas)
                </div>
                <div
                  style={{
                    fontSize: 11.5,
                    color: 'var(--fg-2)',
                    marginTop: 3,
                  }}
                >
                  Os tempos vêm do histórico real (FaseOf_Inicio→Fim). Os
                  tempos standard divergem até 25× do real e não são usados na
                  baseline.
                </div>
              </div>
            </Banner>
          </>
        )}
      </Card>

      <Card padding={0}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.6fr 80px 1fr 1fr 1fr 80px',
            alignItems: 'center',
            gap: 12,
            padding: '12px 18px',
            borderBottom: '1px solid var(--bd-1)',
            background: 'var(--bg-2)',
            fontSize: 10.5,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
          }}
        >
          <div>Fase</div>
          <div>OEE</div>
          <div>Disp.</div>
          <div>Perf.</div>
          <div>Qual.</div>
          <div style={{ textAlign: 'right' }}>Amostra</div>
        </div>
        {oeeQuery.isLoading ? (
          <div style={{ padding: 18 }}>
            <LoadingLine />
          </div>
        ) : breakdown.length === 0 ? (
          <div style={{ padding: 18 }}>
            <EmptyState
              size="sm"
              title="Sem OEE por fase"
              hint="Não há operações agrupáveis por fase no histórico."
            />
          </div>
        ) : (
          breakdown.map((p, i, arr) => {
            const oeePct = p.oee * 100;
            const tone =
              oeePct >= 60
                ? 'green'
                : oeePct >= 40
                  ? 'yellow'
                  : oeePct >= 20
                    ? 'orange'
                    : 'red';
            return (
              <div
                key={p.group_value + i}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.6fr 80px 1fr 1fr 1fr 80px',
                  alignItems: 'center',
                  gap: 12,
                  padding: '12px 18px',
                  borderBottom:
                    i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
                }}
              >
                <span
                  style={{
                    fontSize: 12.5,
                    color: 'var(--fg-0)',
                    fontWeight: 500,
                  }}
                >
                  {p.group_value}
                </span>
                <span
                  className="tabular display"
                  style={{
                    fontSize: 16,
                    color: `var(--${tone})`,
                    fontWeight: 600,
                  }}
                >
                  {oeePct.toFixed(1)}%
                </span>
                <MiniBar
                  value={p.availability * 100}
                  color="var(--green)"
                  height={3}
                />
                <MiniBar
                  value={p.performance * 100}
                  color={
                    p.performance < 0.3 ? 'var(--red)' : 'var(--yellow)'
                  }
                  height={3}
                />
                <MiniBar
                  value={p.quality * 100}
                  color="var(--blue)"
                  height={3}
                />
                <span
                  className="tabular"
                  style={{
                    fontSize: 11,
                    color: 'var(--fg-3)',
                    textAlign: 'right',
                  }}
                >
                  {p.sample_size}
                </span>
              </div>
            );
          })
        )}
      </Card>
    </>
  );
}

// ─── CustosTab ───────────────────────────────────────────────────────────

function CustosTab() {
  const reworkQuery = useReworkList();
  const rework = reworkQuery.data ?? [];
  const totalCost = rework.reduce(
    (s, r) => s + (r.cost_estimate_eur ?? 0),
    0,
  );
  const resolvedCost = rework
    .filter((r) => r.resolved_at)
    .reduce((s, r) => s + (r.cost_estimate_eur ?? 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card padding={18}>
        <SectionHeader
          icon={<Euro size={14} />}
          title="Custo de retrabalho registado"
          subtitle="Soma de cost_estimate_eur · ReworkEntry"
        />
        {reworkQuery.isLoading ? (
          <LoadingLine />
        ) : rework.length === 0 ? (
          <EmptyState
            size="sm"
            title="Sem custos de retrabalho"
            hint="Quando houver registos de retrabalho com custo, o total aparece aqui."
          />
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: 12,
            }}
          >
            <KpiTile
              label="Custo total registado"
              value={`€${Math.round(totalCost).toLocaleString('pt-PT')}`}
              tone="red"
            />
            <KpiTile
              label="Custo de itens resolvidos"
              value={`€${Math.round(resolvedCost).toLocaleString('pt-PT')}`}
              tone="green"
            />
            <KpiTile
              label="Registos"
              value={`${rework.length}`}
              tone="neutral"
            />
          </div>
        )}
      </Card>

      <Card padding={20}>
        <SectionHeader
          title="ROI de acções de qualidade"
          subtitle="Investido vs poupado por acção"
        />
        <EmptyState
          title="ROI de qualidade ainda não disponível"
          hint="O cálculo de retorno (investido vs poupado) de cada acção de qualidade precisa de um endpoint dedicado que ainda não existe. Até lá, não inventamos os números — o custo de retrabalho real está acima."
        />
      </Card>
    </div>
  );
}

// ─── Helpers de UI ───────────────────────────────────────────────────────

function LoadingLine() {
  return (
    <div
      style={{
        padding: '20px 0',
        textAlign: 'center',
        color: 'var(--fg-3)',
        fontSize: 12,
      }}
    >
      A carregar…
    </div>
  );
}

function KpiTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'red' | 'green' | 'neutral';
}) {
  const color =
    tone === 'red'
      ? 'var(--red)'
      : tone === 'green'
        ? 'var(--green)'
        : 'var(--fg-0)';
  return (
    <div
      style={{
        padding: 14,
        background: 'var(--bg-2)',
        borderRadius: 'var(--r-md)',
        border: '1px solid var(--bd-1)',
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
        }}
      >
        {label}
      </div>
      <div
        className="tabular display"
        style={{
          fontSize: 22,
          color,
          fontWeight: 600,
          marginTop: 6,
        }}
      >
        {value}
      </div>
    </div>
  );
}
