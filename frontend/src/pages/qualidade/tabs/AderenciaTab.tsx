// QualidadePage · tab AderenciaTab (Q.60.Q). ZERO MOCKS — liga a endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { Target } from 'lucide-react';
import { EmptyState } from '../../../components/dark';
import { Card, SectionHeader, Banner } from '../../../components/qualidade/QualidadeBits';
import { fetchAdherence } from '../../../components/qualidade/qualidadeApi';
import { LoadingLine, KpiTile } from '../qualidadeShared';

export function AderenciaTab() {
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
