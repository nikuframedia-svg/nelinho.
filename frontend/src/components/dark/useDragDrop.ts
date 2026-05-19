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

import { useCallback, useEffect, useRef, useState } from 'react';
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
 *
 * Q.54.K — robustez do estado `dragging`:
 *   1. O `dragend` do HTML5 nem sempre chega ao handler React: se a barra
 *      arrastada for re-renderizada/remontada durante o arrasto (ex.: o
 *      `onDrop` invalida queries → a lista de barras volta a montar), o nó
 *      DOM que começou o arrasto desaparece e o `dragend` perde-se → o
 *      estado `dragging` ficava preso a `true` para sempre, deixando a
 *      barra a 40% de opacidade e a BLOQUEAR o `onClick`. Resolvido com um
 *      listener global de `dragend`/`drop` na `window` que repõe sempre
 *      `dragging=false`, mesmo que o `dragend` local nunca dispare (drop
 *      fora de zona válida, ESC, remontagem).
 *   2. `wasDragging()` dá ao chamador uma forma fiável de distinguir um
 *      clique de um arrasto sem depender do estado `dragging` (que pode
 *      estar a meio de uma transição de render).
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
  /** `true` durante a janela curta a seguir a um arrasto — para o chamador
   * ignorar o `click` sintético que se segue ao `dragend`. */
  wasDragging: () => boolean;
} {
  const [dragging, setDragging] = useState(false);
  // Ref para handlers estáveis e para o `wasDragging()` ler sem re-render.
  const draggingRef = useRef(false);
  const dragEndedAtRef = useRef(0);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const stopDragging = useCallback((): void => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    dragEndedAtRef.current = Date.now();
    setDragging(false);
    optsRef.current?.onDragEnd?.();
  }, []);

  // Rede de segurança: o `dragend`/`drop` borbulha até à window mesmo que
  // o nó de origem tenha sido remontado. Garante que `dragging` nunca fica
  // preso a `true`.
  useEffect(() => {
    if (!dragging) return;
    const reset = (): void => stopDragging();
    window.addEventListener('dragend', reset, true);
    window.addEventListener('drop', reset, true);
    return () => {
      window.removeEventListener('dragend', reset, true);
      window.removeEventListener('drop', reset, true);
    };
  }, [dragging, stopDragging]);

  const onDragStart = useCallback(
    (e: DragEvent<HTMLElement>): void => {
      e.dataTransfer.setData(MIME, JSON.stringify(payload));
      e.dataTransfer.effectAllowed = 'move';
      draggingRef.current = true;
      setDragging(true);
      optsRef.current?.onDragStart?.();
    },
    [payload],
  );

  const onDragEnd = useCallback((): void => {
    stopDragging();
  }, [stopDragging]);

  // O `click` sintético dispara logo a seguir ao `dragend` na mesma barra.
  // Uma janela curta (250ms) distingue-o de um clique genuíno.
  const wasDragging = useCallback(
    (): boolean =>
      draggingRef.current || Date.now() - dragEndedAtRef.current < 250,
    [],
  );

  return {
    dragProps: { draggable: true, onDragStart, onDragEnd },
    dragging,
    wasDragging,
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
