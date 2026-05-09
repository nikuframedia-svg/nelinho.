/**
 * ZipAtoms — atoms portados literalmente de design/nelo-zip/src/atoms.jsx.
 *
 * StatusBadge / SevBadge / ToneBadge — todos partilham o vocabulário de
 * cores definido em index.css: green/yellow/red/blue/orange/purple/gray
 * com variantes -bg / -bd. Glyph + label PT-PT inline.
 *
 * Legend — pequeno painel "Como ler:" com 4 swatches coloridos.
 *
 * Sprint Q.18.ZIP.atoms.
 */

import type { ReactNode } from 'react';

export type ToneColor =
  | 'green'
  | 'yellow'
  | 'red'
  | 'blue'
  | 'orange'
  | 'purple'
  | 'gray';

export type BoatStatus =
  | 'on_time'
  | 'at_risk'
  | 'late'
  | 'curing'
  | 'completed';

export type Severity = 'critical' | 'high' | 'medium' | 'low';

// ─── STATUS / SEV maps (matching atoms.jsx) ─────────────────────────────────

export const STATUS_MAP: Record<
  BoatStatus,
  { color: ToneColor; label: string; glyph: string }
> = {
  on_time:   { color: 'green',  label: 'No prazo',   glyph: '●' },
  at_risk:   { color: 'yellow', label: 'Em risco',   glyph: '◆' },
  late:      { color: 'red',    label: 'Atrasado',   glyph: '▲' },
  curing:    { color: 'gray',   label: 'Em cura',    glyph: '◐' },
  completed: { color: 'blue',   label: 'Concluído',  glyph: '■' },
};

export const SEV_MAP: Record<
  Severity,
  { color: ToneColor; label: string; glyph: string }
> = {
  critical: { color: 'red',    label: 'Crítico', glyph: '▲' },
  high:     { color: 'orange', label: 'Alto',    glyph: '▲' },
  medium:   { color: 'yellow', label: 'Médio',   glyph: '◆' },
  low:      { color: 'blue',   label: 'Baixo',   glyph: '●' },
};

// ─── ToneBadge — base (matching atoms.jsx Badge) ────────────────────────────

interface ToneBadgeProps {
  tone?: ToneColor;
  glyph?: string;
  size?: 'sm' | 'md';
  children: ReactNode;
}

export function ToneBadge({
  tone = 'gray',
  glyph,
  size = 'md',
  children,
}: ToneBadgeProps) {
  const sz =
    size === 'sm'
      ? { padding: '1px 7px', fontSize: 11, height: 20 }
      : { padding: '3px 10px', fontSize: 12, height: 24 };
  const isAccent = tone !== 'gray';
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        ...sz,
        borderRadius: 999,
        fontWeight: 500,
        letterSpacing: 0.1,
        color: isAccent ? `var(--${tone})` : 'var(--fg-1)',
        background: isAccent ? `var(--${tone}-bg)` : 'var(--bd-1)',
        border: `1px solid ${isAccent ? `var(--${tone}-bd)` : 'var(--bd-2)'}`,
        whiteSpace: 'nowrap',
      }}
    >
      {glyph ? (
        <span style={{ fontSize: 9, lineHeight: 1 }}>{glyph}</span>
      ) : null}
      {children}
    </span>
  );
}

// ─── StatusBadge — boat status ──────────────────────────────────────────────

export function StatusBadge({
  status,
  size = 'md',
}: {
  status: BoatStatus;
  size?: 'sm' | 'md';
}) {
  const s = STATUS_MAP[status] ?? STATUS_MAP.on_time;
  return (
    <ToneBadge tone={s.color} glyph={s.glyph} size={size}>
      {s.label}
    </ToneBadge>
  );
}

// ─── SevBadge — alert / suggestion severity ─────────────────────────────────

export function SevBadge({
  severity,
  size = 'md',
}: {
  severity: Severity;
  size?: 'sm' | 'md';
}) {
  const s = SEV_MAP[severity] ?? SEV_MAP.low;
  return (
    <ToneBadge tone={s.color} glyph={s.glyph} size={size}>
      {s.label}
    </ToneBadge>
  );
}

// ─── Legend — color guide (atoms.jsx pattern) ───────────────────────────────

export interface LegendItem {
  color: ToneColor;
  label: string;
}

