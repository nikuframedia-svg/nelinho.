/**
 * LevelScale — apresentação da escala de níveis dos operadores.
 *
 * Q.53.L. A escala mudou (Q.53.E): **3.0 = melhor, 1.0 = pior**, com
 * meios-níveis 1.0/1.5/2.0/2.5/3.0, atribuída por **grupo de área**
 * (~7 grupos: Laminagem, Pintura, Acabamento, Montagem, Cura/Moldes,
 * Estrutura, Transversal).
 *
 * Componentes reutilizados pela página /equipa e pelo WorkerProfile:
 *   • `levelTone`   — cor semântica de um nível (verde alto → vermelho baixo).
 *   • `LevelGauge`  — barra horizontal 1→3 com o ponto do nível marcado.
 *   • `LevelBadge`  — pílula compacta com o valor do nível.
 */

import type { ReactNode } from 'react';

export const LEVEL_MIN = 1.0;
export const LEVEL_MAX = 3.0;

/**
 * Cor semântica de um nível na escala invertida (3 = melhor).
 * Devolve um nome de variável CSS de tom (`green` / `yellow` / `red` …).
 */
export function levelTone(level: number): string {
  if (level >= 2.75) return 'green';
  if (level >= 2.25) return 'teal';
  if (level >= 1.75) return 'yellow';
  if (level >= 1.25) return 'orange';
  return 'red';
}

/** Texto curto do nível, ex: "2.5". */
export function formatLevel(level: number): string {
  return level.toFixed(1);
}

// ─── Gauge horizontal 1→3 ────────────────────────────────────────────────────

export function LevelGauge({
  level,
  label,
  height = 8,
}: {
  level: number;
  /** Rótulo opcional à esquerda da barra. */
  label?: string;
  height?: number;
}): ReactNode {
  const clamped = Math.max(LEVEL_MIN, Math.min(LEVEL_MAX, level));
  const pct = ((clamped - LEVEL_MIN) / (LEVEL_MAX - LEVEL_MIN)) * 100;
  const tone = levelTone(clamped);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      {label !== undefined ? (
        <span
          style={{
            fontSize: 11,
            color: 'var(--fg-2)',
            minWidth: 96,
            flexShrink: 0,
          }}
        >
          {label}
        </span>
      ) : null}
      <div
        style={{
          flex: 1,
          position: 'relative',
          height,
          background: 'var(--bg-3)',
          borderRadius: 999,
          border: '1px solid var(--bd-1)',
        }}
      >
        {/* Marcas dos meios-níveis */}
        {[1.5, 2.0, 2.5].map((step) => (
          <span
            key={step}
            style={{
              position: 'absolute',
              left: `${((step - LEVEL_MIN) / (LEVEL_MAX - LEVEL_MIN)) * 100}%`,
              top: 0,
              bottom: 0,
              width: 1,
              background: 'var(--bd-2)',
            }}
          />
        ))}
        <span
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${pct}%`,
            background: `var(--${tone})`,
            borderRadius: 999,
            transition: 'width 0.2s',
          }}
        />
      </div>
      <span
        className="tabular"
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: `var(--${tone})`,
          minWidth: 30,
          textAlign: 'right',
        }}
      >
        {formatLevel(clamped)}
      </span>
    </div>
  );
}

// ─── Badge compacto ──────────────────────────────────────────────────────────

export function LevelBadge({ level }: { level: number }): ReactNode {
  const tone = levelTone(level);
  return (
    <span
      className="tabular"
      style={{
        fontSize: 10.5,
        padding: '2px 7px',
        background: `var(--${tone}-bg)`,
        border: `1px solid var(--${tone}-bd)`,
        borderRadius: 4,
        color: `var(--${tone})`,
        fontWeight: 600,
      }}
    >
      ⬢ {formatLevel(level)}
    </span>
  );
}

/** Legenda da escala — mostra que 3 é o melhor. */
export function LevelScaleLegend(): ReactNode {
  return (
    <div
      style={{
        display: 'flex',
        gap: 12,
        fontSize: 10,
        color: 'var(--fg-3)',
        flexWrap: 'wrap',
      }}
    >
      <span>Escala 1.0 → 3.0 · 3.0 = melhor · meios-níveis de 0.5</span>
    </div>
  );
}
