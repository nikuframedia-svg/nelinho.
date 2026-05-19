// Aprendi · CausalTab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { Brain } from 'lucide-react';
import { catalogApi } from '../../../lib/api';
import { Card, SectionHeader, Tag, TabState } from '../atoms';

export function CausalTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['explain', 'catalog'],
    queryFn: () => catalogApi.getMetrics(),
  });
  const metrics: Array<Record<string, unknown>> = Array.isArray(data)
    ? data
    : Array.isArray((data as Record<string, unknown>)?.metrics)
      ? ((data as Record<string, unknown>).metrics as Array<
          Record<string, unknown>
        >)
      : [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={metrics.length === 0}
      emptyText="Sem catálogo de métricas explicáveis disponível."
    >
      <Card padding={18}>
        <SectionHeader
          icon={<Brain size={14} />}
          title="Catálogo de métricas explicáveis"
          subtitle="Cada métrica tem origem rastreável · diagnóstico causal"
        />
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          {metrics.map((m, i) => (
            <div
              key={String(m.id ?? m.metric_id ?? i)}
              style={{
                padding: '10px 12px',
                background: 'var(--bg-2)',
                border: '1px solid var(--bd-1)',
                borderRadius: 'var(--r-sm)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 12.5,
                    color: 'var(--fg-0)',
                    fontWeight: 500,
                  }}
                >
                  {String(m.label ?? m.name ?? m.id ?? m.metric_id)}
                </div>
                {m.description ? (
                  <div
                    style={{ fontSize: 11, color: 'var(--fg-3)' }}
                  >
                    {String(m.description)}
                  </div>
                ) : null}
              </div>
              <Tag
                tone={m.blocked === true ? 'red' : 'green'}
                size="sm"
              >
                {m.blocked === true ? 'bloqueada' : 'disponível'}
              </Tag>
            </div>
          ))}
        </div>
      </Card>
    </TabState>
  );
}

// ─── Tab: Copilot extras ────────────────────────────────────────────
