/**
 * QualidadePage — página "Qualidade" · Q.52.I.
 *
 * Reconstrução fiel do protótipo NELO.html (page-qualidade.jsx): 10
 * tabs — Resumo, Predições, Mapa do casco, Erros, Moldes, Retrabalho,
 * Aderência, Diagnóstico, OEE, Custos vs Ganhos.
 *
 * ZERO MOCKS — cada tab liga a endpoints REAIS:
 *   /v1/quality/{dashboard,first-pass-yield,by-supplier,by-lot,
 *               workers/ranking,rework,root-cause,impact,
 *               defect-risk,defect-zones,roi-actions}
 *   /v1/profit/oee?group_by=phase · /v1/plan/molds/{*} · /v1/plan/adherence
 *
 * Q.53.H — as tabs Predições, Mapa do casco, Aderência e ROI passaram de
 * empty state honesto a dados reais: Q.53.A serviu defect-risk (ML
 * QualityRiskModel), defect-zones e roi-actions; Q.44.B serviu
 * /v1/plan/adherence. Quando um endpoint degrada (modelo sem treino, ERP
 * desligado, sem commit) a tab mostra o empty state honesto da resposta.
 *
 * Átomos da Onda 0 (KPIBig, OEERing, RiskBadge) reutilizados; primitivas
 * locais (Card, SectionHeader, MiniBar, HullHeatmap, Banner) em
 * components/qualidade/QualidadeBits.tsx; fetchers Q.53.H em
 * components/qualidade/qualidadeApi.ts.
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
  RiskBadge,
} from '../../components/dark';
import {
  Card,
  SectionHeader,
  MiniBar,
  Banner,
  HullHeatmap,
  type HullZone,
} from '../../components/qualidade/QualidadeBits';
import {
  fetchDefectRisk,
  fetchDefectZones,
  fetchRoiActions,
  fetchAdherence,
  type DefectZone,
  type HullZoneId,
} from '../../components/qualidade/qualidadeApi';
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

/** Q.54.S — molde real do ERP com o seu histórico de defeitos. */
interface MoldQuality {
  molde_id: string;
  nome: string | null;
  tipo: string | null;
  em_manutencao: boolean;
  defect_events: number;
  defect_qty: number;
  last_defect: string | null;
}

/**
 * Q.54.S — moldes reais (factory_curated.mold) cruzados com os eventos de
 * qualidade. Distinto de `useMolds`, que serve o catálogo de planeamento
 * (`plan.mold`) cujo espaço de IDs não casa com os dados de defeitos.
 */
