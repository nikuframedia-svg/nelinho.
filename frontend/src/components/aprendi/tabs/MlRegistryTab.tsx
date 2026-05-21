// Aprendi · MlRegistryTab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { mlApi } from '../../../lib/api';
import { Card, Tag, TabState } from '../atoms';

export function MlRegistryTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['ml', 'models', 'list'],
    queryFn: () => mlApi.listModels(),
  });
  const models: string[] = Array.isArray(data) ? data : [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={models.length === 0}
      emptyText="Sem modelos no ML registry."
    >
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        {models.map((name) => (
          <MlModelRow key={name} name={name} />
        ))}
      </div>
    </TabState>
  );
}

export function MlModelRow({ name }: { name: string }): ReactNode {
  const versions = useQuery({
    queryKey: ['ml', 'versions', name],
    queryFn: () => mlApi.listVersions(name, { limit: 1 }),
  });
  const active = useQuery({
    queryKey: ['ml', 'active', name],
    queryFn: () => mlApi.getActive(name),
    retry: false,
  });
  const latest = versions.data?.[0] as Record<string, unknown> | undefined;
  const activeArtifact = active.data as
    | Record<string, unknown>
    | undefined;
  return (
    <Card padding={14}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 13,
              color: 'var(--fg-0)',
              fontWeight: 600,
            }}
          >
            {name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
            {versions.data
              ? `${versions.data.length === 0 ? 'sem' : ''} versões registadas`
              : 'a carregar versões…'}
            {latest?.created_at
              ? ` · última ${new Date(
                  String(latest.created_at),
                ).toLocaleDateString('pt-PT')}`
              : ''}
          </div>
        </div>
        <Tag tone={activeArtifact ? 'green' : 'yellow'} size="sm">
          {activeArtifact
            ? `activa ${String(
                activeArtifact.version ?? activeArtifact.id ?? '',
              ).slice(0, 8)}`
            : 'sem versão activa'}
        </Tag>
      </div>
    </Card>
  );
}

// ─── Tab: Twin sandbox ──────────────────────────────────────────────
