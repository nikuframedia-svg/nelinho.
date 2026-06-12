/**
 * Q.173.AC — helpers de formatação para a MateriaisPage.
 * Funções puras, testáveis com vitest.
 */

import type { MaterialEmRisco } from '../../lib/api/supplyApi';

/** Tipo de sugestão → variante DarkBadge */
export type SugestaoVariant = 'danger' | 'warning' | 'info' | 'success' | 'neutral';

export function sugestaoVariant(
  tipo: MaterialEmRisco['sugestao'],
): SugestaoVariant {
  switch (tipo) {
    case 'compra':
      return 'danger';
    case 'producao_interna':
      // Q.174.F0.3 — a Fábrica já tem pedido interno aberto que cobre o
      // défice: ação é confirmar/acelerar produção, não comprar.
      return 'warning';
    case 'replaneamento':
      return 'info';
    case 'ok':
      return 'success';
    default:
      return 'neutral';
  }
}

export function sugestaoLabel(tipo: MaterialEmRisco['sugestao']): string {
  switch (tipo) {
    case 'compra':
      return 'Compra';
    case 'producao_interna':
      return 'Produção interna';
    case 'replaneamento':
      return 'Replaneamento';
    case 'ok':
      return 'OK';
    default:
      return tipo;
  }
}

export function minStockSourceLabel(source: string): string {
  switch (source) {
    case 'erp':
      return 'ERP';
    case 'manual':
      return 'Manual';
    case 'default':
      return 'Padrão';
    default:
      return source;
  }
}

export function minStockSourceVariant(
  source: string,
): 'info' | 'accent' | 'neutral' {
  switch (source) {
    case 'erp':
      return 'info';
    case 'manual':
      return 'accent';
    default:
      return 'neutral';
  }
}

/**
 * Formata a data de rutura prevista de forma legível.
 * Devolve null se a data for null/undefined.
 */
export function formatDataRutura(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString('pt-PT', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return iso;
  }
}

/**
 * Quantos dias até à data de rutura. Negativo = já passou.
 */
export function diasAteRutura(iso: string | null | undefined): number | null {
  if (!iso) return null;
  try {
    const diff = new Date(iso).getTime() - Date.now();
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  } catch {
    return null;
  }
}

/**
 * Urgência para ordenação: menor = mais urgente.
 * Rutura passada → 0; sem data → Infinity; futura → dias.
 */
export function urgenciaMaterial(m: MaterialEmRisco): number {
  const dias = diasAteRutura(m.data_rutura_prevista);
  if (dias === null) return Infinity;
  return dias < 0 ? 0 : dias;
}
