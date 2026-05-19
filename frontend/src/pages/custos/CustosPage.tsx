/**
 * CustosPage — página Custos (Q.53.I).
 *
 * A casa do dinheiro: custo por barco (COGS), margem por produto,
 * ranking de drivers de custo e simulador de cenários what-if. Substitui
 * as tabs COGS/Pricing/Cenários que viviam embebidas em Relatórios.
 *
 * Endpoints REAIS (módulo profit):
 *   - GET  /v1/profit/cost-ledger        — ledger consolidado
 *   - GET  /v1/profit/kpis/objectives    — bandas-alvo do CEO + impacto-PP1
 *   - POST /v1/profit/scenarios/simulate — simulador (via ScenarioSimulator)
 *
 * ZERO MOCKS: barcos sem `CostCalculation` aparecem como `calculado=não` —
 * nada é imputado. Sem ledger → empty state honesto.
 */

import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Coins, RefreshCw } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import {
  DarkBadge,
  DarkButton,
  EmptyState,
  LiveBadge,
  Panel,
} from '../../components/dark';
import { CostCenterBars } from '../../components/custos/CostCenterBars';
import { CostSuggestionsPanel } from '../../components/custos/CostSuggestionsPanel';
import { ScenarioSimulator } from '../../components/custos/ScenarioSimulator';
import { custosApi } from './custosApi';
import type { BoatCostRow } from './custosApi';

