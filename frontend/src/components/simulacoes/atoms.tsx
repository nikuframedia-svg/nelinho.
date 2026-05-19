/**
 * Átomos locais da página Simulações — port fiel do design NELO.html
 * (page-simulacoes.jsx). `Tag` / `SectionHeader` / `SimCard` são usados
 * só aqui, por isso vivem em `components/simulacoes/` e não em dark/.
 *
 * Sprint Q.52.M.
 */

import type { CSSProperties, ReactNode } from 'react';

/** Tons permitidos do design (mapeiam a CSS vars `--<tone>`). */
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

/** Formata um valor em € com agrupamento PT-PT. */
export function fmtEuro(n: number): string {
  return `€${Math.abs(Math.round(n)).toLocaleString('pt-PT')}`;
}

/** Pílula pequena de baixo croma. */
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
      ? { padding: '1px 7px', fontSize: 10.5, height: 18, gap: 4 }
      : { padding: '2px 9px', fontSize: 11.5, height: 22, gap: 5 };
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

/** Cabeçalho de secção dentro de um cartão. */
export function SectionHeader({
  icon,
  title,
  subtitle,
  action,
}: {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
  action?: ReactNode;
}): ReactNode {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
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
            <div
              style={{ fontSize: 11.5, color: 'var(--fg-2)', marginTop: 2 }}
            >
              {subtitle}
            </div>
          ) : null}
        </div>
      </div>
      {action}
    </div>
  );
}

/** Cartão de superfície `--bg-1`. */
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
