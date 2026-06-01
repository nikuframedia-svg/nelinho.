import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { CircuitBreaker } from './circuit-breaker';

// Q.144.D — o breaker tranca a UI inteira quando abre; estes testes fixam o
// contrato de abertura/recuperação que sustenta a auto-cura por /health.

const fail = () => Promise.reject(new Error('boom'));
const ok = () => Promise.resolve('ok');

describe('CircuitBreaker (Q.144.D)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('abre após 5 falhas e rejeita de imediato (sem chamar fn)', async () => {
    const cb = new CircuitBreaker();
    for (let i = 0; i < 5; i++) {
      await expect(cb.call(fail)).rejects.toThrow('boom');
    }
    expect(cb.getState()).toBe('open');

    const spy = vi.fn(ok);
    await expect(cb.call(spy)).rejects.toThrow('Circuit breaker is open');
    expect(spy).not.toHaveBeenCalled(); // bloqueado no cliente
  });

  it('passa a half-open após o timeout (20s) e fecha em sucesso', async () => {
    const cb = new CircuitBreaker();
    for (let i = 0; i < 5; i++) await expect(cb.call(fail)).rejects.toThrow();
    expect(cb.getState()).toBe('open');

    // Antes do timeout: ainda aberto.
    vi.advanceTimersByTime(19_000);
    await expect(cb.call(ok)).rejects.toThrow('Circuit breaker is open');

    // Depois do timeout (default 20s): half-open → sucesso → fechado.
    vi.advanceTimersByTime(2_000);
    await expect(cb.call(ok)).resolves.toBe('ok');
    expect(cb.getState()).toBe('closed');
  });

  it('reset() fecha de imediato — base da auto-cura por /health', async () => {
    const cb = new CircuitBreaker();
    for (let i = 0; i < 5; i++) await expect(cb.call(fail)).rejects.toThrow();
    expect(cb.getState()).toBe('open');

    cb.reset();
    expect(cb.getState()).toBe('closed');
    await expect(cb.call(ok)).resolves.toBe('ok');
  });
});
