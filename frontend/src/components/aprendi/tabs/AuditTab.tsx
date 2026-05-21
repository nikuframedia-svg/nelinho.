// Aprendi · AuditTab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { apiFetch } from '../../../lib/api';
import { Card, SectionHeader, TabState } from '../atoms';

export function AuditTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['governance', 'audit-timeline'],
    queryFn: () =>
      apiFetch<{ events: Array<Record<string, unknown>> }>(
        '/v1/governance/audit/timeline?limit=200',
      ),
  });
  const events = data?.events ?? [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={events.length === 0}
      emptyText="Sem eventos no trilho de auditoria."
    >
      <Card padding={0}>
        <div
          style={{
            padding: '12px 18px',
            borderBottom: '1px solid var(--bd-1)',
          }}
        >
          <SectionHeader
            title="Trilho de auditoria"
            subtitle="Cada decisão tem origem · imutável · hash-encadeado"
          />
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '170px 150px 1fr',
            padding: '10px 18px',
            borderBottom: '1px solid var(--bd-1)',
            background: 'var(--bg-2)',
            fontSize: 10.5,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
            gap: 12,
          }}
        >
          <div>Timestamp</div>
          <div>Autor</div>
          <div>Evento</div>
        </div>
        {events.map((e, i) => (
          <div
            key={i}
            style={{
              display: 'grid',
              gridTemplateColumns: '170px 150px 1fr',
              padding: '10px 18px',
              borderBottom:
                i < events.length - 1 ? '1px solid var(--bd-1)' : 'none',
              gap: 12,
              fontSize: 12,
            }}
          >
            <span
              className="mono tabular"
              style={{ color: 'var(--fg-3)' }}
            >
              {e.timestamp || e.ts || e.at
                ? new Date(
                    String(e.timestamp ?? e.ts ?? e.at),
                  ).toLocaleString('pt-PT')
                : '—'}
            </span>
            <span style={{ color: 'var(--fg-1)' }}>
              {String(e.actor ?? e.by ?? e.who ?? 'sistema')}
            </span>
            <span style={{ color: 'var(--fg-1)' }}>
              {String(e.event ?? e.action ?? e.type ?? '—')}
            </span>
          </div>
        ))}
      </Card>
    </TabState>
  );
}

// ─── Tab: Factory data product ──────────────────────────────────────
