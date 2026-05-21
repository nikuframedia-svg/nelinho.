// Decomposto de OperadorTabletPage.tsx (Q.60.AB).
import type { ReactNode } from 'react';
import { Boxes, Hammer, MoreHorizontal } from 'lucide-react';

export const WORKER_ID_KEY = 'employee_id';

// ─── Tipo de problema → error_code do backend ─────────────────────────────

export const PROBLEM_KINDS: Array<{
  label: string;
  errorCode: string;
  icon: ReactNode;
}> = [
  { label: 'Erro material', errorCode: 'RESIN_BUBBLE', icon: <Boxes size={26} /> },
  { label: 'Erro molde', errorCode: 'DIMENSION_OFF', icon: <Hammer size={26} /> },
  { label: 'Falta peça', errorCode: 'COLAGEM_FAIL', icon: <Boxes size={26} /> },
  { label: 'Outro', errorCode: 'OTHER', icon: <MoreHorizontal size={26} /> },
];

export function fmtClock(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60)
    .toString()
    .padStart(2, '0');
  const s = (totalSeconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

export function fmtTimeOfDay(d: Date): string {
  return d.toLocaleTimeString('pt-PT', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ─── Cartão de contexto ────────────────────────────────────────────────────

export function ContextCard({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}): ReactNode {
  return (
    <div
      style={{
        padding: 18,
        background: accent ? 'var(--accent-bg)' : 'var(--bg-1)',
        border: `1px solid ${accent ? 'var(--accent-bd)' : 'var(--bd-1)'}`,
        borderRadius: 14,
      }}
    >
      <div
        style={{
          fontSize: 12,
          color: accent ? 'var(--accent)' : 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
        }}
      >
        {label}
      </div>
      <div
        className="tabular"
        style={{
          fontSize: 20,
          color: 'var(--fg-0)',
          fontWeight: 600,
          marginTop: 6,
        }}
      >
        {value}
      </div>
    </div>
  );
}

export function bigButton(
  tone: 'green',
  disabled: boolean,
): React.CSSProperties {
  return {
    flex: 2,
    height: 120,
    padding: '0 28px',
    background: `var(--${tone})`,
    color: '#fff',
    border: 'none',
    borderRadius: 16,
    fontSize: 24,
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 14,
    boxShadow: '0 4px 20px rgba(48,209,88,0.25)',
  };
}

export function problemButton(disabled: boolean): React.CSSProperties {
  return {
    flex: 1,
    height: 120,
    background: 'var(--red-bg)',
    color: 'var(--red)',
    border: '1px solid var(--red-bd)',
    borderRadius: 16,
    fontSize: 20,
    fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.6 : 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  };
}
