/**
 * secureStorage — wrapper encriptado de localStorage (Q.68.5.C).
 * =================================================================
 *
 * Problema (auditoria D14): tokens de autenticação (`auth_token`,
 * `refresh_token`) e identificadores de conversa do copiloto (`copilot.*`)
 * ficavam em `localStorage` em plaintext. Um XSS leria tudo.
 *
 * Solução: AES-GCM 256 via Web Crypto API. PBKDF2 deriva a chave a
 * partir de um segredo de sessão gerado aleatoriamente no boot e
 * guardado em `sessionStorage` (vida = tab; fecha o tab → tudo
 * invalidado). IV de 12 bytes por valor, gravado junto do ciphertext.
 *
 * Formato persistido em localStorage:
 *
 *   v1:<base64-iv>:<base64-ciphertext>
 *
 * Prefixo `v1` permite migração futura (rotação de algoritmo/iteração).
 *
 * Fallback: se `crypto.subtle` não estiver disponível (browsers muito
 * antigos, ambientes de teste sem polyfill), grava em plaintext e
 * regista warning. ZERO mocks — a aplicação continua a funcionar.
 *
 * API:
 *   - setSecure(key, value)   — encripta + grava (async)
 *   - getSecure(key)          — lê + desencripta (async)
 *   - removeSecure(key)       — remove (sync)
 *   - getSecureCached(key)    — lê do cache in-memory (sync, null se
 *                               ainda não hidratado)
 *   - primeSecureCache(keys)  — hidrata o cache para a lista de keys
 *                               passadas (chamar 1× no boot)
 *
 * O cache in-memory existe porque a fetch layer (`lib/api/client.ts`)
 * lê tokens de forma síncrona em cada request. Migrar tudo para async
 * implicaria propagar `await` por toda a aplicação. O cache mantém a
 * API existente; a encriptação protege apenas o estado em repouso (que
 * é o que o XSS lê via `localStorage.getItem`).
 */

const KEY_VERSION = 'v1';
const PBKDF2_ITERATIONS = 100_000;
const SESSION_SECRET_KEY = '__prodplan_session_secret';
const SESSION_SALT_KEY = '__prodplan_session_salt';
const IV_LENGTH = 12; // GCM standard
const SALT_LENGTH = 16;

// Cache in-memory dos valores desencriptados — alimenta `getSecureCached`
// para callers que não podem ser async (ex: fetch headers).
const memoryCache = new Map<string, string | null>();

// Chave AES derivada (cache para evitar PBKDF2 a cada operação).
let derivedKeyPromise: Promise<CryptoKey> | null = null;

function hasWebCrypto(): boolean {
  return (
    typeof globalThis.crypto !== 'undefined' &&
    typeof globalThis.crypto.subtle !== 'undefined' &&
    typeof globalThis.crypto.subtle.importKey === 'function'
  );
}

function getOrCreateSessionSecret(): string {
  if (typeof sessionStorage === 'undefined') {
    // SSR ou ambiente sem sessionStorage — devolve string vazia, fallback
    // plaintext fica activo (warning emitido em set/get).
    return '';
  }
  let secret = sessionStorage.getItem(SESSION_SECRET_KEY);
  if (!secret) {
    // 32 bytes random → base64. Vida da sessão = vida do tab.
    const bytes = new Uint8Array(32);
    if (hasWebCrypto()) {
      globalThis.crypto.getRandomValues(bytes);
    } else {
      for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
    }
    secret = bytesToBase64(bytes);
    sessionStorage.setItem(SESSION_SECRET_KEY, secret);
  }
  return secret;
}

function getOrCreateSessionSalt(): Uint8Array {
  if (typeof sessionStorage === 'undefined') {
    return new Uint8Array(SALT_LENGTH);
  }
  const existing = sessionStorage.getItem(SESSION_SALT_KEY);
  if (existing) {
    return base64ToBytes(existing);
  }
  const salt = new Uint8Array(SALT_LENGTH);
  if (hasWebCrypto()) {
    globalThis.crypto.getRandomValues(salt);
  } else {
    for (let i = 0; i < salt.length; i++) salt[i] = Math.floor(Math.random() * 256);
  }
  sessionStorage.setItem(SESSION_SALT_KEY, bytesToBase64(salt));
  return salt;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function base64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

async function deriveKey(secret: string, salt: Uint8Array): Promise<CryptoKey> {
  const passwordKey = await globalThis.crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'PBKDF2' },
    false,
    ['deriveKey'],
  );
  return globalThis.crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      // Web Crypto aceita BufferSource; Uint8Array implementa-o. Cast
      // explícito para `BufferSource` evita ambiguidade do TS strict.
      salt: salt as BufferSource,
      iterations: PBKDF2_ITERATIONS,
      hash: 'SHA-256',
    },
    passwordKey,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

function getDerivedKey(): Promise<CryptoKey> {
  if (!derivedKeyPromise) {
    const secret = getOrCreateSessionSecret();
    const salt = getOrCreateSessionSalt();
    derivedKeyPromise = deriveKey(secret, salt);
  }
  return derivedKeyPromise;
}

