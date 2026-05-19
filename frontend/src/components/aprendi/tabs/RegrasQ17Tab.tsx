// Aprendi · RegrasQ17Tab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { yamlPolicyApi } from '../../../lib/api';
import { Card, SectionHeader, TabState } from '../atoms';
import { RuleStatusBadge } from './aprendiTabBits';

export function RegrasQ17Tab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['yaml-policy', 'rules', 'aprendi'],
    queryFn: () => yamlPolicyApi.list({ limit: 100 }),
  });
  const rules = data?.rules ?? [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={rules.length === 0}
      emptyText="Ainda não há regras Q.17. O fluxo completo (PT-PT → YAML → sandbox → aprovação) vive na página de Regras."
    >
      <Card padding={0}>
        <div
          style={{
            padding: '12px 18px',
            borderBottom: '1px solid var(--bd-1)',
          }}
        >
          <SectionHeader
            title="Regras NL→DSL Q.17"
            subtitle={`${rules.length} regras na whitelist fechada`}
          />
        </div>
        {rules.map((r, i) => (
          <div
            key={r.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 110px 110px',
              padding: '11px 18px',
              borderBottom:
                i < rules.length - 1 ? '1px solid var(--bd-1)' : 'none',
              gap: 12,
              alignItems: 'center',
              fontSize: 12,
            }}
          >
            <span style={{ color: 'var(--fg-0)' }}>
              {r.nl_source ?? r.description ?? r.rule_id}
            </span>
            <span
              className="mono"
              style={{ color: 'var(--fg-3)', fontSize: 11 }}
            >
              {r.event_type || '—'}
            </span>
            <RuleStatusBadge status={r.status} />
          </div>
        ))}
      </Card>
    </TabState>
  );
}
