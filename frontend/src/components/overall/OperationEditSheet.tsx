/**
 * OperationEditSheet — editor de UMA operação do plano (Q.147.C).
 *
 * Resolve "para cada operação escolher a pessoa, pôr numa fase diferente, mudar
 * a data" sem depender da densidade da grelha. Só ops de PLANO (os actuals do
 * passado são read-only). Guardar → reorder (valida axiomas Spelke, cria DRAFT).
 */

import { useState } from 'react';
import { Sheet } from '../dark/Sheet';
import { DarkButton } from '../dark/DarkButton';
import type { ScheduledOp } from './types';

export interface OperatorOption {
  code: string;
  name: string;
}
export interface PhaseOption {
  id: string;
  name: string;
}

const fieldStyle: React.CSSProperties = {
  width: '100%',
  padding: '7px 10px',
  background: 'var(--bg-3)',
  color: 'var(--fg-0)',
  border: '1px solid var(--bd-2)',
  borderRadius: 6,
  fontSize: 13,
  outline: 'none',
  colorScheme: 'dark',
};

function Label({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="text-[10px] uppercase tracking-wide font-semibold mb-1"
      style={{ color: 'var(--fg-3)' }}
    >
      {children}
    </div>
  );
}

export function OperationEditSheet({
  op,
  operators,
  phases,
  isPending,
  onSave,
  onClose,
}: {
  op: ScheduledOp;
  operators: OperatorOption[];
  phases: PhaseOption[];
  isPending: boolean;
  onSave: (v: { phaseId: string; operatorId: string; date: string }) => void;
  onClose: () => void;
}) {
  const [phaseId, setPhaseId] = useState(op.phase_id);
  const [operatorId, setOperatorId] = useState(op.operator_id ?? '');
  const [date, setDate] = useState((op.start ?? '').slice(0, 10));

  const canSave = date.length === 10 && !isPending;

  // Q.154.B — prefere o nome do barco (op.cliente); o código fica entre parêntesis.
  const boatLabel = op.cliente
    ? `${op.cliente}${op.order_id ? ` (#${op.order_id})` : ''}`
    : op.order_id
      ? `Barco #${op.order_id}`
      : op.id;

  return (
    <Sheet
      open
      onClose={onClose}
      title="Editar operação"
      subtitle={`${boatLabel} · fase atual ${op.phase_name}${op.operator_name ? ` · ${op.operator_name}` : ''}`}
      width={440}
      footer={
        <>
          <DarkButton variant="secondary" size="sm" onClick={onClose}>
            Cancelar
          </DarkButton>
          <DarkButton
            size="sm"
            onClick={() => onSave({ phaseId, operatorId, date })}
            disabled={!canSave}
          >
            {isPending ? 'A guardar…' : 'Guardar'}
          </DarkButton>
        </>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div>
          <Label>Operador</Label>
          <select value={operatorId} onChange={(e) => setOperatorId(e.target.value)} style={fieldStyle}>
            <option value="">— sem operador —</option>
            {operators.map((o) => (
              <option key={o.code} value={o.code}>
                {o.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label>Fase</Label>
          <select value={phaseId} onChange={(e) => setPhaseId(e.target.value)} style={fieldStyle}>
            {phases.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <Label>Data</Label>
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} style={fieldStyle} />
        </div>

        <p className="text-[10px] leading-relaxed" style={{ color: 'var(--fg-3)' }}>
          Guardar cria um rascunho do plano e valida os axiomas Spelke — precisa de aprovação humana
          (Decisões) para ficar oficial.
        </p>
      </div>
    </Sheet>
  );
}
