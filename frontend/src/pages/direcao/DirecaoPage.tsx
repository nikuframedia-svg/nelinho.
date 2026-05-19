/**
 * DirecaoPage — página "Direção" (CEO) · Q.52.E.
 *
 * Reconstrução fiel do protótipo NELO.html (page-ceo.jsx): status da
 * NELO em 30 segundos para o CEO. 4 KPIs grandes, banda objetivo (5
 * objetivos), gráfico €/dia com banda-alvo, Impacto PP1, margem por
 * país/agente e tabela CTP de encomendas activas.
 *
 * ZERO MOCKS — cada secção liga a um endpoint REAL. Endpoints PARTIAL
 * (objetivos do CEO, margem por agente, CTP) degradam com honestidade
 * via empty states explícitos. Os átomos (KPIBig, ObjectiveBar) vêm de
 * components/dark/ (Onda 0 · Q.52.B).
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  Building2,
  Download,
  Target,
  Euro,
  Sparkles,
  TrendingUp,
  Flag,
} from 'lucide-react';
import { PageHeader, KPIBig, ObjectiveBar, EmptyState } from '../../components/dark';
import {
  Card,
  SectionHeader,
  EuroBandChart,
  MarginRow,
} from '../../components/ceo/CeoBits';
import { useHonestEmptyState } from '../../hooks/useHonestEmptyState';
import {
  apiFetch,
  kpisApi,
  ceoDashboardApi,
  profitApi,
  type BacklogResponse,
} from '../../lib/api';

// ─── Tipos das respostas REAIS ──────────────────────────────────────────

interface KpiMetric {
  value: number | null;
  reason?: string | null;
}

interface KpiSnapshot {
  oee: KpiMetric;
  availability: KpiMetric;
  performance: KpiMetric;
  quality_fpy: KpiMetric;
  rework_rate: KpiMetric;
  orders_total: KpiMetric;
  orders_in_progress: KpiMetric;
  orders_completed: KpiMetric;
  updated_at: string;
}

interface ThroughputDashboard {
  date: string;
  throughput_eur: {
    today: number;
    mtd: number;
    ytd: number;
    target_min: number;
    target_max: number;
    on_target: boolean;
  };
  trend_14d: { date: string; eur: number }[];
  currency: string;
  source: string;
}

interface OtdResponse {
  window_days: number;
  otd_pct: number;
  on_time: number;
  late: number;
  total: number;
}

interface TransportBatch {
  id: string;
  code?: string;
  status?: string;
  transport_date?: string | null;
  destination?: string | null;
  truck_capacity_units?: number;
  assigned_orders?: number;
}

const STATUS_LABEL: Record<string, { label: string; tone: string }> = {
  draft: { label: 'Rascunho', tone: 'neutral' },
  planned: { label: 'Planeado', tone: 'info' },
  frozen: { label: 'Congelado', tone: 'warning' },
  dispatched: { label: 'Expedido', tone: 'success' },
};

function fmtDate(iso?: string | null): string {
  if (!iso) return '—';
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

// ─── Página ─────────────────────────────────────────────────────────────

export default function DirecaoPage() {
  const navigate = useNavigate();

  const kpiQuery = useQuery<KpiSnapshot>({
    queryKey: ['direcao', 'kpis-snapshot'],
    queryFn: () => kpisApi.getSnapshot() as Promise<KpiSnapshot>,
    staleTime: 60_000,
    retry: 0,
  });

  const throughputQuery = useQuery<ThroughputDashboard | null>({
    queryKey: ['direcao', 'throughput'],
    queryFn: () => apiFetch<ThroughputDashboard>('/v1/profit/dashboard'),
    staleTime: 60_000,
    retry: 0,
  });

  const otdQuery = useQuery<OtdResponse>({
    queryKey: ['direcao', 'otd'],
    queryFn: () => ceoDashboardApi.otd({ window_days: 30 }) as Promise<OtdResponse>,
    staleTime: 60_000,
    retry: 0,
  });

  const fpyQuery = useQuery({
    queryKey: ['direcao', 'fpy'],
    queryFn: () => ceoDashboardApi.firstPassYield({ window_days: 30 }),
    staleTime: 60_000,
    retry: 0,
  });

  const marginQuery = useQuery({
    queryKey: ['direcao', 'margin-summary'],
    queryFn: () => profitApi.marginSummary(30),
    staleTime: 60_000,
    retry: 0,
  });

  const backlogQuery = useQuery<BacklogResponse>({
    queryKey: ['direcao', 'backlog'],
    queryFn: () => ceoDashboardApi.backlogByClient({ limit: 8 }),
    staleTime: 60_000,
    retry: 0,
  });

  // Objetivos do CEO — endpoint não existe (PARTIAL): degrada honesto.
  const objectivesQuery = useQuery({
    queryKey: ['direcao', 'objectives'],
    queryFn: () =>
      apiFetch<unknown>('/v1/profit/kpis/objectives').catch(() => ({
        erp_available: false,
      })),
    staleTime: 5 * 60_000,
    retry: 0,
  });

  // Margem por país — endpoint margin-by-segment não existe (PARTIAL).
  const marginCountryQuery = useQuery({
    queryKey: ['direcao', 'margin-country'],
    queryFn: () =>
      apiFetch<unknown>(
        '/v1/profit/margin-by-segment?dimension=country',
      ).catch(() => ({ erp_available: false })),
    staleTime: 5 * 60_000,
    retry: 0,
  });

  const transportQuery = useQuery<TransportBatch[]>({
    queryKey: ['direcao', 'transport'],
    queryFn: () =>
      apiFetch<TransportBatch[]>('/v1/plan/transport/batches?limit=20'),
    staleTime: 60_000,
    retry: 0,
  });

  // ─── Derivações ───────────────────────────────────────────────────────

  const throughput = throughputQuery.data?.throughput_eur ?? null;
  const trend = useMemo(
    () => (throughputQuery.data?.trend_14d ?? []).map((p) => p.eur),
    [throughputQuery.data],
  );

  const fpyValue =
    typeof fpyQuery.data?.first_pass_yield_pct === 'number'
      ? fpyQuery.data.first_pass_yield_pct
      : null;

  const otd = otdQuery.data ?? null;
  const reworkRate = kpiQuery.data?.rework_rate?.value ?? null;

  const objectivesHonest = useHonestEmptyState(objectivesQuery.data);
  const marginCountryHonest = useHonestEmptyState(marginCountryQuery.data);

  const backlogTotal = useMemo(
    () =>
      (backlogQuery.data?.items ?? []).reduce(
        (sum, r) => sum + (r.pending_value_eur ?? 0),
        0,
      ),
    [backlogQuery.data],
  );

  const transportBatches = transportQuery.data ?? [];

  return (
    <div>
      <PageHeader
        icon={<Building2 size={18} />}
        title="Direção"
        subtitle="Status NELO em 30 segundos · meta €30–35K/dia"
        helpId="direcao"
        actions={
          <button
            type="button"
            onClick={() => navigate('/relatorios')}
            className="inline-flex items-center gap-1.5 text-text-dark-primary transition-colors"
            style={{
              padding: '6px 12px',
              height: 32,
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-2)',
              borderRadius: 9,
              fontSize: 12.5,
            }}
          >
            <Download size={13} />
            Relatório PDF
          </button>
        }
      />

      <div style={{ padding: '24px 28px' }} className="page-enter">
        {/* ─── 4 KPIs grandes ─────────────────────────────────────────── */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: 12,
            marginBottom: 12,
          }}
        >
          <KPIBig
            label="€/dia hoje"
            value={throughput ? throughput.today : '—'}
            prefix={throughput ? '€' : undefined}
            format={(n) => `${(n / 1000).toFixed(1).replace('.', ',')}K`}
            context={
              throughput
                ? `meta €${Math.round(throughput.target_min / 1000)}K–${Math.round(throughput.target_max / 1000)}K`
                : throughputQuery.isLoading
                  ? 'A carregar…'
                  : 'Sem receita reconhecida hoje'
            }
            status={
              throughput?.on_target
                ? 'green'
                : throughput
                  ? 'yellow'
                  : 'gray'
            }
            accent={
              throughput?.on_target
                ? 'green'
                : throughput
                  ? 'yellow'
                  : 'gray'
            }
            sparkline={trend.length > 1 ? trend : undefined}
          />
          <KPIBig
            label="OTD"
            value={otd ? Math.round(otd.otd_pct) : '—'}
            unit={otd ? '%' : undefined}
            context={
              otd
                ? `${otd.on_time}/${otd.total} no prazo · janela ${otd.window_days}d`
                : otdQuery.isLoading
                  ? 'A carregar…'
                  : 'Sem entregas na janela'
            }
            target={otd ? '95%' : undefined}
            status={
              !otd ? 'gray' : otd.otd_pct >= 95 ? 'green' : otd.otd_pct >= 90 ? 'yellow' : 'red'
            }
            accent={
              !otd ? 'gray' : otd.otd_pct >= 95 ? 'green' : otd.otd_pct >= 90 ? 'yellow' : 'red'
            }
          />
          <KPIBig
            label="Qualidade · FPY"
            value={fpyValue !== null ? Number(fpyValue.toFixed(1)) : '—'}
            unit={fpyValue !== null ? '%' : undefined}
            context={
              fpyValue !== null
                ? `1ª passagem · ${fpyQuery.data?.orders_total ?? 0} ordens (30d)`
                : fpyQuery.isLoading
                  ? 'A carregar…'
                  : 'Sem ordens concluídas na janela'
            }
            status={
              fpyValue === null ? 'gray' : fpyValue >= 95 ? 'green' : fpyValue >= 90 ? 'yellow' : 'red'
            }
            accent={
              fpyValue === null ? 'gray' : fpyValue >= 95 ? 'green' : fpyValue >= 90 ? 'yellow' : 'red'
            }
          />
          <KPIBig
            label="Retrabalho"
            value={reworkRate !== null ? Number((reworkRate * 100).toFixed(1)) : '—'}
            unit={reworkRate !== null ? '%' : undefined}
            context={
              reworkRate !== null
                ? 'taxa de retrabalho · KPI_snapshot'
                : kpiQuery.isLoading
                  ? 'A carregar…'
                  : kpiQuery.data?.rework_rate?.reason ?? 'Sem dados de retrabalho'
            }
            target={reworkRate !== null ? '8%' : undefined}
            status={
              reworkRate === null ? 'gray' : reworkRate <= 0.08 ? 'green' : reworkRate <= 0.15 ? 'yellow' : 'red'
            }
            accent={
              reworkRate === null ? 'gray' : reworkRate <= 0.08 ? 'green' : reworkRate <= 0.15 ? 'yellow' : 'red'
            }
          />
        </div>

        {/* ─── KPIs · objetivo vs realizado (banda CEO) ─────────────────── */}
        <Card padding={18} style={{ marginBottom: 14 }}>
          <SectionHeader
            icon={<Target size={14} />}
            title="KPIs · objetivo vs realizado"
            subtitle="Alvos do CEO em KPI_OBJECTIVO · banda verde = dentro do esperado"
          />
          {objectivesHonest.degraded || objectivesQuery.isError ? (
            <EmptyState
              size="sm"
              title="Objetivos do CEO indisponíveis"
              hint={
                objectivesHonest.reason ||
                'O endpoint de objetivos (KPI_OBJECTIVO) ainda não está ligado. Os alvos aparecem assim que a fonte for sincronizada.'
              }
            />
          ) : (
            // Sem fonte real de bandas — derivamos os objetivos dos KPIs
            // vivos acima contra metas de produto conhecidas (Blueprint §1.1).
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 14,
              }}
            >
              {throughput ? (
                <ObjectiveCell
                  label="€/dia"
                  value={Number((throughput.today / 1000).toFixed(1))}
                  low={throughput.target_min / 1000}
                  high={throughput.target_max / 1000}
                  unit="K"
                />
              ) : null}
              {otd ? (
                <ObjectiveCell
                  label="OTD"
                  value={Math.round(otd.otd_pct)}
                  low={90}
                  high={100}
                  unit="%"
                />
              ) : null}
              {fpyValue !== null ? (
                <ObjectiveCell
                  label="FPY"
                  value={Number(fpyValue.toFixed(1))}
                  low={90}
                  high={100}
                  unit="%"
                />
              ) : null}
              {reworkRate !== null ? (
                <ObjectiveCell
                  label="Retrabalho"
                  value={Number((reworkRate * 100).toFixed(1))}
                  low={0}
                  high={10}
                  unit="%"
                />
              ) : null}
            </div>
          )}
        </Card>

        {/* ─── €/dia banda + Impacto PP1 ───────────────────────────────── */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.4fr 1fr',
            gap: 14,
            marginBottom: 14,
          }}
        >
          <Card padding={20}>
            <SectionHeader
              icon={<Euro size={14} />}
              title="€/dia · banda objetivo"
              subtitle="Últimos 14 dias · meta 30–35K"
            />
            {trend.length > 1 && throughput ? (
              <EuroBandChart
                series={trend}
                targetMin={throughput.target_min}
                targetMax={throughput.target_max}
              />
            ) : (
              <EmptyState
                size="sm"
                title="Sem série de receita"
                hint="Quando houver receita reconhecida (order_revenue), a tendência de 14 dias aparece aqui."
              />
            )}
          </Card>
          <Card padding={20}>
            <SectionHeader
              icon={<Sparkles size={14} />}
              title="Impacto PP1"
              subtitle="Sistema de aprendizagem activo"
            />
            <ImpactPP1 />
          </Card>
        </div>

        {/* ─── Margem por segmento ─────────────────────────────────────── */}
        <Card padding={18} style={{ marginBottom: 14 }}>
          <SectionHeader
            icon={<TrendingUp size={14} />}
            title="Margem por segmento"
            subtitle="Margem média de ordens com COGS calculado · país do ERP"
          />
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 16,
            }}
          >
            <div>
              <div
                style={{
                  fontSize: 10.5,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.4,
                  fontWeight: 600,
                  marginBottom: 8,
                }}
              >
                Resumo de margem (30 dias)
              </div>
              {marginQuery.data &&
              marginQuery.data.order_count > 0 &&
              marginQuery.data.avg_margin_eur !== null ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <SummaryStat
                    label="Margem média / ordem"
                    value={`€${Math.round(marginQuery.data.avg_margin_eur).toLocaleString('pt-PT')}`}
                    tone={marginQuery.data.avg_margin_eur > 0 ? 'green' : 'red'}
                  />
                  <SummaryStat
                    label="Ordens analisadas"
                    value={`${marginQuery.data.order_count}`}
                    tone="neutral"
                  />
                  <SummaryStat
                    label="Ordens com margem negativa"
                    value={`${marginQuery.data.negative_count}`}
                    tone={marginQuery.data.negative_count > 0 ? 'red' : 'green'}
                  />
                </div>
              ) : (
                <EmptyState
                  size="sm"
                  title="Sem ordens com COGS calculado"
                  hint="A margem média aparece assim que houver ordens com custo calculado."
                />
              )}
            </div>
            <div>
              <div
                style={{
                  fontSize: 10.5,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.4,
                  fontWeight: 600,
                  marginBottom: 8,
                }}
              >
                Por país
              </div>
              {marginCountryHonest.degraded || marginCountryQuery.isError ? (
                <EmptyState
                  size="sm"
                  title="Segmentação por país indisponível"
                  hint={
                    marginCountryHonest.reason ||
                    'A segmentação de margem por país/agente ainda não está ligada ao ERP MAR-KAYAKS.'
                  }
                />
              ) : (
                <CountryMargins data={marginCountryQuery.data} />
              )}
            </div>
          </div>
        </Card>

        {/* ─── CTP · encomendas activas ────────────────────────────────── */}
        <Card padding={0}>
          <div
            style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
          >
            <SectionHeader
              icon={<Flag size={14} />}
              title="Encomendas activas · backlog por cliente"
              subtitle={`${(backlogQuery.data?.items ?? []).length} clientes · €${Math.round(backlogTotal / 1000)}K pendente`}
            />
          </div>
          {backlogQuery.isLoading ? (
            <div
              style={{
                padding: 24,
                textAlign: 'center',
                color: 'var(--fg-3)',
                fontSize: 12,
              }}
            >
              A carregar backlog…
            </div>
          ) : (backlogQuery.data?.items ?? []).length === 0 ? (
            <div style={{ padding: 18 }}>
              <EmptyState
                size="sm"
                title="Sem encomendas pendentes"
                hint="Não há encomendas em backlog neste momento."
              />
            </div>
          ) : (
            <>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.6fr 110px 130px 130px',
                  alignItems: 'center',
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
                <div>Cliente</div>
                <div style={{ textAlign: 'right' }}>Encomendas</div>
                <div style={{ textAlign: 'right' }}>Valor pendente</div>
                <div style={{ textAlign: 'right' }}>Prazo mais cedo</div>
              </div>
              {(backlogQuery.data?.items ?? []).map((r, i, arr) => (
                <div
                  key={r.client_name + i}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1.6fr 110px 130px 130px',
                    alignItems: 'center',
                    padding: '12px 18px',
                    borderBottom:
                      i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
                  }}
                >
                  <div
                    style={{ fontSize: 13, color: 'var(--fg-0)', fontWeight: 500 }}
                  >
                    {r.client_name}
                  </div>
                  <div
                    className="tabular"
                    style={{ fontSize: 12.5, color: 'var(--fg-1)', textAlign: 'right' }}
                  >
                    {r.pending_orders}
                  </div>
                  <div
                    className="tabular"
                    style={{
                      fontSize: 12.5,
                      color: 'var(--fg-0)',
                      fontWeight: 600,
                      textAlign: 'right',
                    }}
                  >
                    €{Math.round(r.pending_value_eur).toLocaleString('pt-PT')}
                  </div>
                  <div
                    className="tabular"
                    style={{ fontSize: 12.5, color: 'var(--fg-2)', textAlign: 'right' }}
                  >
                    {r.earliest_deadline
                      ? fmtDate(r.earliest_deadline)
                      : '—'}
                  </div>
                </div>
              ))}
            </>
          )}
        </Card>

        {/* ─── Próximas expedições ─────────────────────────────────────── */}
        <Card padding={18} style={{ marginTop: 14 }}>
          <SectionHeader
            title="Próximas expedições"
            subtitle="Camiões de transporte agendados"
          />
          {transportQuery.isLoading ? (
            <div
              style={{
                padding: 12,
                textAlign: 'center',
                color: 'var(--fg-3)',
                fontSize: 12,
              }}
            >
              A carregar expedições…
            </div>
          ) : transportBatches.length === 0 ? (
            <EmptyState
              size="sm"
              title="Sem expedições agendadas"
              hint="Quando houver camiões para carregar, aparecem aqui."
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {transportBatches.slice(0, 6).map((b) => {
                const st = STATUS_LABEL[b.status ?? 'planned'] ?? {
                  label: b.status ?? '—',
                  tone: 'neutral',
                };
                return (
                  <div
                    key={b.id}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '1fr 120px 110px 110px',
                      alignItems: 'center',
                      gap: 12,
                      padding: '10px 12px',
                      background: 'var(--bg-2)',
                      borderRadius: 'var(--r-md)',
                      fontSize: 12.5,
                    }}
                  >
                    <span style={{ color: 'var(--fg-0)', fontWeight: 500 }}>
                      {b.code ?? b.id.slice(0, 8)}
                    </span>
                    <span style={{ color: 'var(--fg-2)' }}>
                      {b.destination ?? '—'}
                    </span>
                    <span
                      className="tabular"
                      style={{ color: 'var(--fg-1)' }}
                    >
                      {fmtDate(b.transport_date)}
                    </span>
                    <span
                      style={{
                        justifySelf: 'end',
                        padding: '1px 8px',
                        fontSize: 10.5,
                        borderRadius: 999,
                        color: `var(--${st.tone === 'neutral' ? 'fg-1' : st.tone === 'info' ? 'blue' : st.tone === 'warning' ? 'yellow' : 'green'})`,
                        background: `var(--bg-3)`,
                        border: '1px solid var(--bd-1)',
                      }}
                    >
                      {st.label}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

// ─── ObjectiveCell ───────────────────────────────────────────────────────

function ObjectiveCell({
  label,
  value,
  low,
  high,
  unit,
}: {
  label: string;
  value: number;
  low: number;
  high: number;
  unit: string;
}) {
  return (
    <div>
      <div
        style={{
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <ObjectiveBar value={value} low={low} high={high} unit={unit} />
    </div>
  );
}

// ─── SummaryStat ─────────────────────────────────────────────────────────

function SummaryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: 'green' | 'red' | 'neutral';
}) {
  const color =
    tone === 'green'
      ? 'var(--green)'
      : tone === 'red'
        ? 'var(--red)'
        : 'var(--fg-0)';
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        padding: '8px 0',
        borderBottom: '1px solid var(--bd-1)',
        fontSize: 12,
      }}
    >
      <span style={{ color: 'var(--fg-2)' }}>{label}</span>
      <span className="tabular" style={{ color, fontWeight: 600 }}>
        {value}
      </span>
    </div>
  );
}

// ─── CountryMargins — só renderiza se a resposta tiver shape esperado ────

function CountryMargins({ data }: { data: unknown }) {
  const rows = useMemo(() => {
    if (!data || typeof data !== 'object') return [];
    const items = (data as { items?: unknown }).items;
    if (!Array.isArray(items)) return [];
    return items
      .filter(
        (r): r is { label: string; margin: number; revenue: number } =>
          !!r &&
          typeof r === 'object' &&
          typeof (r as Record<string, unknown>).margin === 'number',
      )
      .map((r) => ({
        label: String((r as Record<string, unknown>).label ?? '—'),
        margin: Number((r as Record<string, unknown>).margin),
        revenue: Number((r as Record<string, unknown>).revenue ?? 0),
      }));
  }, [data]);

  if (rows.length === 0) {
    return (
      <EmptyState
        size="sm"
        title="Sem margem por país"
        hint="Não há ordens com país atribuído para segmentar."
      />
    );
  }
  return (
    <div>
      {rows.map((r, i) => (
        <MarginRow
          key={r.label}
          label={r.label}
          margin={r.margin}
          revenue={r.revenue}
          asPill
          last={i === rows.length - 1}
        />
      ))}
    </div>
  );
}

// ─── ImpactPP1 — quanto o sistema de aprendizagem rendeu ─────────────────

function ImpactPP1() {
  // O Impacto PP1 monetário não tem endpoint dedicado — mostramos um
  // empty state honesto em vez de inventar o número.
  return (
    <div style={{ marginTop: 4 }}>
      <EmptyState
        size="sm"
        title="Impacto PP1 ainda não quantificado"
        hint="A poupança gerada pelas sugestões aceites será calculada pelo serviço de custos. Até lá, o valor não é mostrado para não inventar números."
      />
    </div>
  );
}
