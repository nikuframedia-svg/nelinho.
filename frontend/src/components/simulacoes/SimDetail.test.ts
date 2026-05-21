/**
 * SimDetail — testes de `buildComparisonRows` (Q.56.C).
 *
 * O backend Twin guarda o resultado como `{before, after, delta_summary,
 * mode}`. A função procurava `kpis`/`comparison` (a forma da RESPOSTA do
 * endpoint `/simulate`, não a guardada) → a tabela "Baseline vs simulação"
 * vinha sempre vazia. Estes testes fixam a leitura de `before`/`after`.
 */

import { describe, it, expect } from 'vitest';
import { buildComparisonRows } from './SimDetail';

const SIM_RESULT = {
  before: {
    wip_theoretical: {
      value: 164,
      unit: 'orders',
      status: 'OK',
      semantic_label: 'WIP teórico',
    },
    backlog_horas_theoretical: {
      value: 613.4,
      unit: 'hours',
      status: 'WARNING',
    },
    oee: { value: null, status: 'BLOCKED' },
    _metadata: { data_version: 'governance_tables' },
  },
  after: {
    wip_theoretical: {
      value: 164,
      unit: 'orders',
      status: 'OK',
      semantic_label: 'WIP teórico',
    },
    backlog_horas_theoretical: {
      value: 797.4,
      unit: 'hours',
      status: 'WARNING',
    },
    oee: { value: null, status: 'BLOCKED' },
    _metadata: { data_version: 'governance_tables' },
  },
  delta_summary: { backlog_horas_theoretical_change: 184.0 },
  mode: 'projecao_linear',
};

describe('buildComparisonRows (Q.56.C)', () => {
  it('lê before/after e produz uma linha por KPI (sem _metadata)', () => {
    const rows = buildComparisonRows(SIM_RESULT);

    // 3 KPIs reais; `_metadata` é ignorado.
    expect(rows).toHaveLength(3);
    expect(rows.map((r) => r.label)).not.toContain('_metadata');
  });

  it('emparelha baseline e simulado do mesmo KPI', () => {
    const rows = buildComparisonRows(SIM_RESULT);
    const backlog = rows.find((r) => r.label.includes('backlog'))!;

    expect(backlog.baseline).toContain('613');
    expect(backlog.simulated).toContain('797');
  });

  it('usa o semantic_label como rótulo quando existe', () => {
    const rows = buildComparisonRows(SIM_RESULT);
    expect(rows.some((r) => r.label === 'WIP teórico')).toBe(true);
  });

  it('um KPI sem valor mostra o estado honesto, não rebenta', () => {
    const rows = buildComparisonRows(SIM_RESULT);
    const oee = rows.find((r) => r.label === 'oee')!;

    expect(oee.baseline).toBe('BLOCKED');
    expect(oee.simulated).toBe('BLOCKED');
  });

  it('resultado nulo ou sem before/after → tabela vazia (empty-state)', () => {
    expect(buildComparisonRows(null)).toEqual([]);
    expect(buildComparisonRows(undefined)).toEqual([]);
    expect(buildComparisonRows({})).toEqual([]);
    expect(buildComparisonRows({ kpis: {}, comparison: {} })).toEqual([]);
  });
});
