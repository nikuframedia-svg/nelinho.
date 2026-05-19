// Decomposto de FabricaPage.tsx (Q.60.AB).
import type { ReactNode } from 'react';
import type { ActiveOrderCard } from './fabricaApi';

export interface PendingMove {
  boat: ActiveOrderCard;
  targetPhase: string;
}

export interface EmployeeRow {
  id: string;
  name: string;
}

export function deriveInitials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '—';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Vista da Fábrica: estado cru vs plano optimizado do CPO. */
export type FabricaView = 'estado' | 'plano';

export function KpiTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: 'green' | 'yellow' | 'red';
}): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        padding: 12,
      }}
    >
      <div
        style={{
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
        }}
      >
        {label}
      </div>
      <div
        className="display tabular"
        style={{
          fontSize: 22,
          fontWeight: 500,
          color: tone ? `var(--${tone})` : 'var(--fg-0)',
          marginTop: 4,
        }}
      >
        {value}
      </div>
    </div>
  );
}
