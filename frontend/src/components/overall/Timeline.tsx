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
import { format, eachDayOfInterval, startOfDay, isToday } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import { TimelineLanes } from '../dark';
import type { TimelineSlot, TimelineLane, TimelineItem } from '../dark';

// ─── Tipos públicos ──────────────────────────────────────────────────────────

export type TimelineScale = 'day' | 'week' | 'month';

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

/** Constrói TimelineSlots a partir do intervalo [startDate, endDate] em escala "day". */
export function buildDaySlots(startDate: Date, endDate: Date): TimelineSlot[] {
  const days = eachDayOfInterval({ start: startDate, end: endDate });
  return days.map((d) => ({
    id: format(d, 'yyyy-MM-dd'),
    label: format(d, 'd MMM', { locale: ptBR }),
    highlight: isToday(d),
  }));
}

/**
 * Dado uma data ISO e o início da timeline, devolve o índice de coluna (0-based).
 * Retorna null se a data cair fora do intervalo.
 */
export function dateToSlotIndex(
  isoDate: string | undefined | null,
  startDate: Date,
): number | null {
  if (!isoDate) return null;
  const d = startOfDay(new Date(isoDate));
  const s = startOfDay(startDate);
  const diff = Math.round((d.getTime() - s.getTime()) / 86_400_000);
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
  // Para já só "day" está implementado; week/month ficarão para Q.115.L.
  if (scale !== 'day') {
    return (
      <div
        className="text-xs text-slate-400 p-4 text-center"
        style={{ border: '1px solid var(--bd-1)', borderRadius: 'var(--r-md)' }}
      >
        Vista por semana/mês disponível em Q.115.L.
      </div>
    );
  }

  const slots = buildDaySlots(startDate, endDate);

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
