// EquipaPage — tipos, helpers e primitivas partilhadas pelas tabs (Q.60.T).
import { type ReactNode } from 'react';
import { ChevronUp, ChevronDown } from 'lucide-react';

export function qualityToLevel(score: number): number {
  if (score >= 9.0) return 3.0;
  if (score >= 8.0) return 2.5;
  if (score >= 6.5) return 2.0;
  if (score >= 5.0) return 1.5;
  return 1.0;
}

// ─── Tipos ──────────────────────────────────────────────────────────────────

export interface RawEmployee {
  id: string;
  employee_code: string;
  employee_name: string;
  status: string;
  hire_date: string | null;
  job_title: string | null;
  department: string | null;
}

export type Tier = '>12m' | '<12m' | '<5m';

export interface EnrichedEmployee extends RawEmployee {
  tier: Tier;
  score: number | null;
  err: number | null;
  ops: number | null;
}

// ─── Helpers ────────────────────────────────────────────────────────────────

export function tierFromHire(hire: string | null): Tier {
  if (!hire) return '<5m';
  const months = (Date.now() - new Date(hire).getTime()) / (1000 * 60 * 60 * 24 * 30);
  if (months >= 12) return '>12m';
  if (months >= 5) return '<12m';
  return '<5m';
}

export const TIER_TONE: Record<Tier, string> = {
  '>12m': 'green',
  '<12m': 'yellow',
  '<5m': 'red',
};

export function scoreTone(score: number | null): string {
  if (score === null) return 'fg-3';
  if (score >= 8) return 'green';
  if (score >= 6.5) return 'yellow';
  if (score >= 5) return 'orange';
  return 'red';
}

export type SortKey = 'name' | 'tier' | 'score' | 'nivel' | 'err' | 'ops' | 'status';

export function SortHeader({
  label,
  col,
  sortBy,
  sortDir,
  onSort,
  align = 'left',
}: {
  label: string;
  col: SortKey | null;
  sortBy?: SortKey;
  sortDir?: 'asc' | 'desc';
  onSort?: (col: SortKey) => void;
  align?: 'left' | 'right';
}) {
  const isActive = col !== null && sortBy === col;
  return (
    <th
      style={{
        padding: '10px 14px',
        textAlign: align,
        borderBottom: '1px solid var(--bd-1)',
      }}
    >
      {col && onSort ? (
        <button
          type="button"
          onClick={() => onSort(col)}
          style={{
            background: 'transparent',
            border: 'none',
            color: isActive ? 'var(--fg-0)' : 'var(--fg-3)',
            fontSize: 10.5,
            fontWeight: 600,
            letterSpacing: 0.4,
            textTransform: 'uppercase',
            cursor: 'pointer',
            padding: 0,
            display: 'inline-flex',
            alignItems: 'center',
            gap: 3,
          }}
        >
          {label}
          {isActive ? (
            sortDir === 'desc' ? (
              <ChevronDown size={11} />
            ) : (
              <ChevronUp size={11} />
            )
          ) : null}
        </button>
      ) : (
        <span
          style={{
            fontSize: 10.5,
            fontWeight: 600,
            letterSpacing: 0.4,
            textTransform: 'uppercase',
            color: 'var(--fg-3)',
          }}
        >
          {label}
        </span>
      )}
    </th>
  );
}

export function FilterSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        padding: '5px 8px',
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 6,
        color: 'var(--fg-1)',
        fontSize: 11.5,
        outline: 'none',
      }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function Tag({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span
      style={{
        fontSize: 9.5,
        padding: '2px 7px',
        background: `var(--${tone}-bg)`,
        border: `1px solid var(--${tone}-bd)`,
        borderRadius: 4,
        color: `var(--${tone})`,
        fontWeight: 600,
        textTransform: 'uppercase',
        letterSpacing: 0.3,
      }}
    >
      {children}
    </span>
  );
}

export function SectionHeader({
  icon,
  title,
  subtitle,
}: {
  icon: ReactNode;
  title: string;
  subtitle?: string;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: 'var(--accent)' }}>{icon}</span>
        <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-0)' }}>
          {title}
        </span>
      </div>
      {subtitle ? (
        <div style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 3 }}>
          {subtitle}
        </div>
      ) : null}
    </div>
  );
}
