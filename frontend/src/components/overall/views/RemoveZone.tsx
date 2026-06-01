/**
 * RemoveZone — Q.153.C2 — zona de remoção por drag no /overall.
 *
 * Arrastar uma operação para aqui = excluir/adiar o BARCO (order_id) do plano
 * automático, de forma reversível (backend Q.153.C1). Vive DENTRO de cada
 * <DndContext> (Por Barco / Por Fase). O ramo de remoção é tratado no
 * handleDragEnd da view (lê op.order_id e chama onExclude).
 *
 * O efeito aplica-se no PRÓXIMO replan (não no commit actual) — o toast da
 * página é honesto ("Replaneie para aplicar"); aqui não removemos nada da
 * grelha optimisticamente.
 */
import { memo, type ReactNode } from 'react';
import { useDroppable } from '@dnd-kit/core';
import { Trash2 } from 'lucide-react';

export const REMOVE_ZONE_ID = 'remove-zone';

export const RemoveZone = memo(function RemoveZone(): ReactNode {
  const { setNodeRef, isOver } = useDroppable({ id: REMOVE_ZONE_ID });
  return (
    <div
      ref={setNodeRef}
      className="flex items-center justify-center gap-2 mb-1.5 py-1.5 px-3 rounded-lg border-2 border-dashed text-xs font-medium transition select-none"
      style={
        isOver
          ? { borderColor: 'var(--red)', background: 'var(--red-bg, rgba(239,68,68,0.12))', color: 'var(--red, #f87171)' }
          : { borderColor: 'var(--bd-2)', background: 'var(--bg-4)', color: 'var(--fg-3)' }
      }
      aria-label="Largar aqui para excluir o barco do plano"
    >
      <Trash2 size={14} />
      {isOver ? 'Largar para excluir o barco do plano' : 'Arrastar um barco para aqui exclui-o do plano (reversível)'}
    </div>
  );
});
