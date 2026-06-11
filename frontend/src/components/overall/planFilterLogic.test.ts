/**
 * Testes Q.173.AF — função pura filterOps + serialização URL.
 *
 * filterOps é pura (sem React, sem fetch) — testável directamente.
 */

import { describe, it, expect } from 'vitest';
import { filterOps, filtersToSearchParams, filtersFromSearchParams, FILTER_DEFAULTS, countActiveFilters } from './planFilterLogic';
import type { PlanFilterState } from './planFilterLogic';
import type { ScheduledOp } from './types';
import type { FiltersContextOut } from '../../lib/api/planApi';

// ─── Fixtures ────────────────────────────────────────────────────────────────

const CTX: FiltersContextOut = {
  commit_sha: 'abc',
  product_names: { 'K1': 'Kayak Alpha', 'C2': 'Canoa Beta' },
  order_products: { '1001': 'K1', '1002': 'C2', '1003': 'K1' },
  product_gamas: { 'K1': 'Kayak', 'C2': 'Canoa' },
  phase_sectors: { '10': 'Laminação', '20': 'Acabamentos', '30': 'Laminação' },
  orders_boost: { '1001': 2 },
  orders_due: { '1001': '2026-06-15', '1002': '2026-06-20' },
  orders_material_risk: ['1002'],
  repair_phase_ids: ['76', '77'],
  material_risk_stale: false,
};

function makeOp(overrides: Partial<ScheduledOp>): ScheduledOp {
  return {
    id: 'op1',
    phase_id: '10',
    phase_name: 'Laminação',
    order_id: '1001',
    product_id: 'K1',
    operator_id: 'EMP01',
    operator_name: 'João Silva',
    cliente: 'Loja A',
    start: '2026-06-12T08:00:00+00:00',
    end: '2026-06-13T08:00:00+00:00',
    source: 'plan',
    ...overrides,
  };
}

const BASE_OPS: ScheduledOp[] = [
  makeOp({ id: 'op1', order_id: '1001', phase_id: '10', product_id: 'K1', operator_id: 'EMP01', source: 'plan' }),
  makeOp({ id: 'op2', order_id: '1002', phase_id: '20', product_id: 'C2', operator_id: 'EMP02', source: 'actual', cliente: 'Loja B' }),
  makeOp({ id: 'op3', order_id: '1003', phase_id: '76', product_id: 'K1', operator_id: 'EMP01', source: 'plan' }),
];

const filters0 = (): PlanFilterState => ({ ...FILTER_DEFAULTS });

// ─── filterOps — predicados ───────────────────────────────────────────────────

describe('filterOps — sem filtros', () => {
  it('devolve todas as ops quando nenhum filtro activo', () => {
    const result = filterOps(BASE_OPS, CTX, filters0());
    expect(result).toHaveLength(3);
  });

  it('funciona sem ctx (resiliente)', () => {
    const result = filterOps(BASE_OPS, null, filters0());
    expect(result).toHaveLength(3);
  });
});

describe('filterOps — filtro texto', () => {
  it('filtra por order_id', () => {
    const f = { ...filters0(), text: '1001' };
    expect(filterOps(BASE_OPS, CTX, f)).toHaveLength(1);
    expect(filterOps(BASE_OPS, CTX, f)[0].id).toBe('op1');
  });

  it('filtra por operator_name (case-insensitive)', () => {
    const f = { ...filters0(), text: 'loja b' };
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('op2');
  });
});

describe('filterOps — filtro modelo', () => {
  it('filtra por código de produto', () => {
    const f = { ...filters0(), modelos: ['C2'] };
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('op2');
  });

  it('aceita múltiplos modelos', () => {
    const f = { ...filters0(), modelos: ['K1', 'C2'] };
    expect(filterOps(BASE_OPS, CTX, f)).toHaveLength(3);
  });
});

describe('filterOps — filtro fase', () => {
  it('filtra por phase_id', () => {
    const f = { ...filters0(), fases: ['20'] };
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('op2');
  });
});

describe('filterOps — filtro setor', () => {
  it('filtra fases do setor Laminação (IDs 10 e 30→76)', () => {
    const f = { ...filters0(), setores: ['Laminação'] };
    // phase_sectors: '10'→'Laminação', '76'→não definido (reparação). op1(10)✓, op3(76)✗, op2(20)✗
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('op1');
  });
});

describe('filterOps — filtro gama', () => {
  it('filtra por disciplina Kayak', () => {
    const f = { ...filters0(), gamas: ['Kayak'] };
    // op1(K1→Kayak)✓, op2(C2→Canoa)✗, op3(K1→Kayak)✓
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(2);
  });
});

