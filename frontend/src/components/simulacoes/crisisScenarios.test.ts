/**
 * crisisScenarios — guarda do contrato dos deltas de crise (Q.56.A).
 *
 * A tab "Crise" criava um twin scenario, aplicava estes deltas e simulava.
 * Os 6 cenários mandavam `entity_type` que o backend Twin rejeita
 * (`mold`, `employee`, `material`…) → `apply-delta` devolvia 422 → o
 * fluxo de crise falhava sempre. Este teste fixa o contrato: cada delta
 * usa um `entity_type` suportado e um patch válido.
 */

import { describe, it, expect } from 'vitest';
import { CRISIS_SCENARIOS } from './crisisScenarios';

// Espelho de `SUPPORTED_DELTA_ENTITY_TYPES` em `src/twin/service.py`.
// O backend é uma whitelist fechada desde Q.54.I.
const SUPPORTED_ENTITY_TYPES = [
  'capacity_adjustment',
  'standard_time',
  'skills_training',
  'quality_improvement',
  'wip_policy',
  'scheduling_input',
] as const;

// Chave de percentagem [-100,100] obrigatória por tipo (espelho de
// `_PERCENTAGE_PATCH_KEYS`).
const PERCENTAGE_KEY: Record<string, string> = {
  capacity_adjustment: 'capacity_increase_pct',
  standard_time: 'reduction_pct',
  quality_improvement: 'error_reduction_pct',
};

describe('CRISIS_SCENARIOS — contrato dos deltas', () => {
  it('tem 6 cenários de crise', () => {
    expect(CRISIS_SCENARIOS).toHaveLength(6);
  });

  for (const scenario of CRISIS_SCENARIOS) {
    describe(`cenário "${scenario.id}"`, () => {
      it('tem pelo menos um delta', () => {
        expect(scenario.deltas.length).toBeGreaterThan(0);
      });

      for (const [i, delta] of scenario.deltas.entries()) {
        it(`delta ${i}: entity_type é suportado pelo backend Twin`, () => {
          expect(SUPPORTED_ENTITY_TYPES).toContain(delta.entity_type);
        });

        it(`delta ${i}: tem entity_key e description`, () => {
          expect(delta.entity_key.trim().length).toBeGreaterThan(0);
          expect(delta.description.trim().length).toBeGreaterThan(0);
        });

        it(`delta ${i}: a chave de percentagem está num intervalo válido`, () => {
          const pctKey = PERCENTAGE_KEY[delta.entity_type];
          if (!pctKey) return; // tipo sem chave de percentagem
          const value = delta.patch[pctKey];
          expect(typeof value).toBe('number');
          expect(Number.isFinite(value as number)).toBe(true);
          expect(value as number).toBeGreaterThanOrEqual(-100);
          expect(value as number).toBeLessThanOrEqual(100);
        });
      }
    });
  }
});
