/**
 * Umwelt context — Onda 12 (L). 3 papéis: gestor / operador / ceo.
 *
 * Persistência via localStorage (key: 'umwelt'). Sem JWT/RBAC backend
 * ainda — a flag aqui é só visual gate para esconder write actions
 * em vista CEO (read-only). Quando JWT/role chegar (Sprint K full),
 * trocar persistência localStorage por claim do token.
 */

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export type Umwelt = 'gestor' | 'operador' | 'ceo';
const STORAGE_KEY = 'umwelt';

// Q.133.B.2 — o switcher de Umwelt tem de mudar o role EFECTIVO. O client.ts
// envia `X-User-Role` a partir de localStorage('user_role'); sem isto, trocar
// para CEO/Operador não mudava nada (header ficava sempre 'admin' no dev) e o
// RBAC era "teatro". Mapeia o papel da UI para o enum `Role` do backend.
// (Só dev — em produção vale o JWT; os headers legacy são ignorados.)
const UMWELT_TO_ROLE: Record<Umwelt, string> = {
  gestor: 'manager_operations',
  operador: 'operator',
  ceo: 'ceo',
};

interface UmweltCtxValue {
  umwelt: Umwelt;
  setUmwelt: (u: Umwelt) => void;
  isReadOnly: boolean;
}

const UmweltCtx = createContext<UmweltCtxValue | null>(null);

function readPersisted(): Umwelt {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === 'gestor' || v === 'operador' || v === 'ceo') return v;
  } catch { /* ignore */ }
  return 'gestor';
}

export function UmweltProvider({ children }: { children: ReactNode }) {
  const [umwelt, setUmweltState] = useState<Umwelt>(() => readPersisted());

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, umwelt);
      // Q.133.B.2 — propaga o role efectivo para o header X-User-Role (client.ts).
      localStorage.setItem('user_role', UMWELT_TO_ROLE[umwelt]);
    } catch { /* ignore */ }
  }, [umwelt]);

  const value = useMemo<UmweltCtxValue>(() => ({
    umwelt,
    setUmwelt: setUmweltState,
    isReadOnly: umwelt === 'ceo',
  }), [umwelt]);

  return <UmweltCtx.Provider value={value}>{children}</UmweltCtx.Provider>;
}

export function useUmwelt(): UmweltCtxValue {
  const ctx = useContext(UmweltCtx);
  if (!ctx) {
    return { umwelt: 'gestor', setUmwelt: () => {}, isReadOnly: false };
  }
  return ctx;
}
