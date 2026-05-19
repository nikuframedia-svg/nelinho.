// Aprendi · Q17AdvancedTab (Q.60.X). ZERO MOCKS — endpoints reais.
import { type ReactNode } from 'react';
import { Card } from '../atoms';

export function Q17AdvancedTab(): ReactNode {
  // Whitelist fechada do DSL Q.17 — estrutura conhecida do sistema,
  // não dados (Pydantic Literal[...] no backend força estes valores).
  const blocks = [
    {
      label: 'Eventos DSL',
      count: 12,
      hint: 'mold_usage_threshold, defect_detected, phase_load_above, weekday, worker_assignment_proposed…',
    },
    {
      label: 'Acções',
      count: 9,
      hint: 'propose_maintenance, route_back, realloc_workers, block, auto_accept…',
    },
    {
      label: 'Operadores',
      count: 8,
      hint: '==, !=, <, >, in, contains, matches, between',
    },
    {
      label: 'Axiomas Spelke',
      count: 7,
      hint: 'continuity, exclusivity, identity, contact, agency, cohesion, solidity',
    },
  ];
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 10,
      }}
    >
      {blocks.map((b) => (
        <Card key={b.label} padding={16}>
          <div
            style={{
              fontSize: 10.5,
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
              fontWeight: 600,
            }}
          >
            {b.label}
          </div>
          <div
            className="display tabular"
            style={{ fontSize: 28, fontWeight: 500, marginTop: 6 }}
          >
            {b.count}
          </div>
          <div
            style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}
          >
            {b.hint}
          </div>
        </Card>
      ))}
    </div>
  );
}

// ─── Tab: 4 Camadas de Aprendizagem ─────────────────────────────────
