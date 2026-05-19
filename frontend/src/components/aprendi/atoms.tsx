/**
 * Átomos locais da página "O que aprendi" — port do design NELO.html
 * (page-aprendi.jsx). `Card` / `SectionHeader` / `Tag` / `MiniBar`
 * usados só nesta página.
 *
 * Sprint Q.52.O.
 */

import type { CSSProperties, ReactNode } from 'react';

export type Tone =
  | 'green'
  | 'yellow'
  | 'red'
  | 'blue'
  | 'orange'
  | 'purple'
  | 'teal'
  | 'gray';

const TOKEN_TONES = new Set<Tone>([
  'green',
  'yellow',
  'red',
  'blue',
  'orange',
  'purple',
  'teal',
]);

export const toneVar = (t: Tone): string => `var(--${t})`;
export const toneBg = (t: Tone): string =>
  TOKEN_TONES.has(t) ? `var(--${t}-bg)` : 'var(--bg-3)';
export const toneBd = (t: Tone): string =>
  TOKEN_TONES.has(t) ? `var(--${t}-bd)` : 'var(--bd-1)';

export function Card({
  children,
  padding = 18,
  style,
}: {
  children: ReactNode;
  padding?: number;
  style?: CSSProperties;
}): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

export function SectionHeader({
  icon,
  title,
  subtitle,
}: {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
}): ReactNode {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 9,
        marginBottom: 12,
      }}
    >
      {icon ? <span style={{ color: 'var(--fg-2)' }}>{icon}</span> : null}
      <div>
        <h2
          style={{
            margin: 0,
            fontSize: 14,
            fontWeight: 600,
            color: 'var(--fg-0)',
            letterSpacing: '-0.1px',
          }}
        >
          {title}
        </h2>
        {subtitle ? (
          <div style={{ fontSize: 11.5, color: 'var(--fg-2)', marginTop: 2 }}>
            {subtitle}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function Tag({
  tone = 'gray',
  size = 'md',
  children,
}: {
  tone?: Tone;
  size?: 'sm' | 'md';
  children: ReactNode;
}): ReactNode {
  const sz =
    size === 'sm'
      ? { padding: '1px 7px', fontSize: 10.5, height: 18 }
      : { padding: '2px 9px', fontSize: 11.5, height: 22 };
  const isToken = TOKEN_TONES.has(tone);
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        ...sz,
        borderRadius: 999,
        fontWeight: 500,
        color: isToken ? toneVar(tone) : 'var(--fg-1)',
        background: isToken ? toneBg(tone) : 'var(--bg-3)',
        border: `1px solid ${isToken ? toneBd(tone) : 'var(--bd-1)'}`,
        whiteSpace: 'nowrap',
      }}
    >
      {children}
    </span>
  );
}

/** Barra horizontal fina (0-100). */
export function MiniBar({
  value,
  color = 'var(--accent)',
  height = 4,
}: {
  value: number;
  color?: string;
  height?: number;
}): ReactNode {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div
      style={{
        height,
        background: 'var(--bg-3)',
        borderRadius: 999,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          height: '100%',
          width: `${pct}%`,
          background: color,
          borderRadius: 999,
        }}
      />
    </div>
  );
}

/** Estado uniforme de "tab vazia / a carregar / erro". */
export function TabState({
  loading,
  error,
  empty,
  emptyText,
  children,
}: {
  loading: boolean;
  error?: unknown;
  empty: boolean;
  emptyText: string;
  children: ReactNode;
}): ReactNode {
  if (loading) {
    return (
      <Card padding={32} style={{ textAlign: 'center' }}>
        <span style={{ fontSize: 13, color: 'var(--fg-2)' }}>A carregar…</span>
      </Card>
    );
  }
  if (error) {
    return (
      <Card padding={32} style={{ textAlign: 'center' }}>
        <span style={{ fontSize: 13, color: 'var(--red)' }}>
          {error instanceof Error ? error.message : 'Erro a carregar dados'}
        </span>
      </Card>
    );
  }
  if (empty) {
    return (
      <Card padding={32} style={{ textAlign: 'center' }}>
        <span style={{ fontSize: 13, color: 'var(--fg-2)' }}>{emptyText}</span>
      </Card>
    );
  }
  return <>{children}</>;
}