function fmtEur(n: number, decimals = 0): string {
  return `€${n.toLocaleString('pt-PT', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

function fmtPct(p: number | null): string {
  return p === null ? '—' : `${(p * 100).toFixed(1)}%`;
}

export function CustosPage(): ReactNode {
  const ledgerQuery = useQuery({
    queryKey: ['custos', 'cost-ledger'],
    queryFn: () => custosApi.costLedger({ limit: 2000 }),
    refetchOnWindowFocus: false,
  });

  const objectivesQuery = useQuery({
    queryKey: ['custos', 'objectives'],
    queryFn: () => custosApi.kpiObjectives(),
    refetchOnWindowFocus: false,
    staleTime: 5 * 60_000,
  });

  const ledger = ledgerQuery.data ?? null;

  // Barcos calculados primeiro, ordenados por COGS total descendente.
  const sortedBoats: BoatCostRow[] = useMemo(() => {
    if (!ledger) return [];
    return [...ledger.per_boat].sort((a, b) => {
      if (a.calculated !== b.calculated) return a.calculated ? -1 : 1;
      return (b.total_cogs_eur ?? 0) - (a.total_cogs_eur ?? 0);
    });
  }, [ledger]);

  const calculatedBoats = useMemo(
    () => sortedBoats.filter((b) => b.calculated),
    [sortedBoats],
  );

  const [showAllBoats, setShowAllBoats] = useState(false);
  const visibleBoats = showAllBoats ? sortedBoats : sortedBoats.slice(0, 25);

  const pp1 = objectivesQuery.data?.pp1_impact;

  return (
    <DarkPageLayout
      title="Custos"
      subtitle="COGS por barco · margem por produto · drivers de custo · simulador de cenários"
      icon={<Coins size={18} />}
      actions={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <DarkButton
            variant="ghost"
            size="sm"
            onClick={() => ledgerQuery.refetch()}
          >
            <RefreshCw size={12} />
            Atualizar
          </DarkButton>
          <LiveBadge />
        </div>
      }
    >
      {ledgerQuery.isError ? (
        <EmptyState
          mascot={false}
          title="Não foi possível carregar os custos"
          hint="O ledger de custos não respondeu. Verifica se o backend está ligado."
          action={
            <DarkButton size="sm" onClick={() => ledgerQuery.refetch()}>
              Tentar novamente
            </DarkButton>
          }
        />
      ) : ledgerQuery.isLoading ? (
        <div
          style={{
            background: 'var(--bg-1)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-lg)',
            padding: 40,
            textAlign: 'center',
            fontSize: 12,
            color: 'var(--fg-3)',
          }}
        >
          A carregar o ledger de custos…
        </div>
      ) : !ledger || ledger.summary.orders_total === 0 ? (
        <EmptyState
          mascot={false}
          icon={<Coins size={28} />}
          title="Sem custos para mostrar"
          hint="Não há ordens no período. Confirma se a ingestão de ordens correu."
        />
      ) : (
        <>
          {/* Strip de KPIs */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: 10,
              marginBottom: 14,
            }}
          >
            <KpiTile
              label="COGS total"
              value={fmtEur(ledger.summary.total_cogs_eur)}
            />
            <KpiTile
              label="Barcos calculados"
              value={`${ledger.summary.orders_calculated} / ${ledger.summary.orders_total}`}
            />
            <KpiTile
              label="Sem cálculo"
              value={ledger.summary.orders_uncalculated}
              tone={
                ledger.summary.orders_uncalculated > 0 ? 'yellow' : undefined
              }
            />
            <KpiTile
              label="Poupado por sugestões"
              value={
                pp1?.eur_saved !== undefined
                  ? fmtEur(pp1.eur_saved)
                  : '—'
              }
              tone="green"
            />
          </div>

          {/* Drivers de custo + margem por produto */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: 12,
              marginBottom: 12,
            }}
          >
            <Panel
              title="Drivers de custo"
              subtitle="Centros de custo ordenados por € gasto"
            >
              {ledger.cost_drivers.length === 0 ? (
                <div
                  style={{
                    padding: 16,
                    fontSize: 12,
                    color: 'var(--fg-3)',
                    textAlign: 'center',
                  }}
                >
                  Nenhum centro de custo com gasto registado.
                </div>
              ) : (
                <CostCenterBars drivers={ledger.cost_drivers} />
              )}
            </Panel>

            <Panel
              title="Margem por produto"
              badge={ledger.margin_by_product.length}
              subtitle="COGS, receita e margem por tipo de barco"
            >
              {ledger.margin_by_product.length === 0 ? (
                <div
                  style={{
                    padding: 16,
                    fontSize: 12,
                    color: 'var(--fg-3)',
                    textAlign: 'center',
                  }}
                >
                  Sem produtos com COGS calculado.
                </div>
              ) : (
                <table style={{ width: '100%', fontSize: 11.5 }}>
                  <thead>
                    <tr style={{ color: 'var(--fg-3)', textAlign: 'left' }}>
                      <th style={{ padding: '4px 6px', fontWeight: 500 }}>
                        Produto
                      </th>
                      <th
                        style={{
                          padding: '4px 6px',
                          fontWeight: 500,
                          textAlign: 'right',
                        }}
                      >
                        COGS
                      </th>
                      <th
                        style={{
                          padding: '4px 6px',
                          fontWeight: 500,
                          textAlign: 'right',
                        }}
                      >
                        Receita
                      </th>
                      <th
                        style={{
                          padding: '4px 6px',
                          fontWeight: 500,
                          textAlign: 'right',
                        }}
                      >
                        Margem
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {ledger.margin_by_product.map((m) => (
                      <tr
                        key={m.product_type}
                        style={{ borderTop: '1px solid var(--bd-1)' }}
                      >
                        <td style={{ padding: '5px 6px', color: 'var(--fg-0)' }}>
                          {m.product_type}{' '}
                          <span style={{ color: 'var(--fg-3)' }}>
                            ·{m.order_count}
                          </span>
                        </td>
                        <td
                          className="tabular"
                          style={{
                            padding: '5px 6px',
                            textAlign: 'right',
                            color: 'var(--fg-1)',
                          }}
                        >
                          {fmtEur(m.total_cogs_eur)}
                        </td>
                        <td
                          className="tabular"
                          style={{
                            padding: '5px 6px',
                            textAlign: 'right',
                            color: 'var(--fg-1)',
                          }}
                        >
                          {m.total_revenue_eur !== null
                            ? fmtEur(m.total_revenue_eur)
                            : '—'}
                        </td>
                        <td
                          className="tabular"
                          style={{
                            padding: '5px 6px',
                            textAlign: 'right',
                            fontWeight: 600,
                            color:
                              m.margin_eur === null
                                ? 'var(--fg-3)'
                                : m.margin_eur >= 0
                                ? 'var(--green)'
                                : 'var(--red)',
                          }}
                        >
                          {m.margin_eur !== null
                            ? `${fmtEur(m.margin_eur)} (${fmtPct(m.margin_pct)})`
                            : 'sem receita'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Panel>
          </div>

          {/* Sugestões de redução de custo (Q.54.H) */}
          <div style={{ marginBottom: 12 }}>
            <CostSuggestionsPanel />
          </div>

          {/* Simulador de cenários */}
          <div style={{ marginBottom: 12 }}>
            <Panel
              title="Simulador de cenários"
              subtitle="What-if sobre o COGS de um barco base — multiplicadores por componente"
            >
              <ScenarioSimulator boats={calculatedBoats} />
            </Panel>
          </div>

          {/* Custo por barco */}
          <Panel
            title="Custo por barco"
            badge={ledger.per_boat.length}
            subtitle="COGS detalhado e margem por barco"
            action={
              sortedBoats.length > 25 ? (
                <DarkButton
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowAllBoats((v) => !v)}
                >
                  {showAllBoats
                    ? 'Mostrar só o topo'
                    : `Ver todos (${sortedBoats.length})`}
                </DarkButton>
              ) : undefined
            }
          >
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', fontSize: 11.5 }}>
                <thead>
                  <tr style={{ color: 'var(--fg-3)', textAlign: 'left' }}>
                    <th style={{ padding: '4px 6px', fontWeight: 500 }}>
                      Barco
                    </th>
                    <th style={{ padding: '4px 6px', fontWeight: 500 }}>
                      Modelo
                    </th>
                    <th style={{ padding: '4px 6px', fontWeight: 500 }}>
                      Estado
                    </th>
                    <th
                      style={{
                        padding: '4px 6px',
                        fontWeight: 500,
                        textAlign: 'right',
                      }}
                    >
                      COGS
                    </th>
                    <th
                      style={{
                        padding: '4px 6px',
                        fontWeight: 500,
                        textAlign: 'right',
                      }}
                    >
                      Receita
                    </th>
                    <th
                      style={{
                        padding: '4px 6px',
                        fontWeight: 500,
                        textAlign: 'right',
                      }}
                    >
                      Margem
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visibleBoats.map((b) => (
                    <tr
                      key={b.order_id}
                      style={{ borderTop: '1px solid var(--bd-1)' }}
                    >
                      <td style={{ padding: '5px 6px', color: 'var(--fg-0)' }}>
                        #{b.hull}
                      </td>
                      <td style={{ padding: '5px 6px', color: 'var(--fg-1)' }}>
                        {b.product_name ?? b.product_type ?? '—'}
                      </td>
                      <td style={{ padding: '5px 6px' }}>
                        {b.calculated ? (
                          <DarkBadge variant="success" size="sm">
                            calculado
                          </DarkBadge>
                        ) : (
                          <DarkBadge variant="neutral" size="sm">
                            sem cálculo
                          </DarkBadge>
                        )}
                      </td>
                      <td
                        className="tabular"
                        style={{
                          padding: '5px 6px',
                          textAlign: 'right',
                          color: 'var(--fg-1)',
                        }}
                      >
                        {b.total_cogs_eur !== null
                          ? fmtEur(b.total_cogs_eur, 2)
                          : '—'}
                      </td>
                      <td
                        className="tabular"
                        style={{
                          padding: '5px 6px',
                          textAlign: 'right',
                          color: 'var(--fg-1)',
                        }}
                      >
                        {b.revenue_eur !== null
                          ? fmtEur(b.revenue_eur, 2)
                          : '—'}
                      </td>
                      <td
                        className="tabular"
                        style={{
                          padding: '5px 6px',
                          textAlign: 'right',
                          fontWeight: 600,
                          color:
                            b.margin_eur === null
                              ? 'var(--fg-3)'
                              : b.margin_eur >= 0
                              ? 'var(--green)'
                              : 'var(--red)',
                        }}
                      >
                        {b.margin_eur !== null
                          ? `${fmtEur(b.margin_eur, 2)} (${fmtPct(b.margin_pct)})`
                          : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
    </DarkPageLayout>
  );
}

function KpiTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: 'green' | 'yellow' | 'red';
}): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        padding: 12,
      }}
    >
      <div
        style={{
          fontSize: 10.5,
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
          fontSize: 20,
          fontWeight: 500,
          color: tone ? `var(--${tone})` : 'var(--fg-0)',
          marginTop: 4,
        }}
      >
        {value}
      </div>
    </div>
  );
}

export default CustosPage;
