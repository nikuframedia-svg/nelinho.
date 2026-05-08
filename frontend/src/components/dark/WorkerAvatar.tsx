/**
 * WorkerAvatar — iniciais + score ★ + tier badge.
 *
 * Usado na EquipaPage tabela e nas BoatCard (operadores atribuídos).
 * O avatar nunca tem imagem real (privacidade fábrica) — só iniciais
 * derivadas do nome.
 *
 * Plan v4 §4.5 / FRONTEND_DESIGN_PROMPT §3.2.
 * Sprint Q.18.UI.A.
 */

import type { ReactNode } from 'react';
import { Star } from 'lucide-react';

type WorkerTier = '<5m' | '<12m' | '>12m' | 'unknown';
type WorkerStatus = 'active' | 'vacation' | 'sick' | 'inactive';
type AvatarSize = 'xs' | 'sm' | 'md' | 'lg';

export interface WorkerAvatarProps {
  name: string;
  score?: number;
  tier?: WorkerTier;
  status?: WorkerStatus;
  size?: AvatarSize;
  showName?: boolean;
  showScore?: boolean;
  showTier?: boolean;
  className?: string;
  onClick?: () => void;
}

const SIZE: Record<AvatarSize, { circle: string; text: string; nameText: string }> = {
  xs: { circle: 'w-6 h-6', text: 'text-[10px]', nameText: 'text-xs' },
  sm: { circle: 'w-8 h-8', text: 'text-xs', nameText: 'text-sm' },
  md: { circle: 'w-10 h-10', text: 'text-sm', nameText: 'text-sm' },
  lg: { circle: 'w-14 h-14', text: 'text-lg', nameText: 'text-base' },
};

const STATUS_DOT: Record<WorkerStatus, string> = {
  active: 'bg-success',
  vacation: 'bg-warning',
  sick: 'bg-danger',
  inactive: 'bg-slate-500',
};

const TIER_LABEL: Record<WorkerTier, string> = {
  '<5m': '<5m',
  '<12m': '<12m',
  '>12m': '>12m',
  unknown: '—',
};

const TIER_BG: Record<WorkerTier, string> = {
  '<5m': 'bg-warning/20 text-warning border-warning/40',
  '<12m': 'bg-primary-500/20 text-primary-300 border-primary-500/40',
  '>12m': 'bg-success/20 text-success border-success/40',
  unknown: 'bg-slate-700/50 text-slate-400 border-slate-600',
};

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function WorkerAvatar({
  name,
  score,
  tier,
  status,
  size = 'md',
  showName = false,
  showScore = false,
  showTier = false,
  className = '',
  onClick,
}: WorkerAvatarProps): ReactNode {
  const s = SIZE[size];
  const interactive = onClick !== undefined;

  return (
    <div
      className={`inline-flex items-center gap-2 ${interactive ? 'cursor-pointer' : ''} ${className}`}
      onClick={onClick}
    >
      <div className="relative">
        <div
          className={`${s.circle} rounded-full bg-gradient-to-br from-accent-500/30 to-accent-700/30 border border-accent-500/40 flex items-center justify-center font-bold text-accent-300 ${s.text} select-none`}
          aria-label={name}
          title={name}
        >
          {initials(name)}
        </div>
        {status ? (
          <div
            className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full ${STATUS_DOT[status]} border-2 border-dark-800`}
            aria-label={`Estado: ${status}`}
          />
        ) : null}
      </div>

      {(showName || showScore || showTier) && (
        <div className="flex flex-col gap-0.5 min-w-0">
          {showName ? (
            <span className={`${s.nameText} font-medium text-text-dark-primary truncate`}>
              {name}
            </span>
          ) : null}
          <div className="flex items-center gap-2">
            {showScore && score !== undefined ? (
              <span className="inline-flex items-center gap-0.5 text-xs font-semibold text-warning">
                <Star className="w-3 h-3 fill-warning" />
                <span className="tabular-nums">{score.toFixed(1)}</span>
              </span>
            ) : null}
            {showTier && tier ? (
              <span
                className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border ${TIER_BG[tier]} tabular-nums`}
              >
                {TIER_LABEL[tier]}
              </span>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
