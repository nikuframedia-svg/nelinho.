// Aprendi · TwinSandboxTab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { FlaskConical } from 'lucide-react';
import { apiFetch } from '../../../lib/api';
import { Card, SectionHeader, TabState, toneVar, type Tone } from '../atoms';

export function TwinSandboxTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['twin', 'scenarios', 'aprendi'],
    queryFn: () => apiFetch<Array<Record<string, unknown>>>(
      '/v1/twin/scenarios',
    ),
  });
  const scenarios = Array.isArray(data) ? data : [];
  const simulated = scenarios.filter(
    (s) => !!s.simulation_result,
  ).length;
  const solved = scenarios.filter((s) => s.status === 'SOLVED').length;

  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={false}
      emptyText=""
    >
      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}
      >
        <Card padding={18}>
          <SectionHeader
            icon={<FlaskConical size={14} />}
            title="Digital twin sandbox"
            subtitle="Cópia isolada da BD · corre what-ifs sem tocar produção"
          />
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: 8,
            }}
          >
            <SandboxStat label="Cenários" value={scenarios.length} />
            <SandboxStat label="Simulados" value={simulated} />
            <SandboxStat
              label="Resolvidos"
              value={solved}
              tone="green"
            />
            <SandboxStat
              label="Por simular"
              value={scenarios.length - simulated}
              tone="yellow"
            />
          </div>
        </Card>
        <Card padding={18}>
          <SectionHeader title="Como funciona" />
          <ol
            style={{
              paddingLeft: 18,
              margin: 0,
              fontSize: 12,
              color: 'var(--fg-1)',
              lineHeight: 1.7,
            }}
          >
            <li>Snapshot da BD de produção (read-only)</li>
            <li>Aplica a mudança proposta na cópia</li>
            <li>Valida os 7 axiomas Spelke</li>
            <li>Mede o impacto · €, dias, OTD</li>
            <li>Descarta a cópia · devolve o veredicto</li>
          </ol>
        </Card>
      </div>
    </TabState>
  );
}

export function SandboxStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: Tone;
}): ReactNode {
  return (
    <div
      style={{
        padding: 10,
        background: 'var(--bg-2)',
        borderRadius: 6,
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
        }}
      >
        {label}
      </div>
      <div
        className="display tabular"
        style={{
          fontSize: 22,
          fontWeight: 500,
          color: tone ? toneVar(tone) : 'var(--fg-0)',
        }}
      >
        {value}
      </div>
    </div>
  );
}

// ─── Tab: Showcase ──────────────────────────────────────────────────
