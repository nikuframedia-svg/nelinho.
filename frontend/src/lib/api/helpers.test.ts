/**
 * Testes para o helper unwrap (Q.130).
 */
import { describe, expect, it } from 'vitest';
import { unwrap } from './helpers';

describe('unwrap', () => {
  it('array nu → devolve-o', () => {
    expect(unwrap([1, 2, 3])).toEqual([1, 2, 3]);
  });

  it('array vazio → []', () => {
    expect(unwrap([])).toEqual([]);
  });

  it('{ items } → devolve items', () => {
    expect(unwrap({ items: ['a', 'b'] })).toEqual(['a', 'b']);
  });

  it('{ decisions } → devolve decisions', () => {
    expect(unwrap({ decisions: [{ id: 1 }] })).toEqual([{ id: 1 }]);
  });

  it('null → []', () => {
    expect(unwrap(null)).toEqual([]);
  });

  it('undefined → []', () => {
    expect(unwrap(undefined)).toEqual([]);
  });

  it('objecto sem items nem decisions → []', () => {
    expect(unwrap({} as unknown as { items?: string[] })).toEqual([]);
  });
});
