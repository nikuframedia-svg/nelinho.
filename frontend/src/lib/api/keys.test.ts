/**
 * Q.61.27 — query-key factories.
 *
 * Pina o shape das keys para garantir que invalidacoes em cascata
 * funcionam (key[0] === 'decisions' apanha lists + details + pending).
 */
import { describe, expect, it } from 'vitest';
import {
  decisionKeys,
  auditLogKeys,
  causalKeys,
  ruleKeys,
} from './keys';

describe('decisionKeys hierarchy', () => {
  it('all is the root', () => {
    expect(decisionKeys.all).toEqual(['decisions']);
  });

  it('lists() extends all', () => {
    expect(decisionKeys.lists()).toEqual(['decisions', 'list']);
  });

  it('list(filters) extends lists()', () => {
    const k = decisionKeys.list({ status: 'PROPOSED' });
    expect(k[0]).toBe('decisions');
    expect(k[1]).toBe('list');
    expect(k[2]).toEqual({ status: 'PROPOSED' });
  });

  it('detail(id) extends details()', () => {
    const k = decisionKeys.detail('abc-123');
    expect(k).toEqual(['decisions', 'detail', 'abc-123']);
  });

  it('cascade invalidation: all key matches every variant', () => {
    // invalidateQueries({ queryKey: ['decisions'] }) deve apanhar todas
    // as keys que comecam por 'decisions' — confirmamos isso a nivel
    // estrutural (cada variant comeca por 'decisions').
    const variants = [
      decisionKeys.lists(),
      decisionKeys.list({}),
      decisionKeys.details(),
      decisionKeys.detail('x'),
      decisionKeys.pending(),
    ];
    for (const k of variants) {
      expect(k[0]).toBe('decisions');
    }
  });
});

describe('auditLogKeys', () => {
  it('list filters are part of key', () => {
    const k = auditLogKeys.list({ action: 'INSERT' });
    expect(k[0]).toBe('audit-logs');
    expect(k[2]).toEqual({ action: 'INSERT' });
  });
});

describe('causalKeys', () => {
  it('attribution embeds params', () => {
    const k = causalKeys.attribution('throughput_eur_day', 200);
    expect(k).toEqual([
      'causal',
      'attribution',
      'throughput_eur_day',
      200,
    ]);
  });
});

describe('ruleKeys', () => {
  it('list(status) uses "any" sentinel when undefined', () => {
    expect(ruleKeys.list()).toEqual(['yaml-policy-rules', 'list', 'any']);
    expect(ruleKeys.list('active')).toEqual([
      'yaml-policy-rules',
      'list',
      'active',
    ]);
  });
});
