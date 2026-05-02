/**
 * ConsequenceBlock — Plan v4 §6.2 / §7.3 / §8 contract.
 *
 * Renders the 5-line impact summary that EVERY drag/move suggestion
 * must show in the UI. Each line carries an icon, a label, a value,
 * and an optional severity tone. Backend `PreviewDeltaService`
 * already returns the data; this component is the consistent visual
 * dialect across SchedulingPage, DispatchPage and TimelinePage.
 *
 * Severities follow §6.2 colour rules:
 *   info     — slate (default neutral consequence)
 *   positive — emerald (e.g. "+€2.400 throughput")
 *   warning  — amber  (e.g. "molde com 23% risco")
 *   critical — rose   (e.g. "FASE PARA")
 *
 * Sprint Q.9 Onda 3.1.
 */

import type { ReactNode } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  XOctagon,
} from 'lucide-react';

export type ConsequenceSeverity = 'info' | 'positive' | 'warning' | 'critical';

export interface ConsequenceLine {
  /** Short label rendered as a chip on the left. */
  label: string;
  /** The value/measurement (e.g. "+€2.400", "FASE PARA", "Paulo Gomes"). */
  value: ReactNode;
  /** Optional explanatory sub-text. */
  detail?: ReactNode;
  /** Severity drives the icon + tone. Defaults to "info". */
  severity?: ConsequenceSeverity;
}

export interface ConsequenceBlockProps {
  title?: string;
  lines: ConsequenceLine[];
  className?: string;
}

const SEVERITY_ROW: Record<ConsequenceSeverity, string> = {
  info: 'bg-slate-800/40 border-slate-700/60',
  positive: 'bg-emerald-500/10 border-emerald-500/30',
  warning: 'bg-amber-500/10 border-amber-500/30',
  critical: 'bg-rose-500/10 border-rose-500/30',
};

const SEVERITY_VALUE_TEXT: Record<ConsequenceSeverity, string> = {
  info: 'text-slate-100',
  positive: 'text-emerald-200',
  warning: 'text-amber-200',
  critical: 'text-rose-200',
};

function severityIcon(severity: ConsequenceSeverity) {
  const iconClass = 'w-4 h-4 shrink-0';
  switch (severity) {
    case 'positive':
      return <CheckCircle2 className={`${iconClass} text-emerald-300`} />;
    case 'warning':
      return <AlertTriangle className={`${iconClass} text-amber-300`} />;
    case 'critical':
      return <XOctagon className={`${iconClass} text-rose-300`} />;
    case 'info':
    default:
      return <Info className={`${iconClass} text-slate-300`} />;
  }
}

export function ConsequenceBlock({
  title = 'Consequências',
  lines,
  className = '',
}: ConsequenceBlockProps) {
  if (!lines.length) {
    return null;
  }
  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      {title ? (
        <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </div>
      ) : null}
      <div className="flex flex-col gap-1.5">
        {lines.map((line, idx) => {
          const severity: ConsequenceSeverity = line.severity ?? 'info';
          return (
            <div
              key={`${line.label}-${idx}`}
              className={`flex items-start gap-3 rounded-md border px-3 py-2 ${SEVERITY_ROW[severity]}`}
            >
              <div className="pt-0.5">{severityIcon(severity)}</div>
              <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2 flex-wrap">
                  <span className="text-xs uppercase tracking-wide text-slate-300">
                    {line.label}
                  </span>
                  <span className={`text-sm font-semibold ${SEVERITY_VALUE_TEXT[severity]}`}>
                    {line.value}
                  </span>
                </div>
                {line.detail ? (
                  <span className="text-xs text-slate-400">{line.detail}</span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