function useMoldQuality() {
  return useQuery<MoldQuality[]>({
    queryKey: ['qualidade', 'mold-quality'],
    queryFn: () => apiFetch<MoldQuality[]>('/v1/quality/molds?limit=60'),
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
  // Q.53.H — GET /v1/quality/defect-risk: scoring do QualityRiskModel
  // sobre cada barco em produção. Degrada com model_available=false.
  const riskQuery = useQuery({
    queryKey: ['qualidade', 'defect-risk'],
    queryFn: () => fetchDefectRisk(50),
    staleTime: 60_000,
    retry: 0,
  });

  if (riskQuery.isLoading) {
    return (
      <Card padding={20}>
        <SectionHeader
          icon={<Brain size={14} />}
          title="Risco preditivo de defeito por barco"
          subtitle="QualityRiskModel · scoring por barco em produção"
        />
        <LoadingLine />
      </Card>
    );
  }

  if (riskQuery.isError) {
    return (
      <Card padding={20}>
        <SectionHeader
          icon={<Brain size={14} />}
          title="Risco preditivo de defeito por barco"
          subtitle="QualityRiskModel · scoring por barco em produção"
        />
        <EmptyState
          title="Predições indisponíveis"
          hint="O endpoint /v1/quality/defect-risk não respondeu. Tenta atualizar dentro de momentos."
        />
      </Card>
    );
  }

  const data = riskQuery.data;
  const orders = data?.orders ?? [];

  // Modelo sem treino possível (histórico insuficiente) — empty honesto.
  if (data && data.model_available === false) {
    return (
      <Card padding={20}>
        <SectionHeader
          icon={<Brain size={14} />}
          title="Risco preditivo de defeito por barco"
          subtitle="QualityRiskModel · scoring por barco em produção"
        />
        <EmptyState
          title="Modelo de risco ainda não disponível"
          hint={
            data.reason ??
            'Não há histórico de qualidade suficiente para treinar o QualityRiskModel.'
          }
        />
      </Card>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
        }}
      >
        <KpiTile
          label="Barcos avaliados"
          value={`${data?.total_orders ?? orders.length}`}
          tone="neutral"
        />
        <KpiTile
          label="Risco alto"
          value={`${data?.high_risk_count ?? orders.filter((o) => o.risk_band === 'alto').length}`}
          tone="red"
        />
        <KpiTile
          label="Risco baixo"
          value={`${orders.filter((o) => o.risk_band === 'baixo').length}`}
          tone="green"
        />
      </div>

      <Card padding={0}>
        <div style={{ padding: '14px 18px 0 18px' }}>
          <SectionHeader
            icon={<Brain size={14} />}
            title="Risco preditivo de defeito por barco"
            subtitle="QualityRiskModel · P(defeito) na fase actual · maior risco primeiro"
          />
        </div>
        {orders.length === 0 ? (
          <div style={{ padding: 18 }}>
            <EmptyState
              size="sm"
              title="Sem barcos em produção"
              hint="O modelo está activo mas não há ordens em curso para avaliar."
            />
          </div>
        ) : (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '120px 1fr 1fr 90px',
                padding: '10px 18px',
                borderBottom: '1px solid var(--bd-1)',
                background: 'var(--bg-2)',
                fontSize: 10.5,
                color: 'var(--fg-3)',
                textTransform: 'uppercase',
                letterSpacing: 0.4,
                fontWeight: 600,
              }}
            >
              <div>Barco (OF)</div>
              <div>Produto</div>
              <div>Fase actual</div>
              <div style={{ textAlign: 'right' }}>Risco</div>
            </div>
            {orders.map((o, i) => (
              <div
                key={o.of_id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '120px 1fr 1fr 90px',
                  alignItems: 'center',
                  padding: '10px 18px',
                  borderBottom:
                    i < orders.length - 1
                      ? '1px solid var(--bd-1)'
                      : 'none',
                  fontSize: 12,
                }}
              >
                <span
                  className="tabular"
                  style={{ color: 'var(--fg-0)', fontWeight: 500 }}
                >
                  {o.of_id}
                </span>
                <span style={{ color: 'var(--fg-1)' }}>
                  {o.product_name ?? o.product_type ?? '—'}
                </span>
                <span style={{ color: 'var(--fg-2)' }}>
                  {o.current_phase_name ?? o.current_phase_id ?? '—'}
                </span>
                <span style={{ justifySelf: 'end' }}>
                  <RiskBadge value={o.defect_probability} />
                </span>
              </div>
            ))}
          </>
        )}
      </Card>
    </div>
  );
}

// ─── MapaTab ─────────────────────────────────────────────────────────────

// Geometria das 8 zonas canónicas do casco sobre o viewBox 0 0 400 86 do
// HullHeatmap. As chaves espelham HULL_ZONE_IDS do backend.
const ZONE_GEOMETRY: Record<
  HullZoneId,
  { label: string; x: number; y: number; w: number; h: number }
> = {
  casco: { label: 'Casco', x: 70, y: 30, w: 78, h: 26 },
  conves: { label: 'Convés', x: 152, y: 30, w: 70, h: 11 },
  cockpit: { label: 'Cockpit', x: 152, y: 44, w: 70, h: 12 },
  interior: { label: 'Interior', x: 226, y: 30, w: 64, h: 26 },
  acabamento: { label: 'Acabamento', x: 294, y: 30, w: 56, h: 26 },
  molde: { label: 'Molde', x: 28, y: 30, w: 38, h: 26 },
  montagem: { label: 'Montagem', x: 354, y: 32, w: 30, h: 22 },
  outro: { label: 'Outro', x: 152, y: 58, w: 70, h: 0 },
};

