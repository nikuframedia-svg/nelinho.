/**
 * fabricaScoring — testes da adequação operador ↔ fase (Q.55.A).
 *
 * O bug que estes testes fecham: `quality.score` vem do backend já em
 * [1,10], mas o scoring multiplicava por 10 → saturava no clamp → TODOS
 * os operadores mostravam "10.0/10". Aqui garantimos que a escala é
 * respeitada e que o ranking volta a discriminar.
 */

import { describe, it, expect } from 'vitest';
import { scoreFor, fitTone } from './fabricaScoring';
import type { WorkerProfile } from './fabricaScoring';
import type { QualityScoreResult, SkillMatrixResult } from '../../lib/api';

function quality(
  score: number,
  method: QualityScoreResult['method'] = 'laplace_smoothed',
): QualityScoreResult {
  // `defect_rate` 0.08 é neutro de propósito: fica entre o limiar de
  // bónus (<0.05) e o de penalização (>0.12), por isso o `fit` reflecte
  // só a base do `score` — é o que estes testes querem isolar.
  return {
    employee_id: 'e1',
    score,
    defects: 3,
    operations: 40,
    defect_rate: 0.08,
    method,
  };
}

function skills(rows: SkillMatrixResult['phases']): SkillMatrixResult {
  return { employee_id: 'e1', phases: rows, total: rows.length };
}

describe('scoreFor — escala do quality-score', () => {
  it('um quality-score 9.0 sem matriz de skills dá fit ≈ 9.0, não 10', () => {
    const worker: WorkerProfile = { id: 'e1', name: 'Ana', quality: quality(9.0) };

    const result = scoreFor(worker, 'Laminagem');

    // Sem `skills` não há penalização de fase; o fit é a base = 9.0.
    expect(result.fit).toBeCloseTo(9.0, 5);
    expect(result.fit).toBeLessThan(10);
  });

  it('um quality-score 4.0 fica claramente abaixo de um 9.0', () => {
    const fraco: WorkerProfile = { id: 'e1', name: 'Beto', quality: quality(4.0) };
    const forte: WorkerProfile = { id: 'e2', name: 'Carla', quality: quality(9.0) };

    const fitFraco = scoreFor(fraco, 'Laminagem').fit;
    const fitForte = scoreFor(forte, 'Laminagem').fit;

    expect(fitFraco).toBeCloseTo(4.0, 5);
    expect(fitForte - fitFraco).toBeGreaterThan(4);
  });

  it('dois operadores com qualidade diferente NÃO empatam (regressão do 10.0/10)', () => {
    const a = scoreFor({ id: 'a', name: 'A', quality: quality(8.7) }, 'Cura').fit;
    const b = scoreFor({ id: 'b', name: 'B', quality: quality(6.2) }, 'Cura').fit;

    expect(a).not.toBe(b);
  });
});

describe('scoreFor — match de fase via skill-matrix', () => {
  it('especialista na fase sobe acima de quem não tem a skill', () => {
    const apto: WorkerProfile = {
      id: 'e1',
      name: 'Apto',
      quality: quality(7.0),
      skills: skills([
        {
          phase_id: 'lam',
          phase_name: 'Laminagem',
          can_do: true,
          nivel: 3,
          ops_count: 80,
          last_used_at: null,
        },
      ]),
    };
    const semSkill: WorkerProfile = {
      id: 'e2',
      name: 'SemSkill',
      quality: quality(7.0),
      skills: skills([]),
    };

    const fitApto = scoreFor(apto, 'Laminagem').fit;
    const fitSem = scoreFor(semSkill, 'Laminagem').fit;

    expect(fitApto).toBeGreaterThan(fitSem);
  });

  it('sem skill na fase aplica a penalização (-2.2) e a razão honesta', () => {
    const worker: WorkerProfile = {
      id: 'e1',
      name: 'Dora',
      quality: quality(8.0),
      skills: skills([]),
    };

    const result = scoreFor(worker, 'Pintura Acabamento');

    expect(result.fit).toBeCloseTo(8.0 - 2.2, 5);
    expect(result.reasons.some((r) => r.text.includes('Sem experiência'))).toBe(
      true,
    );
  });
});

describe('scoreFor — sem histórico', () => {
  it('quality default_no_history mantém razão honesta e base alta sem inventar', () => {
    const worker: WorkerProfile = {
      id: 'e1',
      name: 'Novo',
      quality: quality(9.0, 'default_no_history'),
    };

    const result = scoreFor(worker, 'Laminagem');

    expect(result.reasons.some((r) => r.text.includes('Sem histórico'))).toBe(
      true,
    );
    expect(result.fit).toBeLessThanOrEqual(10);
  });

  it('sem quality-score nenhum cai na base neutra 5.0', () => {
    const worker: WorkerProfile = { id: 'e1', name: 'Vazio' };

    expect(scoreFor(worker, null).fit).toBe(5);
  });
});

describe('fitTone', () => {
  it('mapeia o número para o tom certo', () => {
    expect(fitTone(8)).toBe('green');
    expect(fitTone(6)).toBe('yellow');
    expect(fitTone(3)).toBe('red');
  });
});
