/**
 * PainelDiarioPage — o painel diário "em 5 segundos sabes se está tudo bem".
 *
 * Q.52.D · Onda 1 · T1. Reconstrução fiel do `page-painel.jsx` do design
 * NELO, ligada a endpoints REAIS:
 *   - KPIs               → /v1/factory-map/snapshot (REAL)
 *   - Gargalo por fase   → snapshot.phases.bottlenecks (REAL)
 *   - Alertas            → /v1/copilot/alerts?status=active (REAL)
 *                          + acknowledge / resolve (REAL)
 *   - Aprovações         → /v1/decisions?status_filter=PROPOSED (REAL)
 *   - Feed ao vivo       → /v1/activity/recent (REAL)
 *
 * ZERO MOCKS: nada é placeholder. A "Aderência ao plano" liga ao
 * endpoint /v1/plan/adherence (Q.53.B); sem plano commitado mostra
 * "sem plano" em vez de inventar um número. Estados de carregamento /
 * erro / vazio são todos explícitos.
 *
 * Distinto do `PainelPage.tsx` legacy (Q.18.ZIP.B) — a rota /painel é
 * religada a esta página na integração final (Q.52.S).
 */

import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';
import {
  Boxes,
  CheckCircle2,
  ClipboardCheck,
  Home,
  Layers,
  RefreshCw,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import {
  DarkBadge,
  DarkButton,
  EmptyState,
  KPIBig,
  LiveBadge,
} from '../../components/dark';
import { decisionsApi } from '../../lib/api';
import { planeamentoApi } from '../../components/planeamento/planeamentoApi';
import { painelApi } from './painelApi';
import type { CopilotAlert } from './painelApi';
import { PainelGargalo } from './PainelGargalo';
import { PainelAlertCard } from './PainelAlertCard';
import { OtdRiskCard } from '../../components/painel/OtdRiskCard';
import { fmtEuroK, normalizeBottleneck } from './painelHelpers';

type TabId = 'alertas' | 'aprovacoes' | 'feed';

export function PainelDiarioPage(): ReactNode {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<TabId>('alertas');

  // ─── Snapshot global (KPIs + gargalo) ──────────────────────────────────
  const snapshotQuery = useQuery({
    queryKey: ['painel', 'snapshot'],
    queryFn: () => painelApi.snapshot(),
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });

  // ─── Alertas activos ────────────────────────────────────────────────────
  const alertsQuery = useQuery({
    queryKey: ['painel', 'alerts'],
    queryFn: () => painelApi.alerts({ status: 'active', limit: 50 }),
    refetchOnWindowFocus: false,
  });

  // ─── Aprovações pendentes (decisões PROPOSED) ───────────────────────────
  const decisionsQuery = useQuery({
    queryKey: ['painel', 'decisions', 'proposed'],
    queryFn: () => decisionsApi.list({ status: 'PROPOSED', page_size: 50 }),
    refetchOnWindowFocus: false,
  });

  // ─── Feed de actividade recente ─────────────────────────────────────────
  const activityQuery = useQuery({
    queryKey: ['painel', 'activity'],
    queryFn: () => painelApi.activity(25),
    refetchOnWindowFocus: false,
    // Q.59.G.1 — SSE (`dashboard` + `timeline`) já dispara em cada
    // mudança real. 30 s era polling-belt-and-braces; 60 s mantém
    // safety-net em modo degraded sem martelar o backend.
    refetchInterval: 60_000,
  });

  // ─── Aderência ao plano (Q.53.B) ────────────────────────────────────────
  const adherenceQuery = useQuery({
    queryKey: ['painel', 'adherence'],
    queryFn: () => planeamentoApi.adherence(),
    refetchOnWindowFocus: false,
    staleTime: 60_000,
  });

  // ─── Risco de atraso de encomendas (Q.54.F) ─────────────────────────────
  const otdRiskQuery = useQuery({
    queryKey: ['painel', 'otd-risk'],
    queryFn: () => painelApi.otdRisk(50),
    refetchOnWindowFocus: false,
    staleTime: 5 * 60_000,
  });

  // ─── Mutações dos alertas ───────────────────────────────────────────────
  const [busyAlertId, setBusyAlertId] = useState<string | null>(null);
  const invalidateAlerts = () =>
    queryClient.invalidateQueries({ queryKey: ['painel', 'alerts'] });

  const ackMutation = useMutation({
    mutationFn: (id: string) => painelApi.acknowledgeAlert(id),
    onMutate: (id) => setBusyAlertId(id),
    onSettled: () => {
      setBusyAlertId(null);
      invalidateAlerts();
    },
  });
  const resolveMutation = useMutation({
    mutationFn: (id: string) => painelApi.resolveAlert(id),
    onMutate: (id) => setBusyAlertId(id),
    onSettled: () => {
      setBusyAlertId(null);
      invalidateAlerts();
    },
  });

  // ─── Derivações ─────────────────────────────────────────────────────────
  const snap = snapshotQuery.data;

  const phases = useMemo(
    () => (snap?.phases.bottlenecks ?? []).map(normalizeBottleneck),
    [snap],
  );

  // Defensivo legítimo: enquanto a query carrega ou falha mostramos um
  // estado vazio explícito; o ErrorBoundary da rota apanha um throw real.
  const alerts: CopilotAlert[] = alertsQuery.data ?? [];
  const criticalCount = alerts.filter(
    (a) => a.severity.toUpperCase() === 'CRITICAL',
  ).length;
  const decisions = decisionsQuery.data?.items ?? [];
  const activity = activityQuery.data?.items ?? [];

  // Aderência ao plano — % do plano do CPO que já se realizou.
  const adherence = adherenceQuery.data;
  const adherencePct = adherence?.summary.adherence_pct ?? null;

  // Risco de atraso — ordenado pelo backend, prob. decrescente.
  const otdRisk = otdRiskQuery.data ?? null;

  // €/dia — sai do snapshot quando o ThroughputService está ligado.
  const throughput = snap?.kpis.throughput_eur_day;
  const euroDay =
    typeof throughput === 'object' && throughput !== null ? throughput : null;
  const hasEuroDay = euroDay !== null && typeof euroDay.today === 'number';

  return (
    <DarkPageLayout
      title="Painel"
      subtitle="Em 5 segundos sabes se hoje está tudo bem."
      icon={<Home size={18} />}
      actions={<LiveBadge />}
    >
      {/* ─── KPIs (8) ─────────────────────────────────────────────────── */}
      {snapshotQuery.isError ? (
        <EmptyState
          mascot={false}
          title="Não foi possível carregar o painel"
          hint="O snapshot da fábrica não respondeu. Verifica se o backend está ligado."
          action={
            <DarkButton size="sm" onClick={() => snapshotQuery.refetch()}>
              Tentar novamente
            </DarkButton>
          }
        />
      ) : (
        <>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 12,
              marginBottom: 12,
            }}
          >
            <KPIBig
              label="€/dia"
              value={hasEuroDay ? (euroDay!.today as number) : 'indisponível'}
              prefix={hasEuroDay ? '€' : undefined}
              context={
                euroDay && typeof euroDay.target_min === 'number'
                  ? `Meta ${fmtEuroK(euroDay.target_min)}–${fmtEuroK(
                      euroDay.target_max ?? euroDay.target_min,
                    )}`
                  : 'Throughput €/dia liga quando o ERP de pricing sincronizar'
              }
              status={euroDay && euroDay.on_target ? 'green' : 'yellow'}
              accent="green"
              format={(n) => fmtEuroK(n)}
            />
            <KPIBig
              label="Concluídos hoje"
              value={snap?.kpis.completed_today ?? 0}
              unit="barcos"
              context="Barcos terminados desde as 00h"
              status="green"
              accent="green"
            />
            <KPIBig
              label="Barcos em curso"
              value={snap?.kpis.wip ?? 0}
              unit="barcos"
              context={`${snap?.boats.total ?? 0} ordens no total`}
              status="blue"
              accent="blue"
            />
            <KPIBig
              label="Alertas activos"
              value={alerts.length}
              context={
                alertsQuery.isLoading
                  ? 'A carregar…'
                  : `${criticalCount} crítico(s) · ${
                      alerts.length - criticalCount
                    } outro(s)`
              }
              status={criticalCount > 0 ? 'red' : 'orange'}
              accent={criticalCount > 0 ? 'red' : 'orange'}
            />
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 12,
              marginBottom: 24,
            }}
          >
            <KPIBig
              label="Taxa de defeito"
              value={
                typeof snap?.kpis.defect_rate === 'number'
                  ? snap.kpis.defect_rate.toFixed(2)
                  : 'indisponível'
              }
              unit={
                typeof snap?.kpis.defect_rate === 'number'
                  ? 'erros/ordem'
                  : undefined
              }
              context="Retrabalho registado por ordem · últimos 90 dias"
              status={
                typeof snap?.kpis.defect_rate !== 'number'
                  ? 'gray'
                  : snap.kpis.defect_rate <= 1
                    ? 'green'
                    : 'orange'
              }
              accent={
                typeof snap?.kpis.defect_rate !== 'number'
                  ? 'gray'
                  : snap.kpis.defect_rate <= 1
                    ? 'green'
                    : 'orange'
              }
            />
            <KPIBig
              label="Aprovações pendentes"
              value={decisionsQuery.isLoading ? '…' : decisions.length}
              context="Decisões à espera do teu OK"
              status={decisions.length > 0 ? 'yellow' : 'green'}
              accent="yellow"
            />
            <KPIBig
              label="Moldes"
              value={snap?.molds.total ?? 0}
              unit="activos"
              context="Inventário de moldes da fábrica"
              status="gray"
              accent="gray"
            />
            <KPIBig
              label="Aderência ao plano"
              value={
                adherenceQuery.isLoading
                  ? '…'
                  : adherenceQuery.isError
                    ? 'indisponível'
                    : adherence && !adherence.has_committed_plan
                      ? 'sem plano'
                      : adherencePct !== null
                        ? `${adherencePct.toFixed(0)}%`
                        : 'sem dados'
              }
              context={
                adherenceQuery.isError
                  ? 'O endpoint /v1/plan/adherence não respondeu'
                  : adherence && !adherence.has_committed_plan
                    ? 'Ainda não há plano commitado do CPO'
                    : adherence
                      ? `${adherence.summary.total_realised_ops}/${adherence.summary.total_planned_ops} ops · ${adherence.summary.n_phases} fases`
                      : 'Plano vs realizado por fase'
              }
              status={
                adherencePct === null
                  ? 'gray'
                  : adherencePct >= 80
                    ? 'green'
                    : adherencePct >= 50
                      ? 'yellow'
                      : 'red'
              }
              accent={
                adherencePct === null
                  ? 'gray'
                  : adherencePct >= 80
                    ? 'green'
                    : 'yellow'
              }
            />
          </div>

          {/* ─── Gargalo por fase ──────────────────────────────────────── */}
          <div style={{ marginBottom: 24 }}>
            {snapshotQuery.isLoading ? (
              <SkeletonCard label="A carregar gargalo da linha…" />
            ) : (
              <PainelGargalo phases={phases} />
            )}
          </div>

          {/* ─── Encomendas em risco de atraso (Q.54.F) ────────────────── */}
          <div style={{ marginBottom: 24 }}>
            <OtdRiskCard
              query={{
                data: otdRisk,
                isLoading: otdRiskQuery.isLoading,
                isError: otdRiskQuery.isError,
              }}
              onRetry={() => otdRiskQuery.refetch()}
            />
          </div>
        </>
      )}

      {/* ─── Tabs ────────────────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--bd-1)',
          marginBottom: 16,
        }}
      >
        <div style={{ display: 'flex', gap: 2 }}>
          {(
            [
              { id: 'alertas' as const, label: 'Alertas', badge: alerts.length },
              {
                id: 'aprovacoes' as const,
                label: 'Aprovações',
                badge: decisions.length,
              },
              { id: 'feed' as const, label: 'Actividade', badge: 0 },
            ]
          ).map((t) => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                style={{
                  padding: '9px 14px',
                  background: 'transparent',
                  border: 'none',
                  borderBottom: `1.5px solid ${
                    active ? 'var(--fg-0)' : 'transparent'
                  }`,
                  color: active ? 'var(--fg-0)' : 'var(--fg-2)',
                  fontSize: 13,
                  fontWeight: active ? 600 : 500,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 7,
                  marginBottom: -1,
                }}
              >
                {t.label}
                {t.badge > 0 && (
                  <span
                    style={{
                      background: active ? 'var(--fg-0)' : 'var(--bg-3)',
                      color: active ? 'var(--bg-0)' : 'var(--fg-2)',
                      fontSize: 10,
                      fontWeight: 600,
                      padding: '0 6px',
                      borderRadius: 999,
                      minWidth: 16,
                      textAlign: 'center',
                      height: 16,
                      lineHeight: '16px',
                    }}
                  >
                    {t.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        <button
          type="button"
          onClick={() => {
            alertsQuery.refetch();
            decisionsQuery.refetch();
            activityQuery.refetch();
          }}
          title="Recarregar"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            background: 'transparent',
            border: 'none',
            color: 'var(--fg-3)',
            fontSize: 11.5,
            cursor: 'pointer',
            padding: '4px 8px',
          }}
        >
          <RefreshCw size={12} />
          Recarregar
        </button>
      </div>

      {/* ─── Tab: Alertas ──────────────────────────────────────────────── */}
      {tab === 'alertas' &&
        (alertsQuery.isLoading ? (
          <SkeletonCard label="A carregar alertas…" />
        ) : alertsQuery.isError ? (
          <EmptyState
            mascot={false}
            title="Alertas indisponíveis"
            hint="O serviço de alertas do copiloto não respondeu."
            action={
              <DarkButton size="sm" onClick={() => alertsQuery.refetch()}>
                Tentar novamente
              </DarkButton>
            }
          />
        ) : alerts.length === 0 ? (
          <EmptyState
            mascot={false}
            icon={<CheckCircle2 size={28} />}
            title="Sem alertas activos"
            hint="A fábrica está calma. Os alertas aparecem aqui assim que um detector dispara."
          />
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: 12,
            }}
          >
            {alerts.map((a) => (
              <PainelAlertCard
                key={a.id}
                alert={a}
                busy={busyAlertId === a.id}
                onAcknowledge={(id) => ackMutation.mutate(id)}
                onResolve={(id) => resolveMutation.mutate(id)}
              />
            ))}
          </div>
        ))}

      {/* ─── Tab: Aprovações ───────────────────────────────────────────── */}
      {tab === 'aprovacoes' &&
        (decisionsQuery.isLoading ? (
          <SkeletonCard label="A carregar aprovações…" />
        ) : decisionsQuery.isError ? (
          <EmptyState
            mascot={false}
            title="Aprovações indisponíveis"
            hint="A inbox de decisões não respondeu."
            action={
              <DarkButton size="sm" onClick={() => decisionsQuery.refetch()}>
                Tentar novamente
              </DarkButton>
            }
          />
        ) : decisions.length === 0 ? (
          <EmptyState
            mascot={false}
            icon={<ClipboardCheck size={28} />}
            title="Nada à espera de aprovação"
            hint="Sem decisões propostas. Quando o sistema sugerir uma mudança que precise do teu OK, aparece aqui."
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {decisions.map((d) => (
              <div
                key={d.id}
                style={{
                  background: 'var(--bg-1)',
                  border: '1px solid var(--bd-1)',
                  borderRadius: 'var(--r-md)',
                  padding: 14,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 12,
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{ display: 'flex', alignItems: 'center', gap: 8 }}
                  >
                    <DarkBadge variant="warning" size="sm">
                      Proposta
                    </DarkBadge>
                    <span style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
                      {d.action_type}
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 500,
                      color: 'var(--fg-0)',
                      marginTop: 4,
                    }}
                  >
                    {d.title}
                  </div>
                  <div
                    style={{
                      fontSize: 11.5,
                      color: 'var(--fg-3)',
                      marginTop: 2,
                    }}
                  >
                    Alvo: {d.target} · proposta por {d.proposed_by}
                  </div>
                </div>
                <a
                  href="#/inbox"
                  style={{
                    fontSize: 11.5,
                    color: 'var(--accent)',
                    textDecoration: 'none',
                    whiteSpace: 'nowrap',
                  }}
                >
                  Abrir na Inbox →
                </a>
              </div>
            ))}
          </div>
        ))}

      {/* ─── Tab: Actividade ───────────────────────────────────────────── */}
      {tab === 'feed' &&
        (activityQuery.isLoading ? (
          <SkeletonCard label="A carregar actividade…" />
        ) : activityQuery.isError ? (
          <EmptyState
            mascot={false}
            title="Feed indisponível"
            hint="O feed de actividade não respondeu."
            action={
              <DarkButton size="sm" onClick={() => activityQuery.refetch()}>
                Tentar novamente
              </DarkButton>
            }
          />
        ) : activity.length === 0 ? (
          <EmptyState
            mascot={false}
            icon={<Layers size={28} />}
            title="Sem actividade recente"
            hint="Ainda não há eventos no outbox. Aparecem aqui à medida que a fábrica trabalha."
          />
        ) : (
          <div
            style={{
              background: 'var(--bg-1)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-lg)',
              overflow: 'hidden',
            }}
          >
            {activity.map((item, i) => {
              const when = item.created_at ?? item.timestamp ?? null;
              return (
                <div
                  key={item.id ?? i}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: '11px 14px',
                    borderTop: i === 0 ? 'none' : '1px solid var(--bd-1)',
                  }}
                >
                  <Boxes
                    size={14}
                    color="var(--fg-3)"
                    style={{ marginTop: 2, flexShrink: 0 }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, color: 'var(--fg-1)' }}>
                      {item.title ??
                        item.summary ??
                        item.message ??
                        item.event_type ??
                        item.kind ??
                        'Evento'}
                    </div>
                    {when && (
                      <div
                        style={{
                          fontSize: 10.5,
                          color: 'var(--fg-3)',
                          marginTop: 2,
                        }}
                      >
                        {new Date(when).toLocaleString('pt-PT')}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
    </DarkPageLayout>
  );
}

function SkeletonCard({ label }: { label: string }): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding: 32,
        textAlign: 'center',
        fontSize: 12,
        color: 'var(--fg-3)',
      }}
    >
      {label}
    </div>
  );
}

export default PainelDiarioPage;
