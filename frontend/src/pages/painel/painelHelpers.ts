/**
 * painelHelpers — formatação pt-PT.
 *
 * Saneamento 2026-06-04: a página /painel nunca foi montada (sem rota). Todas as
 * funções que dependiam de `painelApi` (severityTone/Label, normalizeBottleneck,
 * etc.) eram órfãs e foram removidas com o `painelApi.ts`. Sobrevive só `fmtEuro`,
 * o único export vivo (usado por `producao/MoveBoatConfirm`).
 */

/** €xxx — euros inteiros pt-PT. */
export function fmtEuro(n: number): string {
  return `€${Math.round(n).toLocaleString('pt-PT')}`;
}
