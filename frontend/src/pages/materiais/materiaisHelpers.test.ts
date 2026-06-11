/**
 * Q.173.AC — testes dos helpers da MateriaisPage.
 * Funções puras, sem I/O.
 */

import { describe, it, expect } from 'vitest';
import {
  sugestaoVariant,
  sugestaoLabel,
  minStockSourceLabel,
  minStockSourceVariant,
  formatDataRutura,
  diasAteRutura,
  urgenciaMaterial,
} from './materiaisHelpers';
import type { MaterialEmRisco } from '../../lib/api/supplyApi';

describe('sugestaoVariant', () => {
  it('compra → danger', () => {
    expect(sugestaoVariant('compra')).toBe('danger');
  });
  it('replaneamento → info', () => {
    expect(sugestaoVariant('replaneamento')).toBe('info');
  });
  it('ok → success', () => {
    expect(sugestaoVariant('ok')).toBe('success');
  });
  it('desconhecido → neutral', () => {
    expect(sugestaoVariant('outro')).toBe('neutral');
  });
});

describe('sugestaoLabel', () => {
  it('compra → "Compra"', () => {
    expect(sugestaoLabel('compra')).toBe('Compra');
  });
  it('replaneamento → "Replaneamento"', () => {
    expect(sugestaoLabel('replaneamento')).toBe('Replaneamento');
  });
  it('ok → "OK"', () => {
    expect(sugestaoLabel('ok')).toBe('OK');
  });
  it('desconhecido → passthrough', () => {
    expect(sugestaoLabel('xyz')).toBe('xyz');
  });
});

describe('minStockSourceLabel', () => {
  it('erp → "ERP"', () => expect(minStockSourceLabel('erp')).toBe('ERP'));
  it('manual → "Manual"', () => expect(minStockSourceLabel('manual')).toBe('Manual'));
  it('default → "Padrão"', () => expect(minStockSourceLabel('default')).toBe('Padrão'));
  it('outro → passthrough', () => expect(minStockSourceLabel('abc')).toBe('abc'));
});

describe('minStockSourceVariant', () => {
  it('erp → info', () => expect(minStockSourceVariant('erp')).toBe('info'));
  it('manual → accent', () => expect(minStockSourceVariant('manual')).toBe('accent'));
  it('default → neutral', () => expect(minStockSourceVariant('default')).toBe('neutral'));
});

describe('formatDataRutura', () => {
  it('null → null', () => {
    expect(formatDataRutura(null)).toBeNull();
  });
  it('undefined → null', () => {
    expect(formatDataRutura(undefined)).toBeNull();
  });
  it('ISO válido devolve string não vazia', () => {
    const resultado = formatDataRutura('2026-08-15');
    expect(typeof resultado).toBe('string');
    expect(resultado!.length).toBeGreaterThan(0);
  });
});

describe('diasAteRutura', () => {
  it('null → null', () => {
    expect(diasAteRutura(null)).toBeNull();
  });
  it('data futura devolve número positivo', () => {
    const futuro = new Date(Date.now() + 10 * 24 * 60 * 60 * 1000)
      .toISOString()
      .slice(0, 10);
    const dias = diasAteRutura(futuro);
    expect(dias).toBeGreaterThan(0);
  });
  it('data passada devolve número negativo ou zero', () => {
    const passado = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000)
      .toISOString()
      .slice(0, 10);
    const dias = diasAteRutura(passado);
    expect(dias).not.toBeNull();
    expect(dias!).toBeLessThanOrEqual(0);
  });
});

describe('urgenciaMaterial', () => {
  const base: MaterialEmRisco = {
    product_code: 'X',
    product_name: 'Material X',
    stock_atual: 10,
    stock_negativo_erp: false,
    min_stock: 5,
    min_stock_source: 'erp',
    data_rutura_prevista: null,
    defice: 0,
    ordens_afetadas: [],
    sugestao: 'ok',
    sugestao_detalhe: '',
    lead_time_days: 7,
    lead_time_source: 'erp',
    data_limite_encomenda: null,
    outros_armazens: [],
    consumo_mediano_por_barco: null,
  };

  it('sem data de rutura → Infinity (menor urgência)', () => {
    expect(urgenciaMaterial({ ...base, data_rutura_prevista: null })).toBe(Infinity);
  });

  it('rutura passada → 0 (máxima urgência)', () => {
    const passado = new Date(Date.now() - 5 * 24 * 60 * 60 * 1000)
      .toISOString();
    expect(urgenciaMaterial({ ...base, data_rutura_prevista: passado })).toBe(0);
  });

  it('rutura futura → número positivo', () => {
    const futuro = new Date(Date.now() + 20 * 24 * 60 * 60 * 1000)
      .toISOString();
    const u = urgenciaMaterial({ ...base, data_rutura_prevista: futuro });
    expect(u).toBeGreaterThan(0);
  });

  it('rutura mais próxima é mais urgente', () => {
    const cedo = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString();
    const tarde = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();
    const uCedo = urgenciaMaterial({ ...base, data_rutura_prevista: cedo });
    const uTarde = urgenciaMaterial({ ...base, data_rutura_prevista: tarde });
    expect(uCedo).toBeLessThan(uTarde);
  });
});
