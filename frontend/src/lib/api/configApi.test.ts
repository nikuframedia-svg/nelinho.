/**
 * Q.173.O — configApi shape + parsePhaseIds helper.
 *
 * configKeys: pina o shape para garantir que invalidateQueries({ queryKey: configKeys.category('planning') })
 * apanha todos os hits da categoria.
 *
 * parsePhaseIds: lógica de parsing do repair.phase_ids (JSON array ou CSV).
 */
import { describe, expect, it } from 'vitest';
import { parsePhaseIds, serializePhaseIds } from './configApi';
import { configKeys, phaseGapsKeys } from './keys';

// ─── configKeys ───────────────────────────────────────────────────────────────

describe('configKeys', () => {
  it('all é a raiz', () => {
    expect(configKeys.all).toEqual(['config']);
  });

  it('category(planning) começa com all', () => {
    const k = configKeys.category('planning');
    expect(k[0]).toBe('config');
    expect(k[1]).toBe('planning');
  });

  it('category(transporte) é distinto de planning', () => {
    expect(configKeys.category('transporte')).not.toEqual(configKeys.category('planning'));
  });
});

// ─── phaseGapsKeys ────────────────────────────────────────────────────────────

describe('phaseGapsKeys', () => {
  it('all é a raiz', () => {
    expect(phaseGapsKeys.all).toEqual(['phase-gaps']);
  });

  it('list() começa com all', () => {
    const k = phaseGapsKeys.list();
    expect(k[0]).toBe('phase-gaps');
    expect(k[1]).toBe('list');
  });
});

// ─── parsePhaseIds ────────────────────────────────────────────────────────────

describe('parsePhaseIds', () => {
  it('JSON array de inteiros', () => {
    expect(parsePhaseIds('[14, 76, 77]')).toEqual([14, 76, 77]);
  });

  it('CSV separado por vírgula', () => {
    expect(parsePhaseIds('14, 76, 77')).toEqual([14, 76, 77]);
  });

  it('CSV sem espaços', () => {
    expect(parsePhaseIds('14,76,77')).toEqual([14, 76, 77]);
  });

  it('string vazia devolve []', () => {
    expect(parsePhaseIds('')).toEqual([]);
  });

  it('só espaços devolve []', () => {
    expect(parsePhaseIds('   ')).toEqual([]);
  });

  it('texto inválido devolve []', () => {
    expect(parsePhaseIds('abc, xyz')).toEqual([]);
  });

  it('JSON inválido com letras devolve []', () => {
    expect(parsePhaseIds('[14, abc]')).toEqual([]);
  });

  it('número único', () => {
    expect(parsePhaseIds('14')).toEqual([14]);
  });
});

// ─── serializePhaseIds ────────────────────────────────────────────────────────

describe('serializePhaseIds', () => {
  it('devolve o mesmo array', () => {
    expect(serializePhaseIds([14, 76, 77])).toEqual([14, 76, 77]);
  });

  it('array vazio devolve []', () => {
    expect(serializePhaseIds([])).toEqual([]);
  });
});
