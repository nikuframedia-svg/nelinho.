// Aprendi · CopilotTab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { copilotApi } from '../../../lib/api';
import { Card, SectionHeader, TabState } from '../atoms';

export function CopilotTab(): ReactNode {
  // O endpoint real é /api/copilot/insights (copilotApi.getInsights), que
  // devolve { date, now[], next[], meta }. Juntamos as bandas "now" e
  // "next" numa lista única de aprendizagens.
  const { data, isLoading, error } = useQuery({
    queryKey: ['copilot', 'insights', 'aprendi'],
    queryFn: () => copilotApi.getInsights(),
  });
  const raw = data as Record<string, unknown> | undefined;
  const insights: Array<Record<string, unknown>> = Array.isArray(raw)
    ? (raw as Array<Record<string, unknown>>)
    : [
        ...(Array.isArray(raw?.now)
          ? (raw!.now as Array<Record<string, unknown>>)
          : []),
        ...(Array.isArray(raw?.next)
          ? (raw!.next as Array<Record<string, unknown>>)
          : []),
        ...(Array.isArray(raw?.insights)
          ? (raw!.insights as Array<Record<string, unknown>>)
          : []),
      ];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={insights.length === 0}
      emptyText="Sem aprendizagens registadas pelo copiloto."
    >
      <Card padding={18}>
        <SectionHeader
          title="Aprendizagens do copiloto"
          subtitle="O que o copiloto on-prem aprendeu com o feedback dos utilizadores"
        />
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          {insights.map((ins, i) => (
            <div
              key={String(ins.id ?? i)}
              style={{
                padding: 11,
                background: 'var(--bg-2)',
                borderRadius: 6,
                fontSize: 12,
                color: 'var(--fg-1)',
              }}
            >
              {String(
                ins.text ?? ins.summary ?? ins.message ?? ins.title ?? '',
              )}
            </div>
          ))}
        </div>
      </Card>
    </TabState>
  );
}

// ─── Tab: Governance / Audit (hash-chain) ───────────────────────────
