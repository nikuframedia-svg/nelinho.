// QualidadePage · tab CustosTab (Q.60.Q). ZERO MOCKS — liga a endpoints reais.
import { Euro } from 'lucide-react';
import { EmptyState } from '../../../components/dark';
import { Card, SectionHeader } from '../../../components/qualidade/QualidadeBits';
import { useReworkList, RoiCard, LoadingLine, KpiTile } from '../qualidadeShared';

export function CustosTab() {
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
