// Aprendi · FdpTab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { Boxes } from 'lucide-react';
import { capabilitiesApi } from '../../../lib/api';
import { Card, SectionHeader, Tag, TabState } from '../atoms';

export function FdpTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['capabilities', 'aprendi'],
    queryFn: () => capabilitiesApi.get(),
  });

  // Extrai data products / módulos do payload de capabilities.
  const raw = data as Record<string, unknown> | undefined;
  const products: Array<Record<string, unknown>> = Array.isArray(
    raw?.data_products,
  )
    ? (raw!.data_products as Array<Record<string, unknown>>)
    : Array.isArray(raw?.modules)
      ? (raw!.modules as Array<Record<string, unknown>>)
      : Array.isArray(raw?.features)
        ? (raw!.features as Array<Record<string, unknown>>)
        : [];

  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={products.length === 0}
      emptyText="Sem factory data products reportados pelo /v1/capabilities."
    >
      <Card padding={0}>
        <div
          style={{
            padding: '12px 18px',
            borderBottom: '1px solid var(--bd-1)',
          }}
        >
          <SectionHeader
            icon={<Boxes size={14} />}
            title="Factory data product"
            subtitle="Capacidades reportadas pelo sistema · freshness"
          />
        </div>
        {products.map((d, i) => {
          const available =
            d.available === true ||
            d.enabled === true ||
            d.status === 'ok' ||
            d.status === 'available';
          return (
            <div
              key={String(d.name ?? d.id ?? i)}
              style={{
                display: 'grid',
                gridTemplateColumns: '2fr 1fr 100px',
                padding: '10px 18px',
                borderBottom:
                  i < products.length - 1
                    ? '1px solid var(--bd-1)'
                    : 'none',
                gap: 12,
                alignItems: 'center',
                fontSize: 12,
              }}
            >
              <span
                className="mono"
                style={{ color: 'var(--fg-1)' }}
              >
                {String(d.name ?? d.id ?? d.key ?? 'data product')}
              </span>
              <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>
                {String(d.freshness ?? d.description ?? d.detail ?? '')}
              </span>
              <Tag tone={available ? 'green' : 'yellow'} size="sm">
                {available ? 'disponível' : 'parcial'}
              </Tag>
            </div>
          );
        })}
      </Card>
    </TabState>
  );
}

// ─── Tab: ML registry ───────────────────────────────────────────────