describe('filterOps — filtro material em risco', () => {
  it('só mostra ordens com risco de material', () => {
    const f = { ...filters0(), materialRisco: true };
    // orders_material_risk: ['1002'] → op2 ✓
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('op2');
  });
});

describe('filterOps — filtro reparações', () => {
  it('"só reparações" mostra só ops em repair_phase_ids', () => {
    const f = { ...filters0(), reparacoes: 'so' as const };
    // repair_phase_ids: ['76','77'] → op3(76)✓
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('op3');
  });

  it('"excluir reparações" esconde ops em repair_phase_ids', () => {
    const f = { ...filters0(), reparacoes: 'excluir' as const };
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(2);
    expect(result.find((o) => o.id === 'op3')).toBeUndefined();
  });
});

describe('filterOps — filtro prioridade', () => {
  it('só mostra ordens com boost > 0', () => {
    const f = { ...filters0(), prioridade: true };
    // orders_boost: {'1001': 2} → op1 ✓
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('op1');
  });
});

describe('filterOps — filtro estado', () => {
  it('"realizado" só devolve actuals', () => {
    const f = { ...filters0(), estado: 'realizado' as const };
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].source).toBe('actual');
  });

  it('"planeado" exclui actuals', () => {
    const f = { ...filters0(), estado: 'planeado' as const };
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result.every((o) => o.source !== 'actual')).toBe(true);
    expect(result).toHaveLength(2);
  });

  it('"atrasado" mostra ops cujo end > orders_due', () => {
    const opsAtraso: ScheduledOp[] = [
      makeOp({ id: 'late', order_id: '1001', end: '2026-06-20T00:00:00Z', source: 'plan' }),
      makeOp({ id: 'ok', order_id: '1002', end: '2026-06-18T00:00:00Z', source: 'plan' }),
    ];
    // orders_due: {'1001':'2026-06-15', '1002':'2026-06-20'}
    // late: end=20 > due=15 ✓; ok: end=18 < due=20 ✗
    const f = { ...filters0(), estado: 'atrasado' as const };
    const result = filterOps(opsAtraso, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('late');
  });
});

describe('filterOps — filtro expedição', () => {
  it('filtra por janela de promessa', () => {
    const f = { ...filters0(), expedicaoFrom: '2026-06-16', expedicaoTo: '2026-06-25' };
    // orders_due: 1001→15 (fora), 1002→20 (dentro)
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('op2');
  });

  it('"sem promessa" mostra só ordens sem due date', () => {
    const f = { ...filters0(), expedicaoSemPromessa: true };
    // 1003 não tem due date
    const result = filterOps(BASE_OPS, CTX, f);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('op3');
  });
});

// ─── Serialização URL ─────────────────────────────────────────────────────────

describe('filtersToSearchParams / filtersFromSearchParams', () => {
  it('round-trip: serializa e desserializa sem perda', () => {
    const f: PlanFilterState = {
      ...FILTER_DEFAULTS,
      text: 'kayak',
      modelos: ['K1', 'C2'],
      fases: ['10'],
      operadores: ['EMP01'],
      setores: ['Laminação'],
      expedicaoFrom: '2026-06-01',
      expedicaoTo: '2026-06-30',
      expedicaoSemPromessa: false,
      gamas: ['Kayak'],
      materialRisco: true,
      reparacoes: 'excluir',
      prioridade: true,
      estado: 'planeado',
    };
    const params = filtersToSearchParams(f);
    const back = filtersFromSearchParams(params);
    expect(back).toEqual(f);
  });

  it('defaults produzem URLSearchParams vazio (só texto se presente)', () => {
    const params = filtersToSearchParams(FILTER_DEFAULTS);
    expect(params.toString()).toBe('');
  });

  it('params desconhecidos são ignorados', () => {
    const p = new URLSearchParams('f_unknown=foo&f_text=ok');
    const f = filtersFromSearchParams(p);
    expect(f.text).toBe('ok');
    expect(f.modelos).toHaveLength(0);
  });
});

// ─── countActiveFilters ───────────────────────────────────────────────────────

describe('countActiveFilters', () => {
  it('defaults = 0 filtros activos', () => {
    expect(countActiveFilters(FILTER_DEFAULTS)).toBe(0);
  });

  it('texto não conta (tem campo próprio)', () => {
    expect(countActiveFilters({ ...FILTER_DEFAULTS, text: 'x' })).toBe(0);
  });

  it('conta correctamente múltiplos filtros', () => {
    const f: PlanFilterState = {
      ...FILTER_DEFAULTS,
      modelos: ['K1'],
      materialRisco: true,
      estado: 'planeado',
    };
    expect(countActiveFilters(f)).toBe(3);
  });
});
