/**
 * useHonestEmptyState — detecta respostas PARTIAL / degradadas (Q.52.C)
 * =====================================================================
 *
 * Vários endpoints do backend degradam *com honestidade* quando lhes
 * falta o ERP ou os sensores: em vez de inventarem dados, devolvem um
 * marcador no payload. As páginas têm de mostrar um empty state
 * explícito com a razão — NUNCA um placeholder (invariante ZERO MOCKS).
 *
 * Marcadores conhecidos (auditoria de contratos Q.52):
 *   - `erp_available: false`        — falta a ligação ao ERP MAR-KAYAKS
 *   - `dimension_available: false`  — a dimensão pedida (ex: agente) não
 *                                     tem dados no ERP
 *   - `status: "sem_execucao_real"` — não há execução real registada
 *   - `status: "sem_dados_sensor"`  — não há leituras de sensor
 *
 * Uso:
 *
 *     const margin = useQuery({ ... });
 *     const honest = useHonestEmptyState(margin.data);
 *     if (honest.degraded) {
 *       return <EmptyState title="Sem dados" hint={honest.reason} />;
 *     }
 *
 * O hook é puro (só `useMemo`) — não faz pedidos. Aceita `undefined`
 * (query ainda a carregar) e devolve `degraded: false` nesse caso.
 */

import { useMemo } from 'react';

export interface HonestEmptyState {
  /** True quando a resposta é PARTIAL/degradada e a página deve mostrar
   *  um empty state honesto em vez do conteúdo. */
  degraded: boolean;
  /** Razão legível (PT-PT) para mostrar ao utilizador. Vazia se não degradado. */
  reason: string;
  /** Marcador exacto que disparou a deteção — útil para logs/testes. */
  marker:
    | 'erp_indisponivel'
    | 'dimensao_indisponivel'
    | 'sem_execucao_real'
    | 'sem_dados_sensor'
    | null;
}

const NOT_DEGRADED: HonestEmptyState = {
  degraded: false,
  reason: '',
  marker: null,
};

/** Razões em PT-PT por marcador — uma só fonte de verdade. */
const REASONS: Record<NonNullable<HonestEmptyState['marker']>, string> = {
  erp_indisponivel:
    'O ERP MAR-KAYAKS não está acessível. Os dados aparecem assim que a ligação for restabelecida.',
  dimensao_indisponivel:
    'Esta dimensão não tem dados no ERP. Confirma se a fonte foi sincronizada.',
  sem_execucao_real:
    'Ainda não há execução real registada para este período.',
  sem_dados_sensor:
    'Não há leituras de sensor para mostrar. Verifica se os sensores estão a reportar.',
};

/**
 * Inspeciona uma resposta da API e classifica se está degradada.
 *
 * Aceita um objecto qualquer (ou `undefined`). Olha tanto para a raiz
 * como para um nível de aninhamento (`data`, `meta`) porque os
 * envelopes do backend não são uniformes.
 */
export function detectHonestEmptyState(response: unknown): HonestEmptyState {
  if (response === null || typeof response !== 'object') {
    return NOT_DEGRADED;
  }

  // Procura o marcador na raiz e em `data`/`meta` aninhados — os
  // envelopes da API não são uniformes (uns expõem na raiz, outros
  // metem o payload real dentro de `data`).
  const candidates: Record<string, unknown>[] = [
    response as Record<string, unknown>,
  ];
  for (const key of ['data', 'meta'] as const) {
    const nested = (response as Record<string, unknown>)[key];
    if (nested !== null && typeof nested === 'object') {
      candidates.push(nested as Record<string, unknown>);
    }
  }

  for (const obj of candidates) {
    if (obj.erp_available === false) {
      return {
        degraded: true,
        reason: REASONS.erp_indisponivel,
        marker: 'erp_indisponivel',
      };
    }
    if (obj.dimension_available === false) {
      return {
        degraded: true,
        reason: REASONS.dimensao_indisponivel,
        marker: 'dimensao_indisponivel',
      };
    }
    if (obj.status === 'sem_execucao_real') {
      return {
        degraded: true,
        reason: REASONS.sem_execucao_real,
        marker: 'sem_execucao_real',
      };
    }
    if (obj.status === 'sem_dados_sensor') {
      return {
        degraded: true,
        reason: REASONS.sem_dados_sensor,
        marker: 'sem_dados_sensor',
      };
    }
  }

  return NOT_DEGRADED;
}

/**
 * Hook React — memoiza `detectHonestEmptyState` pela referência da
 * resposta. Recalcula só quando a resposta muda.
 */
export function useHonestEmptyState(response: unknown): HonestEmptyState {
  return useMemo(() => detectHonestEmptyState(response), [response]);
}

export default useHonestEmptyState;
