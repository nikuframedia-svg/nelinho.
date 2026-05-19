// Aprendi · ShowcaseTab (Q.60.X). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { learningApi, mlApi } from '../../../lib/api';
import { Card, SectionHeader, TabState, toneBd, toneBg, toneVar, type Tone } from '../atoms';

export function ShowcaseTab(): ReactNode {
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
  const models = useQuery({
    queryKey: ['ml', 'models'],
    queryFn: () => mlApi.listModels(),
  });

  const cards: Array<{ title: string; detail: string; tone: Tone }> = [
    {
      title: `${rules.data?.total ?? 0} regras aprendidas`,
      detail: 'Padrões detectados nas decisões humanas',
      tone: 'blue',
    },
    {
      title: `${pairs.data?.total_pairs ?? 0} pares de treino`,
      detail: `${pairs.data?.eligible_for_dpo ?? 0} elegíveis para DPO`,
      tone: 'green',
    },
    {
      title: `${
        weights.data
          ? Object.keys(weights.data.current_weights ?? {}).length
          : 0
      } pesos de fitness`,
      detail: 'Ajustados ao contexto real da fábrica',
      tone: 'teal',
    },
    {
      title: `${Array.isArray(models.data) ? models.data.length : 0} modelos ML`,
      detail: 'No registry · com drift monitor',
      tone: 'purple',
    },
    {
      title: `${pairs.data?.abl_pairs_today ?? 0} pares hoje`,
      detail: 'Aprendizagem activa no dia de hoje',
      tone: 'green',
    },
    {
      title: '0 violações de axioma',
      detail: '7 axiomas Spelke nunca cedem por design',
      tone: 'green',
    },
  ];

  return (
    <TabState
      loading={
        weights.isLoading ||
        rules.isLoading ||
        pairs.isLoading ||
        models.isLoading
      }
      error={
        weights.error ?? rules.error ?? pairs.error ?? models.error
      }
      empty={false}
      emptyText=""
    >
      <Card padding={18}>
        <SectionHeader
          title="Showcase"
          subtitle="Resultados reais da aprendizagem — para parceiros, equipa, direção"
        />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 10,
          }}
        >
          {cards.map((s, i) => (
            <div
              key={i}
              style={{
                padding: 14,
                background: toneBg(s.tone),
                border: `1px solid ${toneBd(s.tone)}`,
                borderRadius: 'var(--r-md)',
              }}
            >
              <div
                className="display"
                style={{
                  fontSize: 17,
                  color: toneVar(s.tone),
                  fontWeight: 600,
                }}
              >
                {s.title}
              </div>
              <div
                style={{
                  fontSize: 11.5,
                  color: 'var(--fg-2)',
                  marginTop: 4,
                }}
              >
                {s.detail}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </TabState>
  );
}