export function Legend({
  hint = 'Como ler:',
  trailing,
  items,
}: {
  hint?: string;
  trailing?: string;
  items: LegendItem[];
}) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 18,
        padding: '10px 14px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 8,
        fontSize: 11,
        color: 'var(--fg-2)',
        flexWrap: 'wrap',
        alignItems: 'center',
      }}
    >
      <span style={{ fontWeight: 500, color: 'var(--fg-1)' }}>
        {hint}
      </span>
      {trailing ? <span>{trailing}</span> : null}
      <span
        style={{
          display: 'flex',
          gap: 14,
          marginLeft: 'auto',
          flexWrap: 'wrap',
        }}
      >
        {items.map(({ color, label }) => (
          <span
            key={color + label}
            style={{ display: 'flex', alignItems: 'center', gap: 5 }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 2,
                background: `var(--${color})`,
                display: 'inline-block',
              }}
            />
            {label}
          </span>
        ))}
      </span>
    </div>
  );
}

// ─── BoatCardZip — boat tile with hull/client/phase/status (atoms.jsx) ──────

export interface ZipBoat {
  id: number;             // legacy_id
  short: string;          // K1 / K2 / K4
  model: string;          // full model name
  client_code?: string;   // FR / DE / PT / etc
  client_flag?: string;   // 🇫🇷 emoji
  phase_short?: string;   // "Lam." / "Pintura"
  phase_long?: string;    // "Laminagem" / "Pintura Acabamento"
  status: BoatStatus;
  workers?: string[];     // initials e.g. ["PG", "MS"]
  risk?: number;          // 0..1
  dx?: number;            // days to ship
  transport?: string;     // ISO date
  mold?: string | null;
}

export function BoatCardZip({
  boat,
  compact = false,
  onClick,
}: {
  boat: ZipBoat;
  compact?: boolean;
  onClick?: () => void;
}) {
  const s = STATUS_MAP[boat.status] ?? STATUS_MAP.on_time;
  const tooltip = [
    `${boat.model} #${boat.id}`,
    boat.client_code,
    boat.mold ? `Molde: ${boat.mold}` : null,
    boat.transport ? `Expedição: ${boat.transport}` : null,
    boat.risk !== undefined
      ? `Risco qualidade: ${(boat.risk * 100).toFixed(0)}%`
      : null,
  ]
    .filter(Boolean)
    .join('\n');

  const padding = compact ? '6px 8px' : '10px 12px';
  const minW = compact ? 110 : 140;

  return (
    <div
      onClick={onClick}
      title={tooltip}
      style={{
        background: 'var(--bg-2)',
        border: `1px solid var(--${s.color}-bd)`,
        borderLeft: `3px solid var(--${s.color})`,
        borderRadius: 6,
        padding,
        minWidth: minW,
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        cursor: onClick ? 'pointer' : 'default',
        transition: 'background 0.12s, border-color 0.12s',
      }}
    >
      {/* Linha 1: short + client flag + status dot */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 6,
        }}
      >
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: 'var(--fg-0)',
          }}
        >
          {boat.short}{' '}
          <span style={{ fontWeight: 400, opacity: 0.7 }}>#{boat.id}</span>
        </span>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 4,
            fontSize: 11,
          }}
        >
          {boat.client_flag ? <span>{boat.client_flag}</span> : null}
          <span
            aria-label={s.label}
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: `var(--${s.color})`,
              boxShadow: `0 0 6px var(--${s.color}-bd)`,
            }}
          />
        </span>
      </div>

      {/* Linha 2: phase + workers */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 6,
          fontSize: 10,
          color: 'var(--fg-2)',
        }}
      >
        <span
          style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            minWidth: 0,
          }}
        >
          {boat.phase_short ?? boat.phase_long ?? '—'}
        </span>
        {boat.workers && boat.workers.length > 0 ? (
          <span style={{ fontFamily: 'monospace' }}>
            {boat.workers.length === 1
              ? boat.workers[0]
              : `${boat.workers[0]}+${boat.workers.length - 1}`}
          </span>
        ) : null}
      </div>

      {/* Linha 3 (opt): transport / risk warning */}
      {!compact && boat.dx !== undefined ? (
        <div
          style={{
            fontSize: 10,
            color:
              boat.dx <= 0
                ? 'var(--red)'
                : boat.dx <= 2
                  ? 'var(--yellow)'
                  : 'var(--fg-3)',
            fontWeight: 500,
          }}
        >
          {boat.dx <= 0 ? 'Hoje' : `D−${boat.dx}`}
        </div>
      ) : null}

      {!compact && boat.risk !== undefined && boat.risk > 0.15 ? (
        <div
          style={{
            fontSize: 10,
            color: 'var(--yellow)',
            fontWeight: 500,
          }}
        >
          ⚠ risco {Math.round(boat.risk * 100)}%
        </div>
      ) : null}
    </div>
  );
}
