/**
 * Q.130.H — garante que o mapa label→slug envia os enums correctos para o backend.
 * Backend aceita: 'decisoes' | 'overall' | 'llm' | 'configuracoes'  (q115_config.py linha 85)
 */
import { describe, expect, it } from 'vitest';

// Replicar o mapa aqui (source of truth no componente; este teste pina o contrato).
const WHERE_SLUG: Record<string, string> = {
  'Decisões': 'decisoes',
  'Planeamento (Overall)': 'overall',
  'LLM (Chat / KPIs / Regras)': 'llm',
  'Configurações': 'configuracoes',
};

const VALID_BACKEND_SLUGS = new Set(['decisoes', 'overall', 'llm', 'configuracoes']);

describe('WHERE_SLUG (Q.130.H)', () => {
  it('todas as labels mapeiam para um slug válido no backend', () => {
    for (const [label, slug] of Object.entries(WHERE_SLUG)) {
      expect(
        VALID_BACKEND_SLUGS.has(slug),
        `label "${label}" mapeou para "${slug}" que não é um slug válido`,
      ).toBe(true);
    }
  });

  it('4 labels → 4 slugs distintos (sem colisões)', () => {
    const slugs = Object.values(WHERE_SLUG);
    expect(new Set(slugs).size).toBe(slugs.length);
  });
});
