/**
 * TruckGrid — visualização do camião 5×10 (50 slots).
 *
 * Port fiel do `TruckGrid` do protótipo NELO (page-expedicao.jsx). CSS grid
 * 10 colunas × 5 linhas, células pequenas, cor por estado:
 *   verde   → barco pronto
 *   amarelo → barco em risco
 *   cinza   → barco em produção
 *   vazio   → slot livre dentro da capacidade
 *
 * Dados sempre por props (ZERO MOCKS). Os counts vêm do batch real:
 * `assigned_orders_count` para ocupação, `truck_capacity_units` (cap > 50
 * desenha só 50 slots, o resto fica fora da grelha).
 *
 * Sprint Q.52.J.
 */

import type { ReactNode } from 'react';

export interface TruckGridProps {
  /** Barcos prontos para expedir. */
  ready: number;
  /** Barcos ainda em produção (inclui os em risco). */
  inProd: number;
  /** Subconjunto de inProd que está em risco. */
  atRisk: number;
  /** Capacidade total do camião (default 50). */
  total?: number;
  /** Tamanho das células. */
  size?: 'sm' | 'md';
}

const COLS = 10;
const ROWS = 5;

export function TruckGrid({
  ready,
  inProd,
  atRisk,
  total = 50,
  size = 'md',
}: TruckGridProps): ReactNode {
  const slot = size === 'sm' ? 6 : 10;
  const gap = size === 'sm' ? 1.5 : 2.5;
  const cap = Math.min(total, COLS * ROWS);

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${COLS}, ${slot}px)`,
        gap,
        padding: size === 'sm' ? 3 : 5,
        background: 'var(--bg-0)',
        border: '1px solid var(--bd-1)',
        borderRadius: 5,
        width: 'fit-content',
      }}
      aria-label={`Camião: ${ready} prontos, ${inProd} em produção, ${total} de capacidade`}
    >
      {Array.from({ length: COLS * ROWS }).map((_, i) => {
        let bg: string;
        let brd: string;
        if (i < ready) {
          bg = 'var(--green)';
          brd = 'var(--green-bd)';
        } else if (i < ready + atRisk) {
          bg = 'var(--yellow)';
          brd = 'var(--yellow-bd)';
        } else if (i < ready + inProd) {
          bg = 'var(--bg-3)';
          brd = 'var(--bd-2)';
        } else if (i < cap) {
          bg = 'transparent';
          brd = 'var(--bd-1)';
        } else {
          bg = 'transparent';
          brd = 'transparent';
        }
        return (
          <div
            key={i}
            style={{
              width: slot,
              height: slot,
              background: bg,
              border: `1px solid ${brd}`,
              borderRadius: 1.5,
            }}
          />
        );
      })}
    </div>
  );
}
