// QualidadePage · tab PredicoesTab (Q.60.Q). ZERO MOCKS — liga a endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { Brain } from 'lucide-react';
import { EmptyState, RiskBadge } from '../../../components/dark';
import { Card, SectionHeader } from '../../../components/qualidade/QualidadeBits';
import { fetchDefectRisk } from '../../../components/qualidade/qualidadeApi';
import { LoadingLine, KpiTile } from '../qualidadeShared';

export function PredicoesTab() {
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
