// Aprendi · ResumoTab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { Sparkles, Target } from 'lucide-react';
import { learningApi } from '../../../lib/api';
import { Card, MiniBar, SectionHeader, TabState, toneVar, type Tone } from '../atoms';

export function ResumoTab(): ReactNode {
  const weights = useQuery({
    queryKey: ['learning', 'weights'],
    queryFn: () => learningApi.weights(),
  });
  const rules = useQuery({
    queryKey: ['learning', 'rules'],
    queryFn: () => learningApi.rules(),
  });
  const pairs = useQuery({
    queryKey: ['learning', 'pairs'],
    queryFn: () => learningApi.pairs(),
  });

  const loading = weights.isLoading || rules.isLoading || pairs.isLoading;
  const error = weights.error ?? rules.error ?? pairs.error;

  return (
    <TabState
      loading={loading}
      error={error}
      empty={false}
      emptyText=""
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 10,
          marginBottom: 14,
        }}
      >
        <SummaryStat
          label="Regras aprendidas"
          value={rules.data?.total ?? 0}
          tone="blue"
        />
        <SummaryStat
          label="Pares de treino"
          value={pairs.data?.total_pairs ?? 0}
          tone="green"
        />
        <SummaryStat
          label="Elegíveis p/ DPO"
          value={pairs.data?.eligible_for_dpo ?? 0}
          tone="purple"
        />
        <SummaryStat
          label="Pesos a aprender"
          value={
            weights.data
              ? Object.keys(weights.data.current_weights ?? {}).length
              : 0
          }
          tone="teal"
        />
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.2fr 1fr',
          gap: 14,
        }}
      >
        <Card padding={18}>
          <SectionHeader
            icon={<Target size={14} />}
            title="Pesos da fitness"
            subtitle="Default NELO vs ajuste aprendido pelas decisões"
          />
          <FitnessWeights weights={weights.data ?? null} />
        </Card>
        <Card padding={18}>
          <SectionHeader
            icon={<Sparkles size={14} />}
            title="Detector de regras"
            subtitle="Padrões observados nas decisões humanas"
          />
          {rules.data ? (
            <div
              style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
            >
              {Object.entries(rules.data.by_status ?? {}).map(
                ([status, count]) => (
                  <div
                    key={status}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 11px',
                      background: 'var(--bg-2)',
                      borderRadius: 'var(--r-sm)',
                      fontSize: 12,
                    }}
                  >
                    <span style={{ color: 'var(--fg-1)' }}>{status}</span>
                    <span
                      className="tabular"
                      style={{ color: 'var(--fg-0)', fontWeight: 600 }}
                    >
                      {count}
                    </span>
                  </div>
                ),
              )}
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--fg-3)',
                  marginTop: 4,
                }}
              >
                Última deteção:{' '}
                {rules.data.last_detector_run_at
                  ? new Date(
                      rules.data.last_detector_run_at,
                    ).toLocaleString('pt-PT')
                  : 'nunca'}
              </div>
            </div>
          ) : (
            <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>
              Sem dados do detector.
            </span>
          )}
        </Card>
      </div>
    </TabState>
  );
}

export function SummaryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: Tone;
}): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding: 16,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          bottom: 0,
          width: 2,
          background: toneVar(tone),
          opacity: 0.5,
        }}
      />
      <div
        style={{
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.3,
          fontWeight: 500,
        }}
      >
        {label}
      </div>
      <div
        className="display tabular"
        style={{
          fontSize: 28,
          color: 'var(--fg-0)',
          fontWeight: 500,
          marginTop: 8,
        }}
      >
        {value.toLocaleString('pt-PT')}
      </div>
    </div>
  );
}

export function FitnessWeights({
  weights,
}: {
  weights: {
    current_weights?: Record<string, number>;
    default_weights?: Record<string, number>;
  } | null;
}): ReactNode {
  if (!weights || !weights.current_weights) {
    return (
      <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>
        Sem pesos de fitness disponíveis.
      </span>
    );
  }
  const current = weights.current_weights;
  const def = weights.default_weights ?? {};
  const keys = Object.keys(current);
  const maxW = Math.max(...keys.map((k) => current[k]), 0.01);
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          marginBottom: 12,
          padding: '8px 10px',
          background: 'var(--bg-2)',
          borderRadius: 6,
        }}
      >
        <strong style={{ color: 'var(--fg-1)' }}>Default</strong> = padrão
        NELO ·{' '}
        <strong style={{ color: 'var(--accent)' }}>Aprendido</strong> =
        ajustado pelas decisões
      </div>
      {keys.map((k) => {
        const cur = current[k];
        const dft = def[k] ?? cur;
        const diff = cur - dft;
        return (
          <div key={k} style={{ marginBottom: 11 }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: 5,
              }}
            >
              <span style={{ fontSize: 11.5, color: 'var(--fg-1)' }}>
                {k}
              </span>
              <span
                className="tabular"
                style={{ fontSize: 11, color: 'var(--fg-3)' }}
              >
                <span style={{ color: 'var(--fg-2)' }}>
                  {dft.toFixed(2)}
                </span>{' '}
                →{' '}
                <span
                  style={{
                    color:
                      diff > 0
                        ? 'var(--green)'
                        : diff < 0
                          ? 'var(--red)'
                          : 'var(--fg-1)',
                    fontWeight: 600,
                  }}
                >
                  {cur.toFixed(2)}
                </span>
              </span>
            </div>
            <MiniBar value={(cur / maxW) * 100} />
          </div>
        );
      })}
    </div>
  );
}

// ─── Tab: Regras NL→DSL Q.17 ────────────────────────────────────────
