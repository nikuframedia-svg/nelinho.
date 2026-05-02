/**
 * SuggestionExplainer — Plan v4 §8 contract.
 *
 * Renders the 5 mandatory blocks of every system suggestion as
 * distinct, scannable boxes (NOT collapsed in `<details>`):
 *
 *   1. O QUE       — what changes (delta)
 *   2. PORQUÊ      — why the system proposes (cause)
 *   3. SE ACEITAR  — positive consequence
 *   4. SE REJEITAR — negative consequence
 *   5. ALTERNATIVA — optional second-best (omitted when absent)
 *
 * Colour coding follows §4 (explica sempre): green=accept,
 * amber=reject, slate=alternative. The 5 blocks render as 2x2
 * grid + an alternative below; on narrow screens they stack.
 *
 * Sprint Q.9 Onda 3.1.
 */

import type { ReactNode } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  HelpCircle,
  Sparkles,
  XCircle,
} from 'lucide-react';

export interface SuggestionExplainerProps {
  what: ReactNode;
  why: ReactNode;
  ifAccept: ReactNode;
  ifReject: ReactNode;
  alternative?: ReactNode;
  className?: string;
}

interface BoxProps {
  label: string;
  tone: 'neutral' | 'reason' | 'accept' | 'reject' | 'alt';
  icon: ReactNode;
  children: ReactNode;
}

const TONES: Record<BoxProps['tone'], string> = {
  // Backgrounds use bg-*/10 so the text contrast stays high on dark.
  neutral: 'bg-slate-800/40 border-slate-700/60 text-slate-100',
  reason: 'bg-blue-500/10 border-blue-500/30 text-blue-50',
  accept: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-50',
  reject: 'bg-amber-500/10 border-amber-500/30 text-amber-50',
  alt: 'bg-violet-500/10 border-violet-500/30 text-violet-50',
};

function Box({ label, tone, icon, children }: BoxProps) {
  return (
    <div
      className={`rounded-lg border p-3 flex flex-col gap-2 ${TONES[tone]}`}
    >
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider opacity-80">
        <span className="shrink-0">{icon}</span>
        <span>{label}</span>
      </div>
      <div className="text-sm leading-snug">{children}</div>
    </div>
  );
}

export function SuggestionExplainer({
  what,
  why,
  ifAccept,
  ifReject,
  alternative,
  className = '',
}: SuggestionExplainerProps) {
  return (
    <div className={`flex flex-col gap-3 ${className}`}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Box label="O que" tone="neutral" icon={<ArrowRight className="w-3.5 h-3.5" />}>
          {what}
        </Box>
        <Box label="Porquê" tone="reason" icon={<HelpCircle className="w-3.5 h-3.5" />}>
          {why}
        </Box>
        <Box
          label="Se aceitar"
          tone="accept"
          icon={<CheckCircle2 className="w-3.5 h-3.5" />}
        >
          {ifAccept}
        </Box>
        <Box
          label="Se rejeitar"
          tone="reject"
          icon={<XCircle className="w-3.5 h-3.5" />}
        >
          {ifReject}
        </Box>
      </div>
      {alternative ? (
        <Box
          label="Alternativa"
          tone="alt"
          icon={<Sparkles className="w-3.5 h-3.5" />}
        >
          {alternative}
        </Box>
      ) : null}
    </div>
  );
}