function MapaTab() {
  // Q.53.H — GET /v1/quality/defect-zones: agregação de retrabalho por
  // zona do casco. Sempre devolve as 8 zonas canónicas (count 0 quando
  // limpa), por isso o SVG renderiza o casco completo.
  const zonesQuery = useQuery({
    queryKey: ['qualidade', 'defect-zones'],
    queryFn: () => fetchDefectZones(),
    staleTime: 60_000,
    retry: 0,
  });

  const header = (
    <SectionHeader
      icon={<Layers size={14} />}
      title="Mapa de defeitos por zona do casco"
      subtitle="DefectZoneService · onde o defeito ocorre, não só quanto"
    />
  );

  if (zonesQuery.isLoading) {
    return (
      <Card padding={20}>
        {header}
        <LoadingLine />
      </Card>
    );
  }

  if (zonesQuery.isError || !zonesQuery.data) {
    return (
      <Card padding={20}>
        {header}
        <EmptyState
          title="Mapa do casco indisponível"
          hint="O endpoint /v1/quality/defect-zones não respondeu. Tenta atualizar dentro de momentos."
        />
      </Card>
    );
  }

  const data = zonesQuery.data;
  // O HullHeatmap só desenha as zonas com geometria posicionável; a zona
  // "outro" (sem localização no casco) é listada à parte na tabela.
  const heatmapZones: HullZone[] = data.zones
    .filter((z): z is DefectZone => z.zone in ZONE_GEOMETRY && z.zone !== 'outro')
    .map((z) => {
      const g = ZONE_GEOMETRY[z.zone];
      return {
        id: z.zone,
        label: g.label,
        x: g.x,
        y: g.y,
        w: g.w,
        h: g.h,
        count: z.events,
      };
    });

  const ranked = [...data.zones].sort((a, b) => b.events - a.events);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card padding={20}>
        {header}
        {data.total_events === 0 ? (
          <EmptyState
            size="sm"
            title="Sem defeitos registados na janela"
            hint="Não há eventos de retrabalho nos últimos 90 dias para mapear no casco."
          />
        ) : (
          <HullHeatmap zones={heatmapZones} />
        )}
      </Card>

      <Card padding={18}>
        <SectionHeader
          title="Defeitos por zona"
          subtitle={`${data.total_events} eventos · janela de ${new Date(
            data.window.from,
          ).toLocaleDateString('pt-PT')} a ${new Date(
            data.window.to,
          ).toLocaleDateString('pt-PT')}`}
        />
        {ranked.map((z, i, arr) => {
          const tone =
            z.share_pct > 30
              ? 'red'
              : z.share_pct > 15
                ? 'orange'
                : z.share_pct > 5
                  ? 'yellow'
                  : 'green';
          return (
            <div
              key={z.zone}
              style={{
                display: 'grid',
                gridTemplateColumns: '130px 1fr 70px 80px 70px',
                alignItems: 'center',
                gap: 14,
                padding: '9px 0',
                borderBottom:
                  i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
                fontSize: 12,
              }}
            >
              <span style={{ color: 'var(--fg-0)', fontWeight: 500 }}>
                {ZONE_GEOMETRY[z.zone]?.label ?? z.zone}
              </span>
              <MiniBar
                value={z.share_pct}
                max={60}
                color={`var(--${tone})`}
                height={5}
              />
              <span
                className="tabular"
                style={{ color: `var(--${tone})`, fontWeight: 600 }}
              >
                {z.share_pct.toFixed(1)}%
              </span>
              <span
                className="tabular"
                style={{ color: 'var(--red)', textAlign: 'right' }}
              >
                {z.cost_eur > 0 ? `−€${Math.round(z.cost_eur)}` : '—'}
              </span>
              <span
                className="tabular"
                style={{ color: 'var(--fg-2)', textAlign: 'right' }}
              >
                {z.events} ev.
              </span>
            </div>
          );
        })}
      </Card>
    </div>
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
  const moldsQuery = useMoldQuality();
  const molds = moldsQuery.data ?? [];
  const maxQty = molds.reduce((acc, m) => Math.max(acc, m.defect_qty), 0);

  return (
    <>
      <Card padding={18} style={{ marginBottom: 14 }}>
        <SectionHeader
          icon={<Wrench size={14} />}
          title="Defeitos por molde"
          subtitle="Moldes reais do ERP × eventos de qualidade · pior primeiro"
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
            title="Sem moldes com histórico de defeitos"
            hint="Os moldes aparecem aqui quando há eventos de qualidade associados."
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
            // Tom relativo: o molde com mais defeitos puxa a escala.
            const tone =
              maxQty > 0 && m.defect_qty >= maxQty * 0.6
                ? 'red'
                : maxQty > 0 && m.defect_qty >= maxQty * 0.25
                  ? 'yellow'
                  : 'green';
            return (
              <Card key={m.molde_id} padding={14}>
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    marginBottom: 12,
                    gap: 6,
                  }}
                >
                  <span
                    style={{
                      fontSize: 13,
                      color: 'var(--fg-0)',
                      fontWeight: 600,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={m.tipo ?? m.nome ?? m.molde_id}
                  >
                    {m.tipo ?? m.nome ?? `Molde ${m.molde_id}`}
                  </span>
                  {m.em_manutencao && (
                    <span
                      style={{
                        padding: '1px 7px',
                        fontSize: 10.5,
                        borderRadius: 999,
                        color: 'var(--yellow)',
                        background: 'var(--yellow-bg)',
                        border: '1px solid var(--yellow-bd)',
                        flexShrink: 0,
                      }}
                    >
                      Manutenção
                    </span>
                  )}
                </div>
                <div
                  className="tabular display"
                  style={{
                    fontSize: 22,
                    color: `var(--${tone})`,
                    fontWeight: 600,
                    marginBottom: 6,
                  }}
                >
                  {m.defect_qty.toLocaleString('pt-PT')}
                  <span
                    style={{
                      fontSize: 12,
                      color: 'var(--fg-3)',
                      fontWeight: 400,
                    }}
                  >
                    {' '}
                    defeitos
                  </span>
                </div>
                <MiniBar
                  value={m.defect_qty}
                  max={maxQty || 1}
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
                    Eventos:{' '}
                    <strong style={{ color: 'var(--fg-1)' }}>
                      {m.defect_events}
                    </strong>
                  </span>
                  <span>
                    Último:{' '}
                    <strong style={{ color: 'var(--fg-1)' }}>
                      {m.last_defect
                        ? new Date(m.last_defect).toLocaleDateString('pt-PT', {
                            day: '2-digit',
                            month: 'short',
                          })
                        : '—'}
                    </strong>
                  </span>
                </div>
                <div
                  style={{ marginTop: 6, fontSize: 10, color: 'var(--fg-3)' }}
                >
                  molde {m.molde_id}
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
  // Q.53.H — GET /v1/plan/adherence: compara o ScheduleCommit mais recente
  // com o OF_FP real. Degrada com honestidade via `status` quando o ERP
  // está desligado ou o commit não tem plano temporal.
  const adherenceQuery = useQuery({
    queryKey: ['qualidade', 'adherence'],
    queryFn: () => fetchAdherence(),
    staleTime: 60_000,
    retry: 0,
  });

  const header = (
    <SectionHeader
      icon={<Target size={14} />}
      title="Aderência ao plano · ScheduleCommit × OF_FP"
      subtitle="Fecha o ciclo: planeei → aconteceu → aprendi"
    />
  );

  if (adherenceQuery.isLoading) {
    return (
      <Card padding={20}>
        {header}
        <LoadingLine />
      </Card>
    );
  }

  const data = adherenceQuery.data;

  // null = endpoint deu 404: ainda não há nenhum ScheduleCommit.
  if (adherenceQuery.isError || data === null || data === undefined) {
    return (
      <Card padding={20}>
        {header}
        <EmptyState
          title="Sem plano para comparar"
          hint={
            adherenceQuery.isError
              ? 'O endpoint /v1/plan/adherence não respondeu. Tenta atualizar dentro de momentos.'
              : 'Ainda não há nenhum ScheduleCommit. Gera um plano no CPO para poderes medir a aderência.'
          }
        />
      </Card>
    );
  }

  // Degradação honesta: ERP desligado ou commit sem horas.
  if (data.status !== 'ok') {
    return (
      <Card padding={20}>
        {header}
        <EmptyState
          title={
            data.status === 'sem_execucao_real'
              ? 'Sem execução real para comparar'
              : 'Commit sem plano temporal'
          }
          hint={
            data.detail ??
            'O cálculo de aderência não tem dados suficientes para este commit.'
          }
        />
      </Card>
    );
  }

  const phaseDeviations = data.phase_deviations ?? [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card padding={20}>
        {header}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12,
          }}
        >
          <KpiTile
            label="Aderência"
            value={`${(data.adherence_pct ?? 0).toFixed(1)}%`}
            tone={
              (data.adherence_pct ?? 0) >= 85
                ? 'green'
                : (data.adherence_pct ?? 0) >= 60
                  ? 'neutral'
                  : 'red'
            }
          />
          <KpiTile
            label="Cobertura"
            value={`${(data.match_pct ?? 0).toFixed(1)}%`}
            tone="neutral"
          />
          <KpiTile
            label="Operações planeadas"
            value={`${data.planned_total}`}
            tone="neutral"
          />
          <KpiTile
            label="Sem execução"
            value={`${data.missing?.length ?? 0}`}
            tone={(data.missing?.length ?? 0) > 0 ? 'red' : 'green'}
          />
        </div>
        <div style={{ marginTop: 12 }}>
          <Banner tone="accent">
            <Target size={18} color="var(--accent)" />
            <div style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
              Commit{' '}
              <span className="mono" style={{ color: 'var(--fg-1)' }}>
                {data.short_sha}
              </span>{' '}
              · {data.matched_total ?? 0} de {data.planned_total} operações
              executadas · {data.within_tolerance_total ?? 0} dentro da
              tolerância de {data.tolerance_hours ?? 0}h
              {data.window
                ? ` · janela ${new Date(
                    data.window.from,
                  ).toLocaleDateString('pt-PT')}–${new Date(
                    data.window.to,
                  ).toLocaleDateString('pt-PT')}`
                : ''}
            </div>
          </Banner>
        </div>
      </Card>

      <Card padding={0}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.6fr 90px 90px 110px 110px',
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
          <div style={{ textAlign: 'right' }}>Planeado</div>
          <div style={{ textAlign: 'right' }}>Executado</div>
          <div style={{ textAlign: 'right' }}>Deriva início</div>
          <div style={{ textAlign: 'right' }}>Deriva fim</div>
        </div>
        {phaseDeviations.length === 0 ? (
          <div style={{ padding: 18 }}>
            <EmptyState
              size="sm"
              title="Sem desvios por fase"
              hint="O commit não tem operações agrupáveis por fase."
            />
          </div>
        ) : (
          phaseDeviations.map((p, i, arr) => {
            const drift = p.avg_start_drift_hours;
            const tone =
              drift === null
                ? 'fg-2'
                : Math.abs(drift) <= (data.tolerance_hours ?? 4)
                  ? 'green'
                  : Math.abs(drift) <= 24
                    ? 'orange'
                    : 'red';
            return (
              <div
                key={p.phase_id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.6fr 90px 90px 110px 110px',
                  alignItems: 'center',
                  gap: 12,
                  padding: '11px 18px',
                  borderBottom:
                    i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
                  fontSize: 12,
                }}
              >
                <span style={{ color: 'var(--fg-0)', fontWeight: 500 }}>
                  {p.phase_id}
                </span>
                <span
                  className="tabular"
                  style={{ color: 'var(--fg-2)', textAlign: 'right' }}
                >
                  {p.planned_count}
                </span>
                <span
                  className="tabular"
                  style={{ color: 'var(--fg-1)', textAlign: 'right' }}
                >
                  {p.matched_count}
                </span>
                <span
                  className="tabular"
                  style={{ color: `var(--${tone})`, textAlign: 'right' }}
                >
                  {drift !== null ? `${drift > 0 ? '+' : ''}${drift}h` : '—'}
                </span>
                <span
                  className="tabular"
                  style={{ color: 'var(--fg-2)', textAlign: 'right' }}
                >
                  {p.avg_end_drift_hours !== null
                    ? `${p.avg_end_drift_hours > 0 ? '+' : ''}${p.avg_end_drift_hours}h`
                    : '—'}
                </span>
              </div>
            );
          })
        )}
      </Card>
    </div>
  );
}

