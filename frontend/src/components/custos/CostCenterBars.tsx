/**
 * CostCenterBars — barras horizontais dos 6 centros de custo COGS (Q.53.I).
 *
 * Mostra `material / labor / machine / setup / overhead / scrap` ordenados
 * por € gasto, com a quota relativa. Dados 100% por props vindos do
 * `cost-ledger`. ZERO MOCKS — lista vazia → o pai mostra empty state.
 */

import type { ReactNode } from 'react';
import type { CostDriver } from '../../pages/custos/custosApi';

/** Rótulos PT-PT dos centros de custo (chaves técnicas do backend). */
const COST_CENTER_LABEL: Record<string, string> = {
  material: 'Material',
  labor: 'Mão-de-obra',
  machine: 'Máquina',
  setup: 'Preparação',
  overhead: 'Estrutura',
  scrap: 'Refugo',
};

export interface CostCenterBarsProps {
  drivers: CostDriver[];
}

function fmtEur(n: number): string {
  return `€${n.toLocaleString('pt-PT', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

export function CostCenterBars({ drivers }: CostCenterBarsProps): ReactNode {
  const max = drivers.reduce((m, d) => Math.max(m, d.total_eur), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {drivers.map((d) => {
        const pct = max > 0 ? (d.total_eur / max) * 100 : 0;
        return (
          <div key={d.cost_center}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: 3,
              }}
            >
              <span style={{ fontSize: 12, color: 'var(--fg-1)' }}>
                <span
                  className="tabular"
                  style={{ color: 'var(--fg-3)', marginRight: 6 }}
                >
                  #{d.rank}
                </span>
                {COST_CENTER_LABEL[d.cost_center] ?? d.cost_center}
              </span>
              <span
                className="tabular"
                style={{ fontSize: 12, fontWeight: 600, color: 'var(--fg-0)' }}
              >
                {fmtEur(d.total_eur)}
                {d.share_pct !== null && (
                  <span style={{ color: 'var(--fg-3)', fontWeight: 400 }}>
                    {' '}
                    · {(d.share_pct * 100).toFixed(1)}%
                  </span>
                )}
              </span>
            </div>
            <div
              style={{
                height: 8,
                borderRadius: 4,
                background: 'var(--bg-3)',
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${pct}%`,
                  background:
                    d.rank === 1 ? 'var(--accent)' : 'var(--blue)',
                  borderRadius: 4,
                  transition: 'width 0.3s',
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
