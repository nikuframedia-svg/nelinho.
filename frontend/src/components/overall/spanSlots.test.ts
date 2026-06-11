/**
 * Testes Q.173.AE — cálculo de spanSlots por escala.
 */

import { describe, it, expect } from 'vitest';
import { dateToSpanSlots } from './Timeline';

const START = new Date('2026-06-01T00:00:00Z');

describe('dateToSpanSlots — escala dia', () => {
  it('devolve 1 se sem end e sem duração', () => {
    expect(dateToSpanSlots('2026-06-01', null, null, START, 'day', 30)).toBe(1);
  });

  it('calcula span entre start e end (mesmo dia)', () => {
    // start=1 Jun, end=2 Jun → 1 slot
    expect(dateToSpanSlots('2026-06-01', '2026-06-02', null, START, 'day', 30)).toBe(1);
  });

  it('calcula span de 3 dias', () => {
    expect(dateToSpanSlots('2026-06-01', '2026-06-04', null, START, 'day', 30)).toBe(3);
  });

  it('clamp ao fim do intervalo visível', () => {
    // start=1 Jun, end=31 Jun, mas só 10 slots → clamp a 10
    expect(dateToSpanSlots('2026-06-01', '2026-06-30', null, START, 'day', 10)).toBe(10);
  });

  it('usa duration_min se sem end (480 min/dia → 1 slot)', () => {
    expect(dateToSpanSlots('2026-06-01', null, 480, START, 'day', 30)).toBe(1);
  });

  it('usa duration_min de 960 min → 2 slots', () => {
    expect(dateToSpanSlots('2026-06-01', null, 960, START, 'day', 30)).toBe(2);
  });

  it('devolve 1 se start undefined', () => {
    expect(dateToSpanSlots(null, '2026-06-05', null, START, 'day', 30)).toBe(1);
  });

  it('devolve 1 se end <= start', () => {
    // end=start → span=0 → mín 1
    expect(dateToSpanSlots('2026-06-05', '2026-06-05', null, START, 'day', 30)).toBe(1);
  });
});

describe('dateToSpanSlots — escala semana', () => {
  it('ops de 1 semana → 1 slot', () => {
    // start=1 Jun (sem 1 Jun), end=8 Jun (1 semana depois) → 1 slot
    expect(dateToSpanSlots('2026-06-01', '2026-06-08', null, START, 'week', 12)).toBe(1);
  });

  it('ops de 2 semanas → 2 slots', () => {
    expect(dateToSpanSlots('2026-06-01', '2026-06-15', null, START, 'week', 12)).toBe(2);
  });

  it('duration_min 2400 min (1 semana) → 1 slot', () => {
    expect(dateToSpanSlots('2026-06-01', null, 2400, START, 'week', 12)).toBe(1);
  });
});

describe('dateToSpanSlots — escala mês', () => {
  it('ops de 1 mês → 1 slot', () => {
    expect(dateToSpanSlots('2026-06-01', '2026-07-01', null, START, 'month', 6)).toBe(1);
  });

  it('ops de 2 meses → 2 slots', () => {
    expect(dateToSpanSlots('2026-06-01', '2026-08-01', null, START, 'month', 6)).toBe(2);
  });
});
