// QualidadePage · tab ResumoTab (Q.60.Q). ZERO MOCKS — liga a endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Wrench, Repeat } from 'lucide-react';
import { KPIBig, EmptyState } from '../../../components/dark';
import { Card, SectionHeader, MiniBar } from '../../../components/qualidade/QualidadeBits';
import { apiFetch } from '../../../lib/api';
import { type QualityDashboardResponse } from '../qualidadeTypes';
import { useFpy, useReworkList, useMolds, LoadingLine } from '../qualidadeShared';

export function ResumoTab() {
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
