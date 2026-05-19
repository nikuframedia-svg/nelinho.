// QualidadePage · tab ErrosTab (Q.60.Q). ZERO MOCKS — liga a endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { EmptyState } from '../../../components/dark';
import { Card, SectionHeader, MiniBar } from '../../../components/qualidade/QualidadeBits';
import { apiFetch } from '../../../lib/api';
import { type QualityDashboardResponse, type SupplierLotResponse } from '../qualidadeTypes';
import { LoadingLine } from '../qualidadeShared';

export function ErrosTab() {
  const dashboardQuery = useQuery<QualityDashboardResponse>({
    queryKey: ['qualidade', 'dashboard-sku'],
    queryFn: () =>
      apiFetch<QualityDashboardResponse>(
        '/v1/quality/dashboard?group_by=sku&top_n=15',
      ),
    staleTime: 60_000,
    retry: 0,
  });
  const supplierQuery = useQuery<SupplierLotResponse>({
    queryKey: ['qualidade', 'by-supplier'],
    queryFn: () =>
      apiFetch<SupplierLotResponse>('/v1/quality/by-supplier?top_n=10'),
    staleTime: 60_000,
    retry: 0,
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Card padding={18}>
        <SectionHeader
          title="Erros por modelo"
          subtitle="QualityDashboardService · group_by=sku · 30 dias"
        />
        {dashboardQuery.isLoading ? (
          <LoadingLine />
        ) : (dashboardQuery.data?.items ?? []).length === 0 ? (
          <EmptyState
            size="sm"
            title="Sem erros por modelo"
            hint="Não há registos de retrabalho agrupáveis por modelo na janela."
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(dashboardQuery.data?.items ?? []).map((it) => {
              const tone =
                it.share_pct > 25
                  ? 'red'
                  : it.share_pct > 12
                    ? 'orange'
                    : 'yellow';
              return (
                <div
                  key={it.key}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '2fr 1fr 90px',
                    alignItems: 'center',
                    gap: 12,
                    padding: '10px 12px',
                    background: 'var(--bg-2)',
                    borderRadius: 'var(--r-sm)',
                  }}
                >
                  <span style={{ fontSize: 12.5, color: 'var(--fg-0)' }}>
                    {it.key}
                  </span>
                  <MiniBar
                    value={it.events}
                    max={Math.max(
                      ...(dashboardQuery.data?.items ?? []).map(
                        (x) => x.events,
                      ),
                      1,
                    )}
                    color={`var(--${tone})`}
                    height={4}
                    label={`${it.events} ocorrências`}
                  />
                  <span
                    className="tabular"
                    style={{
                      fontSize: 12,
                      color: `var(--${tone})`,
                      fontWeight: 600,
                      textAlign: 'right',
                    }}
                  >
                    {it.share_pct.toFixed(1)}%
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card padding={18}>
        <SectionHeader
          title="Erros por fornecedor"
          subtitle="SupplierQualityService · top 10"
        />
        {supplierQuery.isLoading ? (
          <LoadingLine />
        ) : (supplierQuery.data?.items ?? []).length === 0 ? (
          <EmptyState
            size="sm"
            title="Sem erros atribuídos a fornecedor"
            hint="Não há registos de retrabalho com fornecedor associado."
          />
        ) : (
          (supplierQuery.data?.items ?? []).map((it, i, arr) => (
            <div
              key={(it.supplier_id ?? '') + i}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 90px',
                alignItems: 'center',
                gap: 12,
                padding: '9px 0',
                borderBottom:
                  i < arr.length - 1 ? '1px solid var(--bd-1)' : 'none',
                fontSize: 12,
              }}
            >
              <span style={{ color: 'var(--fg-1)' }}>
                {it.supplier_id ?? '—'}
              </span>
              <span
                className="tabular"
                style={{
                  color: 'var(--orange)',
                  fontWeight: 600,
                  textAlign: 'right',
                }}
              >
                {it.events} ev.
              </span>
            </div>
          ))
        )}
      </Card>
    </div>
  );
}

// ─── MoldesTab ───────────────────────────────────────────────────────────