// ─── DiagnosticoTab ──────────────────────────────────────────────────────

function DiagnosticoTab() {
  // Vazio = deixa o backend escolher o defeito mais frequente da janela.
  // A tab nunca abre partida: sem código escolhido → /root-cause e /impact
  // resolvem o error_code dominante (most_frequent_error_code, Q.54.J).
  const [errorCode, setErrorCode] = useState('');

  // Os códigos de erro reais vêm dos próprios registos de retrabalho do
  // ERP — não de uma lista fixa em inglês (essa divergia dos dados reais).
  const reworkQuery = useReworkList();
  const errorCodes = useMemo(() => {
    const seen = new Map<string, string>();
    for (const r of reworkQuery.data ?? []) {
      if (r.error_code && !seen.has(r.error_code)) {
        seen.set(r.error_code, r.error_description ?? r.error_code);
      }
    }
    return [...seen.entries()].map(([code, label]) => ({ code, label }));
  }, [reworkQuery.data]);

  const qs = errorCode
    ? `?error_code=${encodeURIComponent(errorCode)}`
    : '';
  const rootCauseQuery = useQuery({
    queryKey: ['qualidade', 'root-cause', errorCode],
    queryFn: () =>
      apiFetch<Record<string, unknown>>(`/v1/quality/root-cause${qs}`),
    staleTime: 60_000,
    retry: 0,
  });
  const impactQuery = useQuery({
    queryKey: ['qualidade', 'impact', errorCode],
    queryFn: () =>
      apiFetch<Record<string, unknown>>(`/v1/quality/impact${qs}`),
    staleTime: 60_000,
    retry: 0,
  });

  const rc = rootCauseQuery.data;
  const resolvedCode =
    rc && typeof rc === 'object'
      ? ((rc as { error_code?: string | null }).error_code ?? null)
      : null;
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
        <label style={{ display: 'block', maxWidth: 360 }}>
          <span style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
            Código de erro
          </span>
          <select
            value={errorCode}
            onChange={(e) => setErrorCode(e.target.value)}
            className={FIELD_CLASS}
            style={FIELD_STYLE}
          >
            <option value="">
              Mais frequente (automático)
            </option>
            {errorCodes.map((c) => (
              <option key={c.code} value={c.code}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        {!errorCode && resolvedCode ? (
          <div
            style={{
              fontSize: 11,
              color: 'var(--fg-3)',
              marginTop: 8,
            }}
          >
            A mostrar o defeito mais frequente da janela:{' '}
            <span style={{ color: 'var(--fg-1)', fontWeight: 500 }}>
              {resolvedCode}
            </span>
          </div>
        ) : null}
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

      <RoiCard />
    </div>
  );
}

// ─── RoiCard — ROI de acções de qualidade (Q.53.H) ───────────────────────

function RoiCard() {
  // Q.53.H — GET /v1/quality/roi-actions: € poupado vs investido por
  // acção, ordenado por retorno líquido.
  const roiQuery = useQuery({
    queryKey: ['qualidade', 'roi-actions'],
    queryFn: () => fetchRoiActions(25),
    staleTime: 60_000,
    retry: 0,
  });

  const header = (
    <SectionHeader
      icon={<Euro size={14} />}
      title="ROI de acções de qualidade"
      subtitle="ROIService · investido vs poupado por código de erro"
    />
  );

  if (roiQuery.isLoading) {
    return (
      <Card padding={20}>
        {header}
        <LoadingLine />
      </Card>
    );
  }

  if (roiQuery.isError || !roiQuery.data) {
    return (
      <Card padding={20}>
        {header}
        <EmptyState
          title="ROI de qualidade indisponível"
          hint="O endpoint /v1/quality/roi-actions não respondeu. O custo de retrabalho real está no cartão acima."
        />
      </Card>
    );
  }

  const data = roiQuery.data;
  const actions = data.actions;

  if (actions.length === 0) {
    return (
      <Card padding={20}>
        {header}
        <EmptyState
          size="sm"
          title="Sem acções de qualidade para avaliar"
          hint="Não há registos de retrabalho na janela para calcular retorno."
        />
      </Card>
    );
  }

  const netTotal = data.total_saved_eur - data.total_invested_eur;

  return (
    <Card padding={20}>
      {header}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
          marginBottom: 14,
        }}
      >
        <KpiTile
          label="Poupado (total)"
          value={`€${Math.round(data.total_saved_eur).toLocaleString('pt-PT')}`}
          tone="green"
        />
        <KpiTile
          label="Investido (total)"
          value={`€${Math.round(data.total_invested_eur).toLocaleString('pt-PT')}`}
          tone="red"
        />
        <KpiTile
          label="Retorno líquido"
          value={`€${Math.round(netTotal).toLocaleString('pt-PT')}`}
          tone={netTotal >= 0 ? 'green' : 'red'}
        />
      </div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.4fr 90px 110px 110px 90px',
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
        <div>Código de erro</div>
        <div style={{ textAlign: 'right' }}>Eventos</div>
        <div style={{ textAlign: 'right' }}>Poupado</div>
        <div style={{ textAlign: 'right' }}>Investido</div>
        <div style={{ textAlign: 'right' }}>ROI</div>
      </div>
      {actions.map((a, i, arr) => {
        const tone =
          a.net_eur > 0 ? 'green' : a.net_eur < 0 ? 'red' : 'fg-2';
        return (
          <div
            key={a.error_code}
            style={{
              display: 'grid',
              gridTemplateColumns: '1.4fr 90px 110px 110px 90px',
              alignItems: 'center',
              padding: '11px 6px',
              borderBottom:
                i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
              fontSize: 12,
            }}
          >
            <span style={{ color: 'var(--fg-0)' }}>
              <span style={{ fontWeight: 500 }}>{a.error_code}</span>
              <span
                style={{
                  fontSize: 10.5,
                  color: 'var(--fg-3)',
                  marginLeft: 8,
                }}
              >
                {a.action_basis === 'fixed_corrective_action'
                  ? 'acção correctiva'
                  : 'esforço de reacção'}
              </span>
            </span>
            <span
              className="tabular"
              style={{ color: 'var(--fg-2)', textAlign: 'right' }}
            >
              {a.events}
            </span>
            <span
              className="tabular"
              style={{ color: 'var(--green)', textAlign: 'right' }}
            >
              €{Math.round(a.saved_eur).toLocaleString('pt-PT')}
            </span>
            <span
              className="tabular"
              style={{ color: 'var(--red)', textAlign: 'right' }}
            >
              €{Math.round(a.invested_eur).toLocaleString('pt-PT')}
            </span>
            <span
              className="tabular"
              style={{
                color: `var(--${tone})`,
                fontWeight: 600,
                textAlign: 'right',
              }}
            >
              {a.roi_ratio !== null ? `${a.roi_ratio.toFixed(1)}×` : '—'}
            </span>
          </div>
        );
      })}
    </Card>
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
