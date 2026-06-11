/**
 * configApi — Q.173.O
 *
 * Wraps GET /v1/config/{category} e POST /v1/config/{category}/{key}.
 * Categorias suportadas: planning, transporte, alertas.
 *
 * NOTA: o binding anterior foi removido em Q.172.E (platformApi.ts:252-255)
 * por não ter consumidores. Este nasce JÁ com a PlaneadorTab como consumidor.
 */

import { request } from './client';

// ─── tipos ────────────────────────────────────────────────────────────────────

/** Mapa chave→valor da categoria (conteúdo de `values` na resposta). */
export type ConfigCategory = Record<string, string | number | boolean | null | unknown[]>;

/** Envelope real do GET /v1/config/{category} (CategoryValuesOut). */
interface CategoryValuesOut {
  category: string;
  values: ConfigCategory;
}

export type ConfigDataType = 'string' | 'bool' | 'int' | 'float' | 'json';

export interface SetKeyPayload {
  value: string | number | boolean | unknown[];
  data_type: ConfigDataType;
}

// ─── helpers ─────────────────────────────────────────────────────────────────

/**
 * Tenta fazer parse de repair.phase_ids de string para array de inteiros.
 * Aceita: "[14,76,77]" (JSON) ou "14,76,77" (CSV).
 * Devolve [] se o input for inválido.
 */
export function parsePhaseIds(raw: string): number[] {
  const trimmed = raw.trim();
  if (!trimmed) return [];
  // Tenta JSON primeiro
  if (trimmed.startsWith('[')) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed) && parsed.every((v) => typeof v === 'number')) {
        return parsed as number[];
      }
    } catch {
      // fallthrough para CSV
    }
  }
  // CSV: "14, 76, 77"
  const parts = trimmed.split(',').map((s) => s.trim()).filter(Boolean);
  const nums = parts.map(Number);
  if (nums.some(isNaN)) return [];
  return nums;
}

/**
 * Serializa array de inteiros para o formato que o backend aceita (JSON array).
 */
export function serializePhaseIds(ids: number[]): unknown[] {
  return ids;
}

// ─── api ──────────────────────────────────────────────────────────────────────

export const configApi = {
  /**
   * GET /v1/config/{category}
   * O backend devolve `{category, values: {key: value}}` (CategoryValuesOut)
   * — desembrulha `values` para o consumidor receber o mapa plano.
   * (Q.173.O bugfix: sem o unwrap, a PlaneadorTab mostrava defaults e um
   * "Guardar" cego teria ESCRITO por cima da config real do tenant.)
   */
  getCategory: async (category: string): Promise<ConfigCategory> => {
    const out = await request<CategoryValuesOut>(
      `/v1/config/${encodeURIComponent(category)}`,
    );
    return out?.values ?? {};
  },

  /**
   * POST /v1/config/{category}/{key}
   * Grava uma chave. RBAC: CONFIG_WRITE (em dev o middleware está off).
   */
  setKey: (category: string, key: string, payload: SetKeyPayload) =>
    request<{ key: string; value: unknown; data_type: string }>(
      `/v1/config/${encodeURIComponent(category)}/${encodeURIComponent(key)}`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
};
