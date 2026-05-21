// useTabRouting (Q.60.H) — sincroniza a tab activa com o `?tab=` do URL.
//
// Extrai o trio mecânico (TAB_IDS + type guard + useSearchParams) que cada
// página-mãe com tabs hoje reescreve à mão (QualidadePage, ConfiguracaoPage,
// RelatoriosPage...). Centralizá-lo aqui é o que torna a decomposição da
// Fase 3 barata e consistente — a página fica só com layout + tabs.
import { useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';

interface TabRouting<T extends string> {
  /** Tab activa — sempre um id válido (cai no `fallback` se o URL mentir). */
  activeTab: T;
  /** Muda a tab activa e escreve o `?tab=` (replace — não polui o histórico). */
  setTab: (id: T) => void;
}

export function useTabRouting<T extends string>(
  tabIds: readonly T[],
  fallback: T,
  param = 'tab',
): TabRouting<T> {
  const [searchParams, setSearchParams] = useSearchParams();

  const fromUrl = searchParams.get(param);
  const activeTab: T = (tabIds as readonly string[]).includes(fromUrl ?? '')
    ? (fromUrl as T)
    : fallback;

  const setTab = useCallback(
    (id: T) => {
      const next = new URLSearchParams(searchParams);
      next.set(param, id);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams, param],
  );

  return { activeTab, setTab };
}
