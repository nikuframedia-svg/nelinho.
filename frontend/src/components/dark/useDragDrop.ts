/**
 * useDragDrop — wrapper tipado sobre HTML5 drag-and-drop.
 *
 * O protótipo NELO arrasta dois tipos de payload entre painéis: `boat`
 * (mover barco entre fases / camiões) e `worker` (atribuir operador a
 * barco). Este hook serializa um payload tipado no `dataTransfer` e
 * devolve os handlers prontos para o lado de origem (`dragProps`) e o
 * lado de destino (`dropProps`), mais o estado `isOver`.
 *
 * Primitiva partilhada (>1 página: Fábrica, Planeamento, Expedição) —
 * vive em `components/dark/` para a Onda 1 não partilhar ficheiros.
 *
 * Sprint Q.52.B.
 */

import { useCallback, useState } from 'react';
import type { DragEvent } from 'react';

/** Tipos de payload arrastáveis no NELO. */
export type DragKind = 'boat' | 'worker';

export interface DragPayload<T> {
  kind: DragKind;
  data: T;
}

const MIME = 'application/x-nelo-dnd';

/**
 * Handlers para um elemento ARRASTÁVEL (origem).
 * Espalhar em `<div {...dragProps} draggable>`.
 */
export function useDraggable<T>(
  payload: DragPayload<T>,
  opts?: {
    onDragStart?: () => void;
    onDragEnd?: () => void;
  },
): {
  dragProps: {
    draggable: true;
    onDragStart: (e: DragEvent<HTMLElement>) => void;
    onDragEnd: (e: DragEvent<HTMLElement>) => void;
  };
  dragging: boolean;
} {
  const [dragging, setDragging] = useState(false);

  const onDragStart = useCallback(
    (e: DragEvent<HTMLElement>): void => {
      e.dataTransfer.setData(MIME, JSON.stringify(payload));
      e.dataTransfer.effectAllowed = 'move';
      setDragging(true);
      opts?.onDragStart?.();
    },
    [payload, opts],
  );

  const onDragEnd = useCallback((): void => {
    setDragging(false);
    opts?.onDragEnd?.();
  }, [opts]);

  return {
    dragProps: { draggable: true, onDragStart, onDragEnd },
    dragging,
  };
}

/**
 * Handlers para uma ZONA DE LARGADA (destino).
 * `accept` filtra que tipos de payload são aceites. `onDrop` recebe o
 * payload desserializado e tipado.
 */
export function useDropZone<T>(opts: {
  accept: DragKind | DragKind[];
  onDrop: (payload: DragPayload<T>) => void;
}): {
  dropProps: {
    onDragOver: (e: DragEvent<HTMLElement>) => void;
    onDragEnter: (e: DragEvent<HTMLElement>) => void;
    onDragLeave: (e: DragEvent<HTMLElement>) => void;
    onDrop: (e: DragEvent<HTMLElement>) => void;
  };
  isOver: boolean;
} {
  const [isOver, setIsOver] = useState(false);
  const accepted = Array.isArray(opts.accept) ? opts.accept : [opts.accept];

  const parse = (e: DragEvent<HTMLElement>): DragPayload<T> | null => {
    const raw = e.dataTransfer.getData(MIME);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as DragPayload<T>;
      return accepted.includes(parsed.kind) ? parsed : null;
    } catch {
      return null;
    }
  };

  const onDragOver = useCallback((e: DragEvent<HTMLElement>): void => {
    // Necessário para que onDrop dispare.
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const onDragEnter = useCallback((e: DragEvent<HTMLElement>): void => {
    e.preventDefault();
    setIsOver(true);
  }, []);

  const onDragLeave = useCallback((e: DragEvent<HTMLElement>): void => {
    // Só desliga quando sai do contentor (não dos filhos).
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
      setIsOver(false);
    }
  }, []);

  const onDrop = useCallback(
    (e: DragEvent<HTMLElement>): void => {
      e.preventDefault();
      setIsOver(false);
      const payload = parse(e);
      if (payload) opts.onDrop(payload);
    },
    // parse depende de `accepted` (estável por render) e opts.onDrop.
    [opts],
  );

  return {
    dropProps: { onDragOver, onDragEnter, onDragLeave, onDrop },
    isOver,
  };
}
