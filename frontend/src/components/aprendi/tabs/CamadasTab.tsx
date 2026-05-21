// Aprendi · CamadasTab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { learningApi, mlApi } from '../../../lib/api';
import { Card, TabState } from '../atoms';

export function CamadasTab(): ReactNode {
  const rules = useQuery({
    queryKey: ['learning', 'rules'],
    queryFn: () => learningApi.rules(),
  });
  const weights = useQuery({
    queryKey: ['learning', 'weights'],
    queryFn: () => learningApi.weights(),
  });
  const models = useQuery({
    queryKey: ['ml', 'models'],
    queryFn: () => mlApi.listModels(),
  });

  const layers = [
    {
      n: 1,
      label: 'Regras aprendidas',
      desc: 'Padrões observados em decisões humanas · soft constraints',
      count: rules.data?.total ?? 0,
      unit: 'regras',
    },
    {
      n: 2,
      label: 'Pesos da fitness',
      desc: 'Como ponderar makespan, qualidade, custo, idle, etc.',
      count: weights.data
        ? Object.keys(weights.data.current_weights ?? {}).length
        : 0,
      unit: 'pesos',
    },
    {
      n: 3,
      label: 'Parâmetros',
      desc: 'Thresholds, durações, custos · ajustados ao contexto real',
      count: weights.data
        ? Object.keys(weights.data.multipliers ?? {}).length
        : 0,
      unit: 'multiplicadores',
    },
    {
      n: 4,
      label: 'Modelos ML',
      desc: 'QualityRiskModel, ScheduleFitness, MoldHealth, WorkerScore',
      count: Array.isArray(models.data) ? models.data.length : 0,
      unit: 'modelos',
    },
  ];

  return (
    <TabState
      loading={rules.isLoading || weights.isLoading || models.isLoading}
      error={rules.error ?? weights.error ?? models.error}
      empty={false}
      emptyText=""
    >
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        {layers.map((c) => (
          <Card key={c.n} padding={16}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 14 }}
            >
              <div
                className="display tabular"
                style={{
                  fontSize: 32,
                  color: 'var(--accent)',
                  fontWeight: 500,
                  width: 50,
                }}
              >
                {c.n}
              </div>
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontSize: 13.5,
                    color: 'var(--fg-0)',
                    fontWeight: 600,
                  }}
                >
                  Camada {c.n} · {c.label}
                </div>
                <div
                  style={{
                    fontSize: 11.5,
                    color: 'var(--fg-2)',
                    marginTop: 2,
                  }}
                >
                  {c.desc}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div
                  className="display tabular"
                  style={{
                    fontSize: 22,
                    color: 'var(--fg-0)',
                    fontWeight: 500,
                  }}
                >
                  {c.count}
                </div>
                <div style={{ fontSize: 10, color: 'var(--fg-3)' }}>
                  {c.unit}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </TabState>
  );
}

// ─── Tab: Causal / Explain ──────────────────────────────────────────
