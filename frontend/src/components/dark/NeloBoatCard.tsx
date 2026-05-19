/**
 * NeloBoatCard — cartão de barco arrastável (NELO.html atoms.jsx).
 *
 * Port fiel do atom `BoatCard`: barra de estado lateral, número do
 * barco, código do cliente, modelo + ETA, modo compacto e estado de
 * arrasto (escala + rotação + sombra). Distinto do `BoatCard` legacy
 * (Tailwind) — este bate certo com a geometria do protótipo NELO.
 *
 * Genérico em DnD: o caller controla `draggable`, `onDragStart` etc.
 * Dados sempre por props (ZERO MOCKS).
 *
 * Sprint Q.52.B.
 */

import type { DragEvent, ReactNode } from 'react';

export type NeloBoatStatus =
  | 'on_time'
  | 'at_risk'
  | 'late'
  | 'curing'
  | 'completed';

export interface NeloBoat {
  /** Identificador do barco (legacy_id / OF). */
  id: number | string;
  /** Código curto do cliente (ex: "FR", "DE"). */
  clientCode: string;
  /** Nome do modelo (ex: "K1 Vanquish 3"). */
  model: string;
  status: NeloBoatStatus;
  /** ETA curto (ex: "D−3", "Sex"). */
  eta?: string;
}

export interface NeloBoatCardProps {
  boat: NeloBoat;
  /** Modo compacto — esconde a linha modelo/ETA. */
  compact?: boolean;
  /** Estado visual de arrasto (escala + sombra). */
  dragging?: boolean;
  /** Permitir arrasto HTML5. */
  draggable?: boolean;
  onClick?: () => void;
  onDragStart?: (e: DragEvent<HTMLDivElement>) => void;
  onDragEnd?: (e: DragEvent<HTMLDivElement>) => void;
}

const STATUS_COLOR: Record<NeloBoatStatus, string> = {
  on_time: 'green',
  at_risk: 'yellow',
  late: 'red',
  curing: 'gray',
  completed: 'blue',
};

export function NeloBoatCard({
  boat,
  compact = false,
  dragging = false,
  draggable = false,
  onClick,
  onDragStart,
  onDragEnd,
}: NeloBoatCardProps): ReactNode {
  const color = STATUS_COLOR[boat.status];
  return (
    <div
      onClick={onClick}
      draggable={draggable}
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      style={{
        background: dragging ? 'var(--bg-4)' : 'var(--bg-2)',
        border: '1px solid var(--bd-2)',
        borderRadius: 'var(--r-md)',
        padding: compact ? '6px 8px' : '8px 10px',
        cursor: onClick ? 'pointer' : draggable ? 'grab' : 'default',
        transition: 'background 0.12s, transform 0.15s, box-shadow 0.15s',
        fontSize: 12,
        position: 'relative',
        transform: dragging ? 'scale(1.04) rotate(-1deg)' : 'scale(1)',
        boxShadow: dragging ? 'var(--shadow-2)' : 'none',
      }}
      onMouseEnter={(e) => {
        if (!dragging) e.currentTarget.style.background = 'var(--bg-3)';
      }}
      onMouseLeave={(e) => {
        if (!dragging) e.currentTarget.style.background = 'var(--bg-2)';
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: 0,
          top: 8,
          bottom: 8,
          width: 2,
          borderRadius: 2,
          background: `var(--${color})`,
        }}
      />
      <div style={{ paddingLeft: 6 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            gap: 6,
          }}
        >
          <span
            style={{ fontWeight: 500, color: 'var(--fg-0)', fontSize: 12 }}
          >
            <span style={{ color: 'var(--fg-2)' }}>#</span>
            {boat.id}
          </span>
          <span
            style={{ fontSize: 10, color: 'var(--fg-3)', fontWeight: 500 }}
          >
            {boat.clientCode}
          </span>
        </div>
        {!compact ? (
          <div
            style={{
              marginTop: 3,
              fontSize: 10.5,
              color: 'var(--fg-2)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 6,
            }}
          >
            <span
              style={{
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                maxWidth: 92,
              }}
            >
              {boat.model}
            </span>
            {boat.eta ? (
              <span className="tabular" style={{ color: 'var(--fg-3)' }}>
                {boat.eta}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
