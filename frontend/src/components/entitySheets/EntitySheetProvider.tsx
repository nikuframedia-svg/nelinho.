/**
 * Q.116.A — Context Provider para sheets contextuais de entidades.
 *
 * Estado vive na URL (?sheet=<kind>&id=<id>) — deep-linkable.
 * Tem de estar DENTRO do <BrowserRouter> para usar useSearchParams.
 */
import { createContext, useContext, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { EntityKind } from '../../lib/api/entityApi';

const VALID_KINDS: EntityKind[] = ['modelo', 'fase', 'cliente', 'encomenda'];

function isEntityKind(v: string | null): v is EntityKind {
  return v !== null && (VALID_KINDS as string[]).includes(v);
}

interface EntitySheetContextValue {
  current: { kind: EntityKind; id: string } | null;
  openSheet: (kind: EntityKind, id: string) => void;
  closeSheet: () => void;
}

const EntitySheetContext = createContext<EntitySheetContextValue | null>(null);

export function EntitySheetProvider({ children }: { children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams();

  const rawKind = searchParams.get('sheet');
  const rawId = searchParams.get('id');
  const current =
    isEntityKind(rawKind) && rawId
      ? { kind: rawKind, id: rawId }
      : null;

  function openSheet(kind: EntityKind, id: string) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set('sheet', kind);
        next.set('id', id);
        return next;
      },
      { replace: false }
    );
  }

  function closeSheet() {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete('sheet');
        next.delete('id');
        return next;
      },
      { replace: false }
    );
  }

  return (
    <EntitySheetContext.Provider value={{ current, openSheet, closeSheet }}>
      {children}
    </EntitySheetContext.Provider>
  );
}

export function useEntitySheet(): EntitySheetContextValue {
  const ctx = useContext(EntitySheetContext);
  if (!ctx) {
    throw new Error('useEntitySheet tem de ser usado dentro de <EntitySheetProvider>');
  }
  return ctx;
}
