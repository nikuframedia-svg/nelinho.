// ConfiguracaoPage · AprendizagemTab (Q.60.U). ZERO MOCKS — endpoints reais.
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2, Target } from 'lucide-react';
import { KPIBig, EmptyState } from '../../../components/dark';
import { learningApi } from '../../../lib/api';
import { ConfigCard, SectionHeader } from '../configuracaoShared';

export function AprendizagemTab() {
  const rulesQ = useQuery({
    queryKey: ['config-learning', 'rules'],
    queryFn: () => learningApi.rules(),
    staleTime: 60_000,
    retry: false,
  });
  const weightsQ = useQuery({
    queryKey: ['config-learning', 'weights'],
    queryFn: () => learningApi.weights(),
    staleTime: 60_000,
    retry: false,
  });

  const rules = rulesQ.data;
  const weights = weightsQ.data;

  const confirmed = rules?.by_status?.confirmed ?? 0;
  const detected = rules?.by_status?.detected ?? 0;
  const rejected = rules?.by_status?.rejected ?? 0;
  const totalRules = confirmed + detected + rejected;
  const rejectionRate = totalRules > 0 ? (rejected / totalRules) * 100 : 0;

  const weightRows = useMemo(() => {
    if (!weights?.current_weights) return [];
    return Object.entries(weights.current_weights).map(([key, learned]) => ({
      key: key.replace(/^w_/, ''),
      learned,
      def: weights.default_weights?.[key] ?? 0,
    }));
  }, [weights]);

  return (
    <div className="space-y-3.5">
      <div className="grid grid-cols-4 gap-3">
        <KPIBig
          label="Regras confirmadas"
          value={confirmed}
          status="accent"
          accent="accent"
        />
        <KPIBig label="Em revisão" value={detected} status="yellow" accent="yellow" />
        <KPIBig label="Rejeitadas" value={rejected} status="gray" />
        <KPIBig
          label="Taxa de rejeição"
          value={Math.round(rejectionRate)}
          unit="%"
          context="das regras aprendidas alguma vez detectadas"
          status={rejectionRate < 20 ? 'green' : 'orange'}
        />
      </div>

      <ConfigCard>
        <div
          style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
        >
          <SectionHeader
            icon={<Target size={14} />}
            title="Pesos da fitness · aprendidos vs default"
            subtitle="Como o CPO pondera cada objectivo — ajustado pelas decisões reais"
          />
        </div>
        <div className="p-[18px]">
          {weightsQ.isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={20} className="text-accent-500 animate-spin" />
            </div>
          ) : weightRows.length === 0 ? (
            <EmptyState
              title="Sem pesos aprendidos"
              hint={
                weights?.reason ??
                'Quando o sistema observar decisões suficientes, ajusta os pesos automaticamente. Até lá, usa os defaults NELO.'
              }
            />
          ) : (
            <div className="flex flex-col gap-3">
              {weightRows.map((w) => {
                const diff = w.learned - w.def;
                return (
                  <div key={w.key}>
                    <div className="flex justify-between items-baseline mb-1.5">
                      <span className="text-[12px] text-text-dark-secondary capitalize">
                        {w.key}
                      </span>
                      <span className="tabular-nums text-[11px] text-text-dark-tertiary">
                        default{' '}
                        <span className="text-text-dark-secondary">
                          {w.def.toFixed(2)}
                        </span>{' '}
                        → aprendido{' '}
                        <span
                          className="font-semibold"
                          style={{
                            color:
                              diff > 0.001
                                ? 'var(--green)'
                                : diff < -0.001
                                  ? 'var(--red)'
                                  : 'var(--fg-1)',
                          }}
                        >
                          {w.learned.toFixed(2)}
                        </span>
                      </span>
                    </div>
                    <div
                      style={{
                        position: 'relative',
                        height: 5,
                        background: 'var(--bd-1)',
                        borderRadius: 3,
                      }}
                    >
                      <div
                        style={{
                          position: 'absolute',
                          inset: '0 auto 0 0',
                          width: `${Math.min(100, w.def * 250)}%`,
                          background: 'var(--bd-3)',
                          borderRadius: 3,
                        }}
                      />
                      <div
                        style={{
                          position: 'absolute',
                          inset: '0 auto 0 0',
                          width: `${Math.min(100, w.learned * 250)}%`,
                          background: 'var(--accent)',
                          borderRadius: 3,
                          opacity: 0.85,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
              <p className="text-[10.5px] text-text-dark-tertiary mt-1">
                Treinado com{' '}
                <span className="text-text-dark-secondary">
                  {weights?.pairs_used ?? 0}
                </span>{' '}
                pares ·{' '}
                {weights?.trained_at
                  ? new Date(weights.trained_at).toLocaleString('pt-PT')
                  : 'nunca treinado'}{' '}
                · gerir promote/rollback de adapters em Aprendi → Camadas.
              </p>
            </div>
          )}
        </div>
      </ConfigCard>
    </div>
  );
}

// ═══ Tab Custos ══════════════════════════════════════════════════════════════
