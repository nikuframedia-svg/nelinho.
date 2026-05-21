// MateriaisPage · ProspecaoTab (Q.60.V). ZERO MOCKS — endpoints reais.
import { useMemo, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Target, AlertTriangle } from 'lucide-react';
import { EmptyState } from '../../../components/dark/EmptyState';
import { SkeletonLoader } from '../../../components/ui/Skeleton';
import { materiaisApi, type ShortageRisk } from '../../../components/materiais/materiaisApi';
import { SectionTitle, primaryBtn } from '../materiaisShared';

export function normalizeRisks(
  raw: ShortageRisk[] | { items?: ShortageRisk[]; data?: ShortageRisk[] } | undefined,
): ShortageRisk[] {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  return raw.items ?? raw.data ?? [];
}

export function ProspecaoTab(): ReactNode {
  const risksQuery = useQuery({
    queryKey: ['materiais', 'shortage-risks'],
    queryFn: () => materiaisApi.shortageRisks(14),
    retry: 0,
  });

  const reconQuery = useQuery({
    queryKey: ['materiais', 'reconciliation'],
    queryFn: () => materiaisApi.listReconciliations({ limit: 50 }),
    retry: 0,
  });

  const risks = useMemo(
    () => normalizeRisks(risksQuery.data),
    [risksQuery.data],
  );
  const recons = reconQuery.data ?? [];
  const unresolved = recons.filter((r) => !r.resolved);

  if (risksQuery.isLoading) {
    return <SkeletonLoader count={4} />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* ── Risco de ruptura ─────────────────────────────────────────── */}
      <section
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionTitle
          icon={<Target size={14} />}
          title="Risco de ruptura · próximos 14 dias"
          subtitle="Detetor ROP — materiais que ficam abaixo do ponto de encomenda"
        />
        {risksQuery.isError ? (
          <EmptyState
            title="Não foi possível avaliar o risco"
            hint="O endpoint /v1/factory-map/shortage-risks falhou."
            icon={<AlertTriangle size={24} />}
            size="sm"
            action={
              <button type="button" onClick={() => risksQuery.refetch()} style={primaryBtn}>
                Tentar novamente
              </button>
            }
          />
        ) : risks.length === 0 ? (
          <EmptyState
            title="Sem risco de ruptura"
            hint="Nenhum material está projetado para ficar abaixo do ROP nos próximos 14 dias."
            icon={<Target size={24} />}
            size="sm"
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {risks.map((r, i) => (
              <div
                key={r.sku_id ?? i}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 110px 110px 120px',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 12px',
                  background: 'var(--bg-2)',
                  borderRadius: 'var(--r-sm)',
                }}
              >
                <div>
                  <div style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
                    {r.name ?? r.sku_id}
                  </div>
                  <div style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>{r.sku_id}</div>
                </div>
                <div className="tabular" style={{ fontSize: 12, color: 'var(--fg-2)' }}>
                  {r.on_hand !== undefined ? `on-hand ${r.on_hand}` : '—'}
                </div>
                <div className="tabular" style={{ fontSize: 12, color: 'var(--fg-2)' }}>
                  {r.rop !== undefined && r.rop !== null ? `ROP ${r.rop}` : '—'}
                </div>
                <div
                  className="tabular"
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color:
                      r.days_to_stockout !== undefined && r.days_to_stockout !== null
                        ? r.days_to_stockout <= 3
                          ? 'var(--red)'
                          : 'var(--yellow)'
                        : 'var(--fg-3)',
                  }}
                >
                  {r.days_to_stockout !== undefined && r.days_to_stockout !== null
                    ? `acaba ~${Math.round(r.days_to_stockout)}d`
                    : 'sem estimativa'}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Reconciliações ───────────────────────────────────────────── */}
      <section
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionTitle
          title="Reconciliações de inventário"
          subtitle="Contagem física vs teórica — variâncias por resolver"
        />
        {reconQuery.isLoading ? (
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>A carregar…</div>
        ) : reconQuery.isError ? (
          <EmptyState
            title="Reconciliações indisponíveis"
            hint="O endpoint /v1/supply/reconciliation falhou."
            size="sm"
          />
        ) : recons.length === 0 ? (
          <EmptyState
            title="Sem reconciliações"
            hint="Ainda não foi submetida nenhuma contagem física de stock."
            size="sm"
          />
        ) : (
          <div>
            <div style={{ fontSize: 11.5, color: 'var(--fg-2)', marginBottom: 10 }}>
              {unresolved.length} por resolver de {recons.length} no total
            </div>
            {recons.map((r) => (
              <div
                key={r.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 100px 100px 110px 90px',
                  alignItems: 'center',
                  gap: 12,
                  padding: '8px 0',
                  borderBottom: '1px solid var(--bd-1)',
                  fontSize: 11.5,
                }}
              >
                <span style={{ color: 'var(--fg-1)', fontWeight: 500 }}>{r.sku_id}</span>
                <span className="tabular" style={{ color: 'var(--fg-2)' }}>
                  teór. {r.theoretical_qty}
                </span>
                <span className="tabular" style={{ color: 'var(--fg-2)' }}>
                  fís. {r.physical_qty}
                </span>
                <span
                  className="tabular"
                  style={{
                    color: r.variance_qty === 0 ? 'var(--fg-3)' : 'var(--orange)',
                  }}
                >
                  Δ {r.variance_qty > 0 ? '+' : ''}
                  {r.variance_qty}
                </span>
                <span
                  style={{
                    color: r.resolved ? 'var(--green)' : 'var(--yellow)',
                    fontWeight: 500,
                  }}
                >
                  {r.resolved ? 'Resolvida' : 'Aberta'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · ENTREGAS  (Q.53.D/J — tracking de encomendas a fornecedor)
// ═══════════════════════════════════════════════════════════════════════════