/**
 * Encripta `value` e persiste em `localStorage` na chave `key`.
 *
 * Se Web Crypto não estiver disponível, grava plaintext + warning.
 * Actualiza o cache in-memory para que `getSecureCached(key)` veja
 * o valor imediatamente.
 */
export async function setSecure(key: string, value: string): Promise<void> {
  // Cache primeiro — sync callers vêem o novo valor imediatamente.
  memoryCache.set(key, value);

  if (typeof localStorage === 'undefined') return;

  if (!hasWebCrypto()) {
    // Fallback documentado: plaintext + warning. Não quebra a app.
    // eslint-disable-next-line no-console
    console.warn('[secureStorage] Web Crypto indisponível — guardando em plaintext:', key);
    localStorage.setItem(key, value);
    return;
  }

  try {
    const derivedKey = await getDerivedKey();
    const iv = new Uint8Array(IV_LENGTH);
    globalThis.crypto.getRandomValues(iv);
    const ciphertext = await globalThis.crypto.subtle.encrypt(
      { name: 'AES-GCM', iv: iv as BufferSource },
      derivedKey,
      new TextEncoder().encode(value),
    );
    const payload = `${KEY_VERSION}:${bytesToBase64(iv)}:${bytesToBase64(new Uint8Array(ciphertext))}`;
    localStorage.setItem(key, payload);
  } catch (err) {
    // Encriptação falhou — log + fallback plaintext (melhor app a
    // funcionar que app partida).
    // eslint-disable-next-line no-console
    console.warn('[secureStorage] encrypt falhou, fallback plaintext:', key, err);
    localStorage.setItem(key, value);
  }
}

/**
 * Lê + desencripta a chave `key`. Devolve `null` se não existir ou
 * se a desencriptação falhar (ex: segredo de sessão diferente após
 * reabrir tab — o token expirou, comportamento esperado).
 *
 * Actualiza o cache in-memory.
 */
export async function getSecure(key: string): Promise<string | null> {
  if (typeof localStorage === 'undefined') return null;

  const raw = localStorage.getItem(key);
  if (raw === null) {
    memoryCache.set(key, null);
    return null;
  }

  // Plaintext legado (gravado antes desta migração ou em fallback) —
  // devolve directamente para não partir sessões existentes. Não
  // re-encripta para evitar surpresas; próximo `setSecure` encripta.
  if (!raw.startsWith(`${KEY_VERSION}:`)) {
    memoryCache.set(key, raw);
    return raw;
  }

  if (!hasWebCrypto()) {
    // Web Crypto sumiu mas o valor está encriptado — nada a fazer.
    memoryCache.set(key, null);
    return null;
  }

  try {
    const parts = raw.split(':');
    if (parts.length !== 3) {
      memoryCache.set(key, null);
      return null;
    }
    const iv = base64ToBytes(parts[1]);
    const ciphertext = base64ToBytes(parts[2]);
    const derivedKey = await getDerivedKey();
    const plaintext = await globalThis.crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: iv as BufferSource },
      derivedKey,
      ciphertext as BufferSource,
    );
    const value = new TextDecoder().decode(plaintext);
    memoryCache.set(key, value);
    return value;
  } catch (err) {
    // Desencriptação falhou (segredo de sessão mudou, dados corrompidos).
    // Limpa para evitar voltar a tentar. Caller deve tratar null como
    // "sem token" (forçar relogin).
    // eslint-disable-next-line no-console
    console.warn('[secureStorage] decrypt falhou (sessão pode ter expirado):', key, err);
    localStorage.removeItem(key);
    memoryCache.set(key, null);
    return null;
  }
}

/**
 * Remove a chave de localStorage e do cache in-memory.
 */
export function removeSecure(key: string): void {
  memoryCache.set(key, null);
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem(key);
  }
}

/**
 * Lê o valor cacheado em memória — síncrono. Devolve `null` se
 * `primeSecureCache` ou `setSecure`/`getSecure` ainda não viu esta
 * chave. Usado pela fetch layer que não pode ser async.
 */
export function getSecureCached(key: string): string | null {
  const cached = memoryCache.get(key);
  if (cached !== undefined) return cached;
  // Nunca hidratado — tenta ler plaintext legado de forma síncrona como
  // best-effort. Se for ciphertext, devolve null (cache primará via async).
  if (typeof localStorage === 'undefined') return null;
  const raw = localStorage.getItem(key);
  if (raw === null) return null;
  if (raw.startsWith(`${KEY_VERSION}:`)) return null; // ciphertext — espera async.
  memoryCache.set(key, raw);
  return raw;
}

/**
 * Hidrata o cache in-memory para as keys passadas. Chamar 1× no boot
 * (ex: no `main.tsx` antes de montar o React) para que a fetch layer
 * tenha tokens disponíveis no primeiro render.
 */
export async function primeSecureCache(keys: string[]): Promise<void> {
  await Promise.all(keys.map((k) => getSecure(k)));
}

/**
 * Reset interno — apenas para testes. NÃO chamar em runtime.
 */
export function __resetSecureStorageForTests(): void {
  memoryCache.clear();
  derivedKeyPromise = null;
}
