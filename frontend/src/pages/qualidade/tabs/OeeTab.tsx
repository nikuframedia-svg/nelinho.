// QualidadePage · tab OeeTab (Q.60.Q). ZERO MOCKS — liga a endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, TrendingUp } from 'lucide-react';
import { OEERing, EmptyState } from '../../../components/dark';
import { Card, SectionHeader, MiniBar, Banner } from '../../../components/qualidade/QualidadeBits';
import { apiFetch } from '../../../lib/api';
import { type OeeResponse } from '../qualidadeTypes';
import { LoadingLine } from '../qualidadeShared';

export function OeeTab() {
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
