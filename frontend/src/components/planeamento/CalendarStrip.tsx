/**
 * CalendarStrip — tira de dias do calendário de trabalho (Q.53.G).
 *
 * Sombra os fins-de-semana e feriados na timeline de Planeamento, para o
 * planeador ver de relance que dias não contam para o lead time. Os dias
 * vêm de `GET /v1/plan/calendar` (seeded por src/adapters/nelo/etl/
 * calendar.py). ZERO MOCKS — calendário não-seeded → empty state honesto.
 */

import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CalendarDays } from 'lucide-react';
import { planeamentoApi } from './planeamentoApi';

/** Próximos N dias a mostrar na tira. */
const WINDOW_DAYS = 21;

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

const WEEKDAY_PT = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

export function CalendarStrip(): ReactNode {
  const from = new Date();
  const to = new Date();
  to.setDate(to.getDate() + WINDOW_DAYS);

  const calendarQuery = useQuery({
    queryKey: ['planeamento', 'calendar', isoDate(from), isoDate(to)],
    queryFn: () =>
      planeamentoApi.calendar({ from_date: isoDate(from), to_date: isoDate(to) }),
    refetchOnWindowFocus: false,
  });

  // Calendário não-seeded ou indisponível: nada de tira, nota honesta.
  if (calendarQuery.isLoading) {
    return (
      <div style={{ fontSize: 11, color: 'var(--fg-3)', marginBottom: 10 }}>
        A carregar calendário da fábrica…
      </div>
    );
  }
  if (calendarQuery.isError) {
    return (
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          marginBottom: 10,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <CalendarDays size={12} />
        Calendário da fábrica indisponível — fins-de-semana não sombreados.
      </div>
    );
  }
  const items = calendarQuery.data?.items ?? [];
  if (items.length === 0) {
    return (
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          marginBottom: 10,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <CalendarDays size={12} />
        Calendário ainda não foi semeado — corre a mirror `calendar` do ETL.
      </div>
    );
  }

  const data = calendarQuery.data!;

  return (
    <div style={{ marginBottom: 12 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 6,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            fontSize: 11,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
          }}
        >
          <CalendarDays size={12} />
          Calendário · próximos {WINDOW_DAYS} dias
        </div>
        <div style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>
          {data.working_days} dias úteis · {data.non_working_days} fechados
        </div>
      </div>
      <div
        style={{
          display: 'flex',
          gap: 3,
          overflowX: 'auto',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-md)',
          background: 'var(--bg-1)',
          padding: 6,
        }}
      >
        {items.map((d) => {
          const date = new Date(`${d.day}T00:00:00`);
          const closed = !d.is_working_day;
          return (
            <div
              key={d.day}
              title={
                closed
                  ? `${d.day} · ${d.label ?? 'fechado'}`
                  : `${d.day} · ${d.shift_hours}h de turno`
              }
              style={{
                flex: '0 0 auto',
                width: 46,
                textAlign: 'center',
                padding: '5px 0',
                borderRadius: 'var(--r-sm)',
                background: closed ? 'var(--bg-3)' : 'var(--accent-bg)',
                border: `1px solid ${
                  closed ? 'var(--bd-2)' : 'var(--accent-bd)'
                }`,
                opacity: closed ? 0.65 : 1,
              }}
            >
              <div
                style={{
                  fontSize: 9,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                }}
              >
                {WEEKDAY_PT[date.getDay()]}
              </div>
              <div
                className="tabular"
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: closed ? 'var(--fg-3)' : 'var(--fg-0)',
                }}
              >
                {date.getDate()}
              </div>
              {closed && d.label && (
                <div
                  style={{
                    fontSize: 8,
                    color: 'var(--fg-3)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {d.label}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
