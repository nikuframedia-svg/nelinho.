/**
 * Q.164.D — ordenação cronológica das ops dentro de uma célula (lane × slot).
 *
 * As vistas Por Barco / Por Pessoa agrupam ops por (lane, dia) mas empurravam-nas
 * por ordem do array (arbitrária) → dentro do mesmo dia uma fase podia aparecer
 * fora de sequência. O decoder força precedência, por isso o `start` (timestamp)
 * já reflecte a ordem REAL das fases; ordenar por `start` repõe a sequência.
 * Desempate por `phase_id` numérico (a "Por Fase" usa FP_SEQUENCIA do catálogo;
 * aqui o tempo é a verdade e o id só desempata starts idênticos, raros).
 */
import type { ScheduledOp } from '../types';

function phaseNum(phaseId: string): number {
  const n = parseInt(phaseId, 10);
  return Number.isNaN(n) ? Number.MAX_SAFE_INTEGER : n;
}

/** Ordena as ops in-place por start asc, depois phase_id numérico. Devolve a lista. */
export function sortOpsChrono(ops: ScheduledOp[]): ScheduledOp[] {
  ops.sort(
    (a, b) =>
      (a.start ?? '').localeCompare(b.start ?? '') ||
      phaseNum(a.phase_id) - phaseNum(b.phase_id),
  );
  return ops;
}
