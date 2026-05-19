/**
 * NeloWorkerAvatar — avatar de operador com iniciais (NELO.html atoms.jsx).
 *
 * Port fiel do atom `WorkerAvatar`: círculo com iniciais, nome opcional
 * e score ★ + tier opcionais. Sem foto real (privacidade da fábrica).
 * Distinto do `WorkerAvatar` legacy (Tailwind) — este bate certo com a
 * geometria do protótipo NELO.
 *
 * As iniciais derivam do nome se não forem passadas. Dados por props.
 *
 * Sprint Q.52.B.
 */

import type { ReactNode } from 'react';

export interface NeloWorker {
  /** Nome completo do operador. */
  name: string;
  /** Iniciais — derivadas do nome se omitidas. */
  initials?: string;
  /** Score 0-10. */
  score?: number;
  /** Tier de senioridade (ex: ">12m"). */
  tier?: string;
}

export interface NeloWorkerAvatarProps {
  worker: NeloWorker;
  /** Diâmetro do círculo em px. */
  size?: number;
  /** Mostrar score ★ + tier. */
  showScore?: boolean;
  /** Mostrar nome ao lado. */
  showName?: boolean;
}

function deriveInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0 || parts[0] === '') return '—';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function NeloWorkerAvatar({
  worker,
  size = 28,
  showScore = false,
  showName = false,
}: NeloWorkerAvatarProps): ReactNode {
  const initials = worker.initials ?? deriveInitials(worker.name);
  return (
    <div
      style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
    >
      <div
        title={worker.name}
        style={{
          width: size,
          height: size,
          borderRadius: '50%',
          background: 'var(--bg-3)',
          border: '1px solid var(--bd-2)',
          display: 'grid',
          placeItems: 'center',
          fontSize: size * 0.36,
          fontWeight: 500,
          color: 'var(--fg-1)',
          flexShrink: 0,
        }}
      >
        {initials}
      </div>
      {showName ? (
        <div style={{ overflow: 'hidden' }}>
          <div
            style={{
              fontSize: 12,
              color: 'var(--fg-0)',
              fontWeight: 500,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {worker.name}
          </div>
          {showScore && worker.score !== undefined ? (
            <div style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
              ★ {worker.score.toFixed(1)}
              {worker.tier ? ` · ${worker.tier}` : ''}
            </div>
          ) : null}
        </div>
      ) : null}
      {showScore && !showName && worker.score !== undefined ? (
        <span style={{ fontSize: 11, color: 'var(--fg-2)' }}>
          ★{' '}
          <span className="tabular" style={{ color: 'var(--fg-0)' }}>
            {worker.score.toFixed(1)}
          </span>
        </span>
      ) : null}
    </div>
  );
}
