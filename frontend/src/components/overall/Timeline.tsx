/**
 * Timeline — cabeçalho horizontal de dias reutilizável (Q.115.K).
 *
 * Composição fina sobre TimelineLanes: converte um intervalo de datas em
 * slots diários, semanais ou mensais e passa os `children` render-prop
 * para o caller posicionar operações.
 *
 * Exporta também `buildDaySlots` para os callers produzirem `TimelineItem[]`
 * a partir de datas ISO.
 */

import type { ReactNode } from 'react';
import {
  format,
  eachDayOfInterval,
  eachWeekOfInterval,
  eachMonthOfInterval,
  startOfDay,
  isToday,
  isSameMonth,
  isWithinInterval,
  endOfWeek,
  differenceInCalendarDays,
  differenceInCalendarWeeks,
  differenceInCalendarMonths,
} from 'date-fns';
import { pt } from 'date-fns/locale';
import { TimelineLanes } from '../dark';
import type { TimelineSlot, TimelineLane, TimelineItem } from '../dark';

// ─── Tipos públicos ──────────────────────────────────────────────────────────

export type TimelineScale = 'day' | 'week' | 'month';

const _WEEK_OPTS = { weekStartsOn: 1 as const };

export interface TimelineProps {
  startDate: Date;
  endDate: Date;
  scale?: TimelineScale;
  lanes: TimelineLane[];
  items: TimelineItem[];
  slotWidth?: number;
  laneHeight?: number;
  renderItem: (item: TimelineItem) => ReactNode;
}

// ─── Helpers públicos ────────────────────────────────────────────────────────

/** Constrói TimelineSlots em escala "day". */
export function buildDaySlots(startDate: Date, endDate: Date): TimelineSlot[] {
  return eachDayOfInterval({ start: startDate, end: endDate }).map((d) => ({
    id: format(d, 'yyyy-MM-dd'),
    label: format(d, 'd MMM', { locale: pt }),
    highlight: isToday(d),
  }));
}

/** Escala "week" — Q.141.F. id = data de início da semana (segunda). */
export function buildWeekSlots(startDate: Date, endDate: Date): TimelineSlot[] {
  const now = new Date();
  return eachWeekOfInterval({ start: startDate, end: endDate }, _WEEK_OPTS).map((w) => ({
    id: format(w, 'yyyy-MM-dd'),
    label: `Sem ${format(w, 'd MMM', { locale: pt })}`,
    highlight: isWithinInterval(now, { start: w, end: endOfWeek(w, _WEEK_OPTS) }),
  }));
}

/** Escala "month" — Q.141.F. id = data de início do mês. */
export function buildMonthSlots(startDate: Date, endDate: Date): TimelineSlot[] {
  const now = new Date();
  return eachMonthOfInterval({ start: startDate, end: endDate }).map((m) => ({
    id: format(m, 'yyyy-MM-dd'),
    label: format(m, 'MMM yyyy', { locale: pt }),
    highlight: isSameMonth(now, m),
  }));
}

/** Dispatcher por escala (Q.141.F). */
export function buildSlots(
  scale: TimelineScale, startDate: Date, endDate: Date,
): TimelineSlot[] {
  if (scale === 'week') return buildWeekSlots(startDate, endDate);
  if (scale === 'month') return buildMonthSlots(startDate, endDate);
  return buildDaySlots(startDate, endDate);
}

/**
 * Índice de coluna (0-based) de uma data ISO, conforme a escala. `null` se a
 * data faltar; nunca negativo (datas antes do início caem na coluna 0).
 */
export function dateToSlotIndex(
  isoDate: string | undefined | null,
  startDate: Date,
  scale: TimelineScale = 'day',
): number | null {
  if (!isoDate) return null;
  const d = startOfDay(new Date(isoDate));
  const s = startOfDay(startDate);
  let diff: number;
  if (scale === 'week') diff = differenceInCalendarWeeks(d, s, _WEEK_OPTS);
  else if (scale === 'month') diff = differenceInCalendarMonths(d, s);
  else diff = differenceInCalendarDays(d, s);
  return diff < 0 ? 0 : diff;
}

// ─── Componente ──────────────────────────────────────────────────────────────

export function Timeline({
  startDate,
  endDate,
  scale = 'day',
  lanes,
  items,
  slotWidth = 72,
  laneHeight = 52,
  renderItem,
}: TimelineProps): ReactNode {
  // Q.141.F — dia/semana/mês reais (o stub "Q.115.L" foi removido).
  const slots = buildSlots(scale, startDate, endDate);

  return (
    <TimelineLanes
      slots={slots}
      lanes={lanes}
      items={items}
      slotWidth={slotWidth}
      laneHeight={laneHeight}
      renderItem={renderItem}
    />
  );
}
