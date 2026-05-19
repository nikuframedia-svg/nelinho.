/**
 * FabricaPhaseColumn — coluna Kanban de uma fase (Q.52.F).
 *
 * Port fiel do `PhaseColumn` do design NELO: cabeçalho com nome da fase,
 * contagem de barcos, ScoreBar de gargalo e carga. O corpo é alvo de
 * largada para barcos (payload `boat`) — arrastar um barco para cá pede
 * o preview da consequência.
 *
 * Dados 100% por props. ZERO MOCKS.
 */

import { useState } from 'react';
import type { DragEvent, ReactNode } from 'react';
import { ScoreBar } from '../../components/dark';
import { BoatAssignCard } from './BoatAssignCard';
import type { AssignedWorker } from './BoatAssignCard';
import type { ActiveOrderCard } from './fabricaApi';

const MIME = 'application/x-nelo-dnd';

export interface PhaseColumnModel {
  /** Identificador da fase (= current_phase_name). */
  id: string;
  /** Nome curto a mostrar. */
  short: string;
  /** Score de gargalo 0-100 (do snapshot). */
  score: number;
  load: number | null;
  cap: number | null;
}

export interface FabricaPhaseColumnProps {
  phase: PhaseColumnModel;
  boats: ActiveOrderCard[];
  /** Operadores atribuídos por order id. */
  assignments: Record<string, AssignedWorker[]>;
  activeBoatId: string | null;
  draggedBoatId: string | null;
  /** Riscos preditivos por order id (opcional). */
  riskByBoat?: Record<string, number>;
  onBoatClick: (boatId: string) => void;
  /** Largar um barco nesta fase. */
  onBoatDrop: (boatId: string, phaseId: string) => void;
  onWorkerDrop: (boatId: string, workerId: string) => void;
  onWorkerRemove: (boatId: string, workerId: string) => void;
  onBoatDragStart: (boatId: string) => void;
  onBoatDragEnd: () => void;
}

export function FabricaPhaseColumn({
  phase,
  boats,
  assignments,
  activeBoatId,
  draggedBoatId,
  riskByBoat,
  onBoatClick,
  onBoatDrop,
  onWorkerDrop,
  onWorkerRemove,
  onBoatDragStart,
  onBoatDragEnd,
}: FabricaPhaseColumnProps): ReactNode {
  const [overBoat, setOverBoat] = useState(false);
  const pct =
    phase.load !== null && phase.cap !== null && phase.cap > 0
      ? Math.round((phase.load / phase.cap) * 100)
      : null;

  return (
    <div
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes(MIME)) {
          e.preventDefault();
          setOverBoat(true);
        }
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
          setOverBoat(false);
        }
      }}
      onDrop={(e: DragEvent<HTMLDivElement>) => {
        const raw = e.dataTransfer.getData(MIME);
        setOverBoat(false);
        if (!raw) return;
        try {
          const parsed = JSON.parse(raw) as {
            kind: string;
            data: { id: string };
          };
          if (parsed.kind === 'boat') {
            e.preventDefault();
            onBoatDrop(parsed.data.id, phase.id);
          }
        } catch {
          /* payload inválido */
        }
      }}
      style={{
        background: overBoat ? 'var(--accent-bg)' : 'var(--bg-1)',
        border: `1px solid ${overBoat ? 'var(--accent-bd)' : 'var(--bd-1)'}`,
        borderRadius: 'var(--r-lg)',
        minWidth: 200,
        display: 'flex',
        flexDirection: 'column',
        transition: 'background 0.18s, border-color 0.18s',
      }}
    >
      <div
        style={{
          padding: '12px 12px 10px',
          borderBottom: '1px solid var(--bd-1)',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            marginBottom: 6,
          }}
        >
          <span
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: 'var(--fg-0)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
            title={phase.short}
          >
            {phase.short}
          </span>
          <span
            className="tabular"
            style={{ fontSize: 11, color: 'var(--fg-2)' }}
          >
            {boats.length}
          </span>
        </div>
        <ScoreBar score={phase.score} />
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: 5,
            fontSize: 10,
            color: 'var(--fg-3)',
          }}
        >
          <span>{pct !== null ? `Carga ${pct}%` : 'Carga —'}</span>
          <span>
            {phase.load !== null && phase.cap !== null
              ? `${phase.load}/${phase.cap} op.`
              : '—'}
          </span>
        </div>
      </div>
      <div
        style={{
          padding: 8,
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          flex: 1,
          minHeight: 80,
        }}
      >
        {boats.length === 0 ? (
          <div
            style={{
              fontSize: 10.5,
              color: 'var(--fg-4)',
              fontStyle: 'italic',
              padding: '8px 4px',
              textAlign: 'center',
            }}
          >
            sem barcos
          </div>
        ) : (
          boats.map((b) => (
            <BoatAssignCard
              key={b.id}
              boat={b}
              assignedWorkers={assignments[b.id] ?? []}
              isActive={activeBoatId === b.id}
              isDragging={draggedBoatId === b.id}
              risk={riskByBoat?.[b.id]}
              onClick={() => onBoatClick(b.id)}
              onBoatDragStart={(e) => {
                e.dataTransfer.setData(
                  MIME,
                  JSON.stringify({ kind: 'boat', data: { id: b.id } }),
                );
                e.dataTransfer.effectAllowed = 'move';
                onBoatDragStart(b.id);
              }}
              onBoatDragEnd={onBoatDragEnd}
              onWorkerDrop={(workerId) => onWorkerDrop(b.id, workerId)}
              onWorkerRemove={(workerId) => onWorkerRemove(b.id, workerId)}
            />
          ))
        )}
      </div>
    </div>
  );
}
