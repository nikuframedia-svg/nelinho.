// Aprendi · Camada1Tab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { preferenceRulesApi, type PreferenceRule } from '../../../lib/api';
import { Card, SectionHeader, TabState } from '../atoms';
import { RuleStatusBadge } from './aprendiTabBits';

export function Camada1Tab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['preference-rules', 'all'],
    queryFn: () => preferenceRulesApi.list({ limit: 100 }),
  });
  const rules: PreferenceRule[] = Array.isArray(data) ? data : [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={rules.length === 0}
      emptyText="Sem regras de preferência aprendidas. O sistema regista padrões à medida que tomas decisões."
    >
      <Card padding={18}>
        <SectionHeader
          title="Camada 1 · Regras aprendidas (soft)"
          subtitle="Padrões observados, não definidos · convivem com as regras Q.17"
        />
        {rules.map((r) => (
          <div
            key={r.id}
            style={{
              padding: '12px 14px',
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-sm)',
              marginBottom: 8,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: 4,
              }}
            >
              <span
                style={{
                  fontSize: 12.5,
                  color: 'var(--fg-0)',
                  fontWeight: 500,
                }}
              >
                {r.description || r.type}
              </span>
              <RuleStatusBadge status={r.status} />
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              Confiança {Math.round(r.confidence * 100)}% · {r.type}
            </div>
          </div>
        ))}
      </Card>
    </TabState>
  );
}

// ─── Tab: Q.17 Avançado — arquitectura fixa do DSL ──────────────────
