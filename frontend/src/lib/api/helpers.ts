/**
 * unwrap — normaliza respostas de API para array simples.
 *
 * Aceita:
 *   - array nu → devolve-o directamente
 *   - { items: T[] } → devolve items
 *   - { decisions: T[] } → devolve decisions
 *   - null / undefined → devolve []
 */
export function unwrap<T>(
  res: T[] | { items?: T[] } | { decisions?: T[] } | null | undefined,
): T[] {
  if (res == null) return [];
  if (Array.isArray(res)) return res;
  if ('items' in res && Array.isArray(res.items)) return res.items;
  if ('decisions' in res && Array.isArray((res as { decisions?: T[] }).decisions))
    return (res as { decisions: T[] }).decisions;
  return [];
}
