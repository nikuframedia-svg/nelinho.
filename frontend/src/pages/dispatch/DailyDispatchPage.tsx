/**
 * DailyDispatchPage — Plan v4 §4.3 (vista Atribuição) standalone.
 *
 * Página chão-de-fábrica focada em "que ops temos para esta data, e
 * que operadores as fazem". Tem date picker (default hoje) e usa o
 * componente partilhado `AssignmentTable` que faz o swap-flow
 * (worker-pairs → preview-delta → apply-move) com razão ≥10 chars.
 *
 * É ortogonal às páginas de transporte:
 *  - DispatchPage (`/dispatch`) trata transport batches (3 rails, drag-drop
 *    de orders entre camiões, freeze, dispatch).
 *  - ExpedicaoPage (`/expedicao`) é a vista alto nível dos camiões.
 *  - DailyDispatchPage (`/dispatch/today`) é o despacho diário do CHÃO de
 *    fábrica — operadores × ops do dia.
 *
 * ZERO MOCKS — todos os estados (loading/error/empty) são tratados pelo
 * `AssignmentTable` próprio.
 */

import { useState } from 'react';
import { Calendar, ChevronLeft, ChevronRight, Hammer, RefreshCw } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { DarkPageLayout } from '../../layouts';
import { DarkButton, DarkCard } from '../../components/dark';
import { AssignmentTable } from '../../components/scheduling/AssignmentTable';

function isoLocalKey(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function shiftDays(d: Date, delta: number): Date {
  const next = new Date(d);
  next.setDate(d.getDate() + delta);
  next.setHours(0, 0, 0, 0);
  return next;
}

function startOfDay(d: Date): Date {
  const next = new Date(d);
  next.setHours(0, 0, 0, 0);
  return next;
}

export default function DailyDispatchPage() {
  const queryClient = useQueryClient();
  const [date, setDate] = useState<Date>(() => startOfDay(new Date()));

  const dateValue = isoLocalKey(date);
  const today = startOfDay(new Date());
  const isToday = isoLocalKey(date) === isoLocalKey(today);
  const isTomorrow = isoLocalKey(date) === isoLocalKey(shiftDays(today, 1));

  const dateLabel = date.toLocaleDateString('pt-PT', {
    weekday: 'long',
    day: '2-digit',
    month: 'long',
    year: 'numeric',
  });

  return (
    <DarkPageLayout
      title="Plano de Hoje"
      subtitle="Atribuição diária — operadores × operações. Trocar requer razão (alimenta a aprendizagem)."
      icon={<Hammer className="w-6 h-6 text-amber-300" />}
      actions={
        <DarkButton
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['cpo', 'commits'] });
          }}
          variant="secondary"
        >
          <RefreshCw className="w-4 h-4" /> Refrescar
        </DarkButton>
      }
    >
      <div className="flex flex-col gap-4">
        <DarkCard className="p-3 flex flex-wrap items-center gap-3">
          <Calendar className="w-4 h-4 text-slate-400" />
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setDate((d) => shiftDays(d, -1))}
              className="p-1.5 rounded-md border border-slate-700 hover:bg-slate-800 text-slate-300"
              aria-label="Dia anterior"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <input
              type="date"
              value={dateValue}
              onChange={(e) => {
                const [y, m, d] = e.target.value.split('-').map(Number);
                if (y && m && d) {
                  setDate(startOfDay(new Date(y, m - 1, d)));
                }
              }}
              className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
            />
            <button
              type="button"
              onClick={() => setDate((d) => shiftDays(d, 1))}
              className="p-1.5 rounded-md border border-slate-700 hover:bg-slate-800 text-slate-300"
              aria-label="Dia seguinte"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setDate(today)}
              className={`px-2.5 py-1 rounded-md text-xs border ${
                isToday
                  ? 'bg-amber-500/15 border-amber-500/40 text-amber-100'
                  : 'border-slate-700 text-slate-300 hover:bg-slate-800'
              }`}
            >
              Hoje
            </button>
            <button
              type="button"
              onClick={() => setDate(shiftDays(today, 1))}
              className={`px-2.5 py-1 rounded-md text-xs border ${
                isTomorrow
                  ? 'bg-amber-500/15 border-amber-500/40 text-amber-100'
                  : 'border-slate-700 text-slate-300 hover:bg-slate-800'
              }`}
            >
              Amanhã
            </button>
          </div>
          <span className="text-sm text-slate-300 capitalize ml-auto">
            {dateLabel}
          </span>
        </DarkCard>

        <AssignmentTable date={date} />
      </div>
    </DarkPageLayout>
  );
}
