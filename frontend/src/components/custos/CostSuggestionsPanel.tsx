/**
 * CostSuggestionsPanel — painel "Sugestões de redução de custo" (Q.54.L).
 *
 * Liga aos endpoints REAIS de Q.54.H:
 *   - POST /v1/profit/cost-reduction-suggestions          (lista)
 *   - POST /v1/profit/cost-reduction-suggestions/decision (cria Decisão)
 *
 * Cada sugestão é um outlier de custo (barco/centro acima da mediana do
 * tipo). O botão "Criar decisão" promove a sugestão a um DecisionRun no
 * Inbox de governança — fica a aguardar aprovação humana.
 *
 * ZERO MOCKS: a lista vem toda do backend; sem sugestões mostra a
 * `reason` honesta (custos dentro do esperado, sem COGS calculado…).
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Lightbulb, CheckCircle2 } from 'lucide-react';
import { DarkBadge, DarkButton, EmptyState, Panel } from '../dark';
import { custosApi } from '../../pages/custos/custosApi';
import type { CostReductionSuggestion } from '../../pages/custos/custosApi';

function fmtEur(n: number): string {
  return `€${Math.round(n).toLocaleString('pt-PT')}`;
}

export function CostSuggestionsPanel(): ReactNode {
  const queryClient = useQueryClient();

  const suggestionsQuery = useQuery({
    queryKey: ['custos', 'cost-reduction-suggestions'],
    queryFn: () => custosApi.costReductionSuggestions({ limit: 20 }),
    refetchOnWindowFocus: false,
    staleTime: 5 * 60_000,
  });

  // order_id da sugestão a ser promovida agora — para o estado do botão.
  const [busyOrderId, setBusyOrderId] = useState<string | null>(null);
  // Sugestões já promovidas nesta sessão (decisão criada).
  const [createdFor, setCreatedFor] = useState<Set<string>>(new Set());

  const decisionMutation = useMutation({
    mutationFn: (s: CostReductionSuggestion) =>
      custosApi.createSuggestionDecision(s),
    onMutate: (s) => setBusyOrderId(s.order_id),
    onSuccess: (_res, s) => {
      setCreatedFor((prev) => new Set(prev).add(s.order_id));
      // A nova decisão aparece no Inbox e conta para o impacto-PP1.
      queryClient.invalidateQueries({ queryKey: ['decisions'] });
      queryClient.invalidateQueries({ queryKey: ['painel', 'decisions'] });
      queryClient.invalidateQueries({ queryKey: ['custos', 'objectives'] });
    },
    onSettled: () => setBusyOrderId(null),
  });

  const data = suggestionsQuery.data ?? null;
  const suggestions = data?.suggestions ?? [];

  return (
    <Panel
      title="Sugestões de redução de custo"
      badge={suggestions.length}
      subtitle="Outliers de COGS — barco/centro acima da mediana do tipo de produto"
      action={
        data && data.total_opportunity_eur > 0 ? (
          <span style={{ fontSize: 11.5, color: 'var(--green)' }}>
            {fmtEur(data.total_opportunity_eur)} de oportunidade
          </span>
        ) : undefined
      }
    >
      {suggestionsQuery.isLoading ? (
        <div
          style={{
            padding: 20,
            textAlign: 'center',
            fontSize: 12,
            color: 'var(--fg-3)',
          }}
        >
          A analisar os custos…
        </div>
      ) : suggestionsQuery.isError ? (
        <EmptyState
          mascot={false}
          size="sm"
          title="Sugestões indisponíveis"
          hint="A análise de redução de custo não respondeu."
          action={
            <DarkButton
              size="sm"
              onClick={() => suggestionsQuery.refetch()}
            >
              Tentar novamente
            </DarkButton>
          }
        />
      ) : suggestions.length === 0 ? (
        <EmptyState
          mascot={false}
          size="sm"
          icon={<CheckCircle2 size={24} />}
          title="Sem desvios de custo"
          hint={
            data?.reason ??
            'Os custos por barco estão dentro do esperado — nenhum outlier encontrado.'
          }
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {suggestions.map((s) => {
            const created = createdFor.has(s.order_id);
            const busy = busyOrderId === s.order_id;
            return (
              <div
                key={`${s.order_id}-${s.cost_center}`}
                style={{
                  background: 'var(--bg-2)',
                  border: '1px solid var(--bd-1)',
                  borderRadius: 'var(--r-md)',
                  padding: 12,
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'space-between',
                    gap: 12,
                  }}
                >
                  <div style={{ minWidth: 0 }}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        marginBottom: 4,
                      }}
                    >
                      <Lightbulb size={13} color="var(--accent)" />
                      <span
                        style={{
                          fontSize: 12.5,
                          fontWeight: 600,
                          color: 'var(--fg-0)',
                        }}
                      >
                        {s.title}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: 11.5,
                        color: 'var(--fg-2)',
                        lineHeight: 1.5,
                      }}
                    >
                      {s.explanation}
                    </div>
                    <div
                      style={{
                        display: 'flex',
                        gap: 12,
                        marginTop: 6,
                        fontSize: 10.5,
                        color: 'var(--fg-3)',
                      }}
                    >
                      <span>
                        Centro:{' '}
                        <strong style={{ color: 'var(--fg-1)' }}>
                          {s.cost_center_label}
                        </strong>
                      </span>
                      <span>
                        Barco {fmtEur(s.boat_cost_eur)} · mediana{' '}
                        {fmtEur(s.baseline_cost_eur)}
                      </span>
                    </div>
                  </div>
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'flex-end',
                      gap: 6,
                      flexShrink: 0,
                    }}
                  >
                    <DarkBadge variant="warning" size="sm">
                      +{fmtEur(s.overspend_eur)}
                    </DarkBadge>
                    {created ? (
                      <span
                        style={{
                          fontSize: 11,
                          color: 'var(--green)',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 4,
                          whiteSpace: 'nowrap',
                        }}
                      >
                        <CheckCircle2 size={12} />
                        Decisão criada
                      </span>
                    ) : (
                      <DarkButton
                        size="sm"
                        disabled={busy}
                        onClick={() => decisionMutation.mutate(s)}
                      >
                        {busy ? 'A criar…' : 'Criar decisão'}
                      </DarkButton>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          {decisionMutation.isError && (
            <div
              style={{
                fontSize: 11.5,
                color: 'var(--red)',
                padding: '6px 2px',
              }}
            >
              Não foi possível criar a decisão. Tenta novamente.
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

export default CostSuggestionsPanel;
