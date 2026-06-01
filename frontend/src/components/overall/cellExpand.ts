/**
 * Q.147.B — context para o drill-down de célula (heatmap → lista de ops).
 *
 * Evita threading de `onExpandCell` por OverallPage → 3 vistas → renderItem →
 * DropSlot. A OverallPage providencia; os DropSlots consomem.
 */
import { createContext, useContext } from 'react';
import type { ScheduledOp } from './types';

export type ExpandCellFn = (ops: ScheduledOp[]) => void;

const CellExpandContext = createContext<ExpandCellFn | null>(null);

export const CellExpandProvider = CellExpandContext.Provider;

export function useCellExpand(): ExpandCellFn | null {
  return useContext(CellExpandContext);
}
