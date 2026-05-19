/**
 * DirecaoPage — Direção (shell · Q.60.W).
 *
 * Os tipos das respostas vivem em ./direcaoTypes; os componentes e helpers
 * (ObjectiveCell/SummaryStat/CountryMargins/ImpactPP1) em ./direcaoComponents.
 */
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Building2, Download, Target, Euro, Sparkles, TrendingUp, Flag } from 'lucide-react';
import { PageHeader, KPIBig, EmptyState } from '../../components/dark';
import { Card, SectionHeader, EuroBandChart } from '../../components/ceo/CeoBits';
import { useHonestEmptyState } from '../../hooks/useHonestEmptyState';
import { OtdRiskCard } from '../../components/painel/OtdRiskCard';
import { painelApi } from '../painel/painelApi';
import { apiFetch, kpisApi, ceoDashboardApi, profitApi, type BacklogResponse } from '../../lib/api';
import { direcaoApi, type KpiObjectivesResponse, type MarginBySegmentResponse } from './direcaoApi';
import { type KpiSnapshot, type ThroughputDashboard, type OtdResponse, type TransportBatch } from './direcaoTypes';
import { STATUS_LABEL, fmtDate, realisedForKpi, ObjectiveCell, SummaryStat, CountryMargins, ImpactPP1 } from './direcaoComponents';

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

  // Objetivos do CEO — bandas low/target/high por KPI + impacto-PP1 (Q.53.C).
  const objectivesQuery = useQuery<KpiObjectivesResponse>({
    queryKey: ['direcao', 'objectives'],
    queryFn: () => direcaoApi.objectives(),
    staleTime: 5 * 60_000,
    retry: 0,
  });

  // Margem por país — segmentação do ERP NELO (Q.53.C). Degrada honesto
  // via erp_available=false quando o adaptador NELO está offline.
  const marginCountryQuery = useQuery<MarginBySegmentResponse>({
    queryKey: ['direcao', 'margin-country'],
    queryFn: () => direcaoApi.marginBySegment('country'),
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

  // Risco de atraso de encomendas (Q.54.F) — partilhado com o Painel.
  const otdRiskQuery = useQuery({
    queryKey: ['painel', 'otd-risk'],
    queryFn: () => painelApi.otdRisk(50),
    staleTime: 5 * 60_000,
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

  const marginCountryHonest = useHonestEmptyState(marginCountryQuery.data);
  const objectives = objectivesQuery.data?.kpis ?? [];
  const pp1Impact = objectivesQuery.data?.pp1_impact ?? null;

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
            subtitle="Bandas-alvo do CEO · banda verde = dentro do esperado"
          />
          {objectivesQuery.isLoading ? (
            <div
              style={{
                padding: 16,
                textAlign: 'center',
                color: 'var(--fg-3)',
                fontSize: 12,
              }}
            >
              A carregar objetivos…
            </div>
          ) : objectivesQuery.isError ? (
            <EmptyState
              size="sm"
              title="Objetivos do CEO indisponíveis"
              hint="Não foi possível ler /v1/profit/kpis/objectives. Tenta recarregar a página."
            />
          ) : objectives.length === 0 ? (
            <EmptyState
              size="sm"
              title="Sem objetivos definidos"
              hint="Ainda não há bandas-alvo configuradas. Define-as na configuração de custos."
            />
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: `repeat(${Math.min(objectives.length, 4)}, 1fr)`,
                gap: 14,
              }}
            >
              {objectives.map((band) => (
                <ObjectiveCell
                  key={band.kpi}
                  band={band}
                  realised={realisedForKpi(band.kpi, {
                    throughputToday: throughput?.today ?? null,
                    otdPct: otd?.otd_pct ?? null,
                    fpyPct: fpyValue,
                    reworkRate,
                  })}
                />
              ))}
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
              subtitle="€ poupado por sugestões aceites"
            />
            <ImpactPP1
              impact={pp1Impact}
              isLoading={objectivesQuery.isLoading}
              isError={objectivesQuery.isError}
            />
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
              {marginCountryQuery.isLoading ? (
                <div
                  style={{
                    padding: 16,
                    textAlign: 'center',
                    color: 'var(--fg-3)',
                    fontSize: 12,
                  }}
                >
                  A carregar margem por país…
                </div>
              ) : marginCountryHonest.degraded || marginCountryQuery.isError ? (
                <EmptyState
                  size="sm"
                  title="Segmentação por país indisponível"
                  hint={
                    marginCountryQuery.data?.unavailable_reason ||
                    marginCountryHonest.reason ||
                    'A segmentação de margem por país ainda não está ligada ao ERP MAR-KAYAKS.'
                  }
                />
              ) : (
                <CountryMargins data={marginCountryQuery.data ?? null} />
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

        {/* ─── Encomendas em risco de atraso (Q.54.F) ──────────────────── */}
        <div style={{ marginTop: 14 }}>
          <OtdRiskCard
            query={{
              data: otdRiskQuery.data ?? null,
              isLoading: otdRiskQuery.isLoading,
              isError: otdRiskQuery.isError,
            }}
            onRetry={() => otdRiskQuery.refetch()}
          />
        </div>

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

// ─── realisedForKpi — casa um KPI da banda com o seu valor vivo ──────────
