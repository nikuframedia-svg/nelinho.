/** Utilitários de formatação PT-PT. */

/** €xxx — euros inteiros pt-PT (mantém sinal para deltas). */
export function fmtEuro(n: number): string {
  return `€${Math.round(n).toLocaleString('pt-PT')}`;
}
