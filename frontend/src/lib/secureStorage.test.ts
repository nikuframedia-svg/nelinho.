/**
 * Testes do wrapper encriptado de localStorage (Q.68.5.C).
 *
 * Cobertura:
 *   1. Round-trip setSecure + getSecure
 *   2. getSecure de key inexistente devolve null
 *   3. removeSecure apaga + invalida cache
 *   4. Fallback plaintext quando Web Crypto indisponível (mock)
 *   5. Plaintext legado é lido sem reencriptar
 *   6. getSecureCached devolve null antes de hidratação, valor depois
 *   7. primeSecureCache popula cache para vários keys
 *   8. Ciphertext em localStorage NÃO contém plaintext (XSS-readable check)
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  setSecure,
  getSecure,
  removeSecure,
  getSecureCached,
  primeSecureCache,
  __resetSecureStorageForTests,
} from './secureStorage';

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  __resetSecureStorageForTests();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('secureStorage (Q.68.5.C)', () => {
  it('round-trip: setSecure + getSecure devolvem o mesmo valor', async () => {
    await setSecure('auth_token', 'jwt-abc-123');
    const back = await getSecure('auth_token');
    expect(back).toBe('jwt-abc-123');
  });

  it('getSecure de key inexistente devolve null', async () => {
    const result = await getSecure('nao_existe');
    expect(result).toBeNull();
  });

  it('removeSecure apaga o valor e o cache', async () => {
    await setSecure('refresh_token', 'rt-xyz');
    expect(await getSecure('refresh_token')).toBe('rt-xyz');
    removeSecure('refresh_token');
    expect(await getSecure('refresh_token')).toBeNull();
    expect(getSecureCached('refresh_token')).toBeNull();
  });

  it('fallback plaintext quando Web Crypto indisponível (subtle stubbed)', async () => {
    // Mock: força crypto.subtle a parecer ausente. Não usamos
    // deleteProperty (que crashes em getters non-configurable) — em
    // vez disso espiamos hasWebCrypto via stub do importKey.
    const origImportKey = globalThis.crypto.subtle.importKey;
    // @ts-expect-error — apagar para simular ambiente sem subtle.
    globalThis.crypto.subtle.importKey = undefined;

    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      await setSecure('fallback_key', 'sensitive-value');
      // Plaintext fica directo em localStorage.
      expect(localStorage.getItem('fallback_key')).toBe('sensitive-value');
      // Warning foi emitido.
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('Web Crypto indisponível'),
        'fallback_key',
      );
      // getSecure devolve o plaintext.
      expect(await getSecure('fallback_key')).toBe('sensitive-value');
    } finally {
      // Restaura — assignment é válido em strict (subtle.importKey é writable).
      (globalThis.crypto.subtle as { importKey: typeof origImportKey }).importKey =
        origImportKey;
    }
  });

  it('plaintext legado é lido sem reencriptar (compat com sessões antigas)', async () => {
    // Simular valor antigo gravado antes desta migração — plaintext puro.
    localStorage.setItem('legacy_token', 'old-plaintext-value');
    const back = await getSecure('legacy_token');
    expect(back).toBe('old-plaintext-value');
    // Mantém-se em plaintext (não reencripta automaticamente).
    expect(localStorage.getItem('legacy_token')).toBe('old-plaintext-value');
  });

  it('getSecureCached devolve null antes de hidratação para ciphertext, valor após', async () => {
    await setSecure('cached_key', 'cached-value');
    // Limpa cache mas mantém ciphertext em localStorage.
    __resetSecureStorageForTests();
    // Sync read de ciphertext devolve null (precisa de async para decifrar).
    expect(getSecureCached('cached_key')).toBeNull();
    // Após hidratação async, cache funciona.
    await getSecure('cached_key');
    expect(getSecureCached('cached_key')).toBe('cached-value');
  });

  it('primeSecureCache popula cache para várias keys em paralelo', async () => {
    await setSecure('k1', 'v1');
    await setSecure('k2', 'v2');
    await setSecure('k3', 'v3');
    __resetSecureStorageForTests();

    await primeSecureCache(['k1', 'k2', 'k3']);
    expect(getSecureCached('k1')).toBe('v1');
    expect(getSecureCached('k2')).toBe('v2');
    expect(getSecureCached('k3')).toBe('v3');
  });

  it('ciphertext em localStorage NÃO contém o plaintext (XSS mitigation)', async () => {
    const secret = 'eyJhbGciOiJIUzI1NiJ9.super-secret-token';
    await setSecure('auth_token', secret);
    const stored = localStorage.getItem('auth_token');
    expect(stored).not.toBeNull();
    expect(stored).not.toContain(secret);
    // Formato esperado: v1:<iv>:<ciphertext>
    expect(stored).toMatch(/^v1:[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+$/);
  });
});
