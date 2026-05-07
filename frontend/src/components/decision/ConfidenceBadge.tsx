/**
 * ConfidenceBadge — Plan v4 §4 / §8 contract.
 *
 * Every system suggestion exposes a confidence score so the human
 * decision-maker reads two signals at once: a numeric percentage AND
 * a coarse band (Alta / Média / Baixa). Showing the band alone hides
 * delta; showing the number alone forces mental arithmetic on the
 * shop floor. We render both, with an icon, so colour is never the
 * sole information channel (FRONTEND_DESIGN_PROMPT §2.2).
 *
 * Bands match the governance learning thresholds:
 *   Alta   ≥ 0.80
 *   Média  ≥ 0.50
 *   Baixa  < 0.50
 */

import { ShieldCheck, ShieldAlert, ShieldOff } from 'lucide-react';
import type { Confidence } from '../../types/decision';
import { confidenceBand, type ConfidenceBand } from './confidenceBand';

export interface ConfidenceBadgeProps {
  value: Confidence;
  /** Render the percentage next to the label. Defaults to true. */
  showNumeric?: boolean;
  /** Compact pill (icon + label only). Defaults to false. */
  compact?: boolean;
  className?: string;
}

const BAND_STYLES: Record<ConfidenceBand, { wrap: string; label: string }> = {
  alta: {
    wrap: 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200',
    label: 'Alta',
  },
  media: {
    wrap: 'bg-amber-500/15 border-amber-500/40 text-amber-200',
    label: 'Média',
  },
  baixa: {
    wrap: 'bg-rose-500/15 border-rose-500/40 text-rose-200',
    label: 'Baixa',
  },
};

function bandIcon(band: ConfidenceBand) {
  const cls = 'w-3.5 h-3.5 shrink-0';
  switch (band) {
    case 'alta':
      return <ShieldCheck className={cls} />;
    case 'media':
      return <ShieldAlert className={cls} />;
    case 'baixa':
      return <ShieldOff className={cls} />;
  }
}

export function ConfidenceBadge({
  value,
  showNumeric = true,
  compact = false,
  className = '',
}: ConfidenceBadgeProps) {
  const safeValue = Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;
  const band = confidenceBand(safeValue);
  const style = BAND_STYLES[band];
  const pct = Math.round(safeValue * 100);
  const numeric = showNumeric ? `${pct}%` : null;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider ${style.wrap} ${className}`}
      aria-label={`Confiança ${style.label}${numeric ? `, ${pct} por cento` : ''}`}
      data-confidence-band={band}
    >
      {bandIcon(band)}
      <span>{style.label}</span>
      {!compact && numeric ? (
        <span className="font-mono normal-case tracking-normal opacity-80">
          {numeric}
        </span>
      ) : null}
    </span>
  );
}
