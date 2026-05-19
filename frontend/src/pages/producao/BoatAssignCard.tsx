/**
 * BoatAssignCard — cartão de barco arrastável + alvo de largada para
 * operadores (Q.52.F · Q.53.I).
 *
 * Port fiel do `BoatAssignCard` do design NELO: barra de estado lateral,
 * número do barco, modelo + nome do cliente, RiskBadge, e slots de
 * operadores atribuídos. É draggable (payload `boat`) e drop-target
 * (payload `worker`) — DnD bidirecional via o hook `useDragDrop`.
 *
 * Q.53.I — o cartão deixa de mostrar só códigos: passa a destacar o
 * nome do modelo (`product_name`) e o nome do cliente (`customer_name`)
 * quando disponível. ZERO MOCKS — se o cliente não está sincronizado o
 * cartão omite-o em silêncio, nunca inventa um nome.
 *
 * Dados 100% por props.
 */

import { useState } from 'react';
import type { DragEvent, ReactNode } from 'react';
import type { ActiveOrderCard } from './fabricaApi';

export interface AssignedWorker {
  id: string;
  name: string;
  initials: string;
}

export interface BoatAssignCardProps {
  boat: ActiveOrderCard;
  assignedWorkers: AssignedWorker[];
  /** Cartão actualmente seleccionado (rail religa-se a este barco). */
  isActive: boolean;
  /** A ser arrastado neste momento. */
  isDragging: boolean;
  onClick: () => void;
  /** Arrasto do barco (origem) — payload `boat`. */
  onBoatDragStart: (e: DragEvent<HTMLDivElement>) => void;
  onBoatDragEnd: (e: DragEvent<HTMLDivElement>) => void;
  /** Largar um operador (id) neste barco. */
  onWorkerDrop: (workerId: string) => void;
  /** Remover um operador deste barco. */
  onWorkerRemove: (workerId: string) => void;
  /** Risco preditivo 0..1 — opcional. */
  risk?: number;
}

const STATUS_COLOR: Record<string, string> = {
  IN_PROGRESS: 'var(--blue)',
  COMPLETED: 'var(--green)',
  LATE: 'var(--red)',
  AT_RISK: 'var(--yellow)',
};

const MIME = 'application/x-nelo-dnd';

export function BoatAssignCard({
  boat,
  assignedWorkers,
  isActive,
  isDragging,
  onClick,
  onBoatDragStart,
  onBoatDragEnd,
  onWorkerDrop,
  onWorkerRemove,
  risk,
}: BoatAssignCardProps): ReactNode {
  const [overWorker, setOverWorker] = useState(false);
  const statusColor = STATUS_COLOR[boat.status] ?? 'var(--blue)';

  function isWorkerDrag(e: DragEvent<HTMLDivElement>): boolean {
    // O payload só é legível no `drop`; no `dragOver` confiamos no MIME.
    return e.dataTransfer.types.includes(MIME);
  }

  return (
    <div
      onClick={onClick}
      draggable
      onDragStart={onBoatDragStart}
      onDragEnd={onBoatDragEnd}
      onDragOver={(e) => {
        if (isWorkerDrag(e)) {
          e.preventDefault();
          e.stopPropagation();
          setOverWorker(true);
        }
      }}
      onDragLeave={() => setOverWorker(false)}
      onDrop={(e) => {
        const raw = e.dataTransfer.getData(MIME);
        if (!raw) return;
        try {
          const parsed = JSON.parse(raw) as {
            kind: string;
            data: { id: string };
          };
          if (parsed.kind === 'worker') {
            e.preventDefault();
            e.stopPropagation();
            setOverWorker(false);
            onWorkerDrop(parsed.data.id);
          }
        } catch {
          /* payload inválido — ignora */
        }
      }}
      role="button"
      tabIndex={0}
      style={{
        background: isActive
          ? 'var(--bg-3)'
          : isDragging
          ? 'var(--bg-4)'
          : 'var(--bg-2)',
        border: `1px solid ${
          isActive
            ? 'var(--accent-bd)'
            : overWorker
            ? 'var(--green-bd)'
            : 'var(--bd-2)'
        }`,
        boxShadow: overWorker
          ? '0 0 0 2px var(--green-bd) inset'
          : isActive
          ? '0 0 0 1px var(--accent-bd)'
          : isDragging
          ? 'var(--shadow-2)'
          : 'none',
        borderRadius: 'var(--r-md)',
        padding: '8px 10px',
        cursor: 'grab',
        transition: 'background 0.15s, border-color 0.15s, transform 0.18s',
        fontSize: 12,
        position: 'relative',
        transform: isDragging ? 'scale(1.04) rotate(-1deg)' : 'scale(1)',
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
          background: statusColor,
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
          <span style={{ fontWeight: 500, color: 'var(--fg-0)', fontSize: 12 }}>
            <span style={{ color: 'var(--fg-3)' }}>#</span>
            {boat.hull ?? boat.id.slice(0, 6)}
          </span>
          {boat.product_type && (
            <span
              style={{ fontSize: 10, color: 'var(--fg-3)', fontWeight: 500 }}
            >
              {boat.product_type}
            </span>
          )}
        </div>
        {/* Modelo do barco (product_name é o nome do modelo). */}
        <div
          style={{
            marginTop: 3,
            fontSize: 10.5,
            color: 'var(--fg-2)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
          title={boat.product_name ?? ''}
        >
          {boat.product_name ?? 'Modelo —'}
        </div>
        {/* Nome do cliente — só quando a sincronização ERP o trouxe. */}
        {boat.customer_name && (
          <div
            style={{
              marginTop: 2,
              fontSize: 9.5,
              color: 'var(--fg-3)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={boat.customer_name}
          >
            {boat.customer_name}
          </div>
        )}

        {risk !== undefined && risk > 0 && (
          <div style={{ marginTop: 4, fontSize: 9.5 }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 3,
                padding: '1px 6px',
                borderRadius: 999,
                background: 'var(--orange-bg)',
                border: '1px solid var(--orange-bd)',
                color: 'var(--orange)',
                fontWeight: 600,
              }}
            >
              risco {Math.round(risk * 100)}%
            </span>
          </div>
        )}

        {/* Slots de operadores */}
        <div
          style={{
            marginTop: 6,
            display: 'flex',
            alignItems: 'center',
            gap: 4,
            minHeight: 22,
            flexWrap: 'wrap',
          }}
        >
          {assignedWorkers.length > 0 ? (
            assignedWorkers.map((w) => (
              <button
                key={w.id}
                type="button"
                title={`${w.name} — clica para remover`}
                onClick={(e) => {
                  e.stopPropagation();
                  onWorkerRemove(w.id);
                }}
                style={{
                  width: 20,
                  height: 20,
                  borderRadius: '50%',
                  background:
                    'linear-gradient(135deg, var(--bg-3), var(--bg-4))',
                  border: '1px solid var(--bd-2)',
                  fontSize: 8.5,
                  fontWeight: 600,
                  color: 'var(--fg-0)',
                  display: 'grid',
                  placeItems: 'center',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                {w.initials}
              </button>
            ))
          ) : (
            <span
              style={{
                fontSize: 9.5,
                color: 'var(--fg-4)',
                fontStyle: 'italic',
              }}
            >
              sem operador
            </span>
          )}
          {overWorker && (
            <span
              style={{
                fontSize: 9.5,
                color: 'var(--green)',
                fontWeight: 600,
                marginLeft: 'auto',
              }}
            >
              ← largar
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
