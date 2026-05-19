/**
 * PainelGargalo — barra de gargalo por fase (Q.52.D).
 *
 * Reconstrói o `GargaloBars` do protótipo NELO: cartão com cabeçalho,
 * grelha `nome | ScoreBar | load/cap | %`. Dados 100% do snapshot
 * factory-map — ZERO MOCKS. Empty state explícito quando não há fases.
 */

import type { ReactNode } from 'react';
import { Factory } from 'lucide-react';
import { ScoreBar } from '../../components/dark';
import type { PhaseLoad } from './painelHelpers';

export interface PainelGargaloProps {
  phases: PhaseLoad[];
}

export function PainelGargalo({ phases }: PainelGargaloProps): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding: 18,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 14,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Factory size={14} color="var(--fg-2)" />
          <div>
            <div
              style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}
            >
              Score de gargalo por fase
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              Vermelho &gt; 80 — risco de paragem
            </div>
          </div>
        </div>
        <span
          style={{
            fontSize: 10.5,
            color: 'var(--fg-3)',
            background: 'var(--bg-2)',
            border: '1px solid var(--bd-1)',
            borderRadius: 999,
            padding: '2px 8px',
          }}
        >
          {phases.length} {phases.length === 1 ? 'fase' : 'fases'}
        </span>
      </div>

      {phases.length === 0 ? (
        <div
          style={{
            fontSize: 12,
            color: 'var(--fg-3)',
            padding: '18px 0',
            textAlign: 'center',
          }}
        >
          Sem fases em carga. O snapshot da fábrica ainda não detectou
          gargalos — confirma se o agendamento correu hoje.
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '140px 1fr 56px 56px',
            columnGap: 12,
            rowGap: 9,
            alignItems: 'center',
            fontSize: 11.5,
          }}
        >
          {phases.map((p) => (
            <PhaseRow key={p.id} phase={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function PhaseRow({ phase }: { phase: PhaseLoad }): ReactNode {
  const pct =
    phase.load !== null && phase.cap !== null && phase.cap > 0
      ? Math.round((phase.load / phase.cap) * 100)
      : null;
  return (
    <>
      <span
        style={{
          color: 'var(--fg-1)',
          fontWeight: 500,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={phase.short}
      >
        {phase.short}
      </span>
      <ScoreBar score={phase.score} />
      <span
        className="tabular"
        style={{ color: 'var(--fg-3)', fontSize: 11 }}
      >
        {phase.load !== null && phase.cap !== null
          ? `${phase.load}/${phase.cap}`
          : '—'}
      </span>
      <span
        className="tabular"
        style={{
          color: 'var(--fg-2)',
          fontSize: 10.5,
          textAlign: 'right',
        }}
      >
        {pct !== null ? `${pct}%` : '—'}
      </span>
    </>
  );
}
