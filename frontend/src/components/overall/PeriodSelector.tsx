/**
 * PeriodSelector — atalhos de intervalo + escolha custom (Q.141.E).
 *
 * Controla a janela temporal da /overall: atalhos (Ontem, Hoje, Amanhã,
 * Próximos 7 dias, Últimos 7 dias, Este mês) + dois date inputs de/até.
 * Componente controlado: o pai detém {start,end} e recebe onChange.
 */
import { useMemo } from 'react';
import {
  addDays,
  startOfDay,
  startOfMonth,
  endOfMonth,
  format,
  isSameDay,
} from 'date-fns';

export interface PeriodRange {
  start: Date;
  end: Date;
}

interface PeriodSelectorProps {
  start: Date;
  end: Date;
  today: Date;
  onChange: (range: PeriodRange) => void;
}

interface Shortcut {
  id: string;
  label: string;
  range: (today: Date) => PeriodRange;
}

const SHORTCUTS: Shortcut[] = [
  { id: 'ontem', label: 'Ontem', range: (t) => ({ start: addDays(t, -1), end: addDays(t, -1) }) },
  { id: 'hoje', label: 'Hoje', range: (t) => ({ start: t, end: t }) },
  { id: 'amanha', label: 'Amanhã', range: (t) => ({ start: addDays(t, 1), end: addDays(t, 1) }) },
  { id: 'ultimos7', label: 'Últimos 7 dias', range: (t) => ({ start: addDays(t, -7), end: t }) },
  { id: 'proximos7', label: 'Próximos 7 dias', range: (t) => ({ start: t, end: addDays(t, 7) }) },
  { id: 'mes', label: 'Este mês', range: (t) => ({ start: startOfMonth(t), end: endOfMonth(t) }) },
];

function parseInput(value: string): Date | null {
  if (!value) return null;
  const d = new Date(`${value}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : startOfDay(d);
}

export function PeriodSelector({ start, end, today, onChange }: PeriodSelectorProps) {
  const activeId = useMemo(() => {
    const t = startOfDay(today);
    for (const sc of SHORTCUTS) {
      const r = sc.range(t);
      if (isSameDay(r.start, start) && isSameDay(r.end, end)) return sc.id;
    }
    return null;
  }, [start, end, today]);

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <div
        className="flex items-center gap-0.5 rounded-lg p-0.5"
        style={{ background: 'var(--bg-4)', border: '1px solid var(--bd-2)' }}
      >
        {SHORTCUTS.map((sc) => (
          <button
            key={sc.id}
            onClick={() => onChange(sc.range(startOfDay(today)))}
            className="px-2.5 py-1 rounded-md text-xs font-medium transition whitespace-nowrap"
            style={
              activeId === sc.id
                ? { background: 'var(--accent)', color: '#fff' }
                : { color: 'var(--fg-3)' }
            }
          >
            {sc.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--fg-3)' }}>
        <input
          type="date"
          aria-label="Data inicial"
          value={format(start, 'yyyy-MM-dd')}
          max={format(end, 'yyyy-MM-dd')}
          onChange={(e) => {
            const d = parseInput(e.target.value);
            if (d) onChange({ start: d, end: d > end ? d : end });
          }}
          className="rounded-md px-2 py-1 text-xs"
          style={{ background: 'var(--bg-3)', border: '1px solid var(--bd-2)', color: 'var(--fg-1)' }}
        />
        <span>→</span>
        <input
          type="date"
          aria-label="Data final"
          value={format(end, 'yyyy-MM-dd')}
          min={format(start, 'yyyy-MM-dd')}
          onChange={(e) => {
            const d = parseInput(e.target.value);
            if (d) onChange({ start: d < start ? d : start, end: d });
          }}
          className="rounded-md px-2 py-1 text-xs"
          style={{ background: 'var(--bg-3)', border: '1px solid var(--bd-2)', color: 'var(--fg-1)' }}
        />
      </div>
    </div>
  );
}

export default PeriodSelector;
