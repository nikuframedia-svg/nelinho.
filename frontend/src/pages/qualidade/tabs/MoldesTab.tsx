// QualidadePage · tab MoldesTab (Q.60.Q). ZERO MOCKS — liga a endpoints reais.
import { Wrench } from 'lucide-react';
import { EmptyState } from '../../../components/dark';
import { Card, SectionHeader, MiniBar } from '../../../components/qualidade/QualidadeBits';
import { useMoldQuality, LoadingLine } from '../qualidadeShared';

export function MoldesTab() {
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
