// Aprendi — primitivas partilhadas entre tabs (Q.60.X).
import { type ReactNode } from 'react';
import { Tag, type Tone } from '../atoms';

export function RuleStatusBadge({ status }: { status: string }): ReactNode {
  const tone: Tone =
    status === 'active' || status === 'approved' || status === 'confirmed'
      ? 'green'
      : status === 'rejected' ||
          status === 'suspended' ||
          status === 'rolled_back'
        ? 'red'
        : 'yellow';
  return <Tag tone={tone} size="sm">{status}</Tag>;
}

// ─── Tab: Camada 1 — regras aprendidas (preference-rules) ───────────
