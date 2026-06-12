/**
 * AbsencesSheet — gestão mínima de ausências de operadores (Q.174.F4).
 *
 * Decisão do dono: ERP ENT_MOV é a fonte (entra direto no CPO) + overrides
 * locais aqui (registar uma falta que o ERP ainda não tem). O CPO exclui o
 * operador no intervalo no PRÓXIMO replaneamento — a sheet diz isso às claras.
 */

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Trash2 } from 'lucide-react';
import { Sheet } from '../dark/Sheet';
import { DarkButton } from '../dark/DarkButton';
import { planKeys } from '../../lib/api/keys';
import { workerAbsencesApi } from '../../lib/api';
import { useToastContext } from '../ToastProvider';
import type { OperatorOption } from './OperationEditSheet';

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

export function AbsencesSheet({
  operators,
  onClose,
}: {
  operators: OperatorOption[];
  onClose: () => void;
}) {
  const toast = useToastContext();
  const queryClient = useQueryClient();
  const [employeeCode, setEmployeeCode] = useState('');
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');
  const [reason, setReason] = useState('');

  const nameByCode = new Map(operators.map((o) => [o.code, o.name]));

  const absencesQuery = useQuery({
    queryKey: planKeys.absences(),
    queryFn: () => workerAbsencesApi.list(),
    retry: false,
    refetchOnWindowFocus: false,
  });

  const createMutation = useMutation({
    mutationFn: workerAbsencesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: planKeys.absences() });
      setEmployeeCode('');
      setDateStart('');
      setDateEnd('');
      setReason('');
      toast.success('Ausência registada — entra no próximo replaneamento.');
    },
    onError: (err: unknown) => {
      const e = err as { message?: string };
      toast.error(`Falha ao registar: ${e.message ?? 'erro desconhecido'}`);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: workerAbsencesApi.remove,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: planKeys.absences() });
      toast.info('Ausência anulada — entra no próximo replaneamento.');
    },
    onError: (err: unknown) => {
      const e = err as { message?: string };
      toast.error(`Falha ao anular: ${e.message ?? 'erro desconhecido'}`);
    },
  });

  const canAdd =
    employeeCode !== '' &&
    dateStart.length === 10 &&
    dateEnd.length === 10 &&
    dateEnd >= dateStart &&
    !createMutation.isPending;

  const rows = absencesQuery.data ?? [];

  return (
    <Sheet
      open
      onClose={onClose}
      title="Ausências de operadores"
      subtitle="Faltas do ERP entram sozinhas no plano; aqui registas as que o ERP ainda não tem."
      width={460}
      footer={
        <DarkButton variant="secondary" size="sm" onClick={onClose}>
          Fechar
        </DarkButton>
      }
    >
      <div className="flex flex-col gap-3.5">
        <div>
          <Label>Operador</Label>
          <select
            value={employeeCode}
            onChange={(e) => setEmployeeCode(e.target.value)}
            style={fieldStyle}
          >
            <option value="">— escolher operador —</option>
            {operators.map((o) => (
              <option key={o.code} value={o.code}>
                {o.name}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label>De</Label>
            <input
              type="date"
              value={dateStart}
              onChange={(e) => setDateStart(e.target.value)}
              style={fieldStyle}
            />
          </div>
          <div>
            <Label>Até (inclusive)</Label>
            <input
              type="date"
              value={dateEnd}
              onChange={(e) => setDateEnd(e.target.value)}
              style={fieldStyle}
            />
          </div>
        </div>

        <div>
          <Label>Motivo (opcional)</Label>
          <input
            type="text"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="ex.: consulta médica"
            style={fieldStyle}
          />
        </div>

        <DarkButton
          size="sm"
          disabled={!canAdd}
          onClick={() =>
            createMutation.mutate({
              employee_code: employeeCode,
              date_start: dateStart,
              date_end: dateEnd,
              reason: reason || undefined,
            })
          }
        >
          {createMutation.isPending ? 'A registar…' : 'Registar ausência'}
        </DarkButton>

        <div>
          <Label>Registadas (futuras)</Label>
          {absencesQuery.isLoading && (
            <span className="text-xs" style={{ color: 'var(--fg-3)' }}>
              A carregar…
            </span>
          )}
          {absencesQuery.isError && (
            <span className="text-xs" style={{ color: 'var(--red)' }}>
              Não foi possível carregar as ausências.
            </span>
          )}
          {!absencesQuery.isLoading && !absencesQuery.isError && rows.length === 0 && (
            <span className="text-xs" style={{ color: 'var(--fg-3)' }}>
              Sem overrides locais — o plano usa só as faltas do ERP.
            </span>
          )}
          <div className="flex flex-col gap-1.5 mt-1 max-h-56 overflow-y-auto">
            {rows.map((a) => (
              <div
                key={a.id}
                className="flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs"
                style={{ background: 'var(--bg-4)', border: '1px solid var(--bd-2)' }}
              >
                <span className="font-medium truncate" style={{ color: 'var(--fg-1)' }}>
                  {nameByCode.get(a.employee_code) ?? a.employee_code}
                </span>
                <span className="font-mono tabular-nums" style={{ color: 'var(--fg-2)' }}>
                  {a.date_start === a.date_end
                    ? a.date_start
                    : `${a.date_start} → ${a.date_end}`}
                </span>
                {a.reason && (
                  <span className="truncate max-w-[120px]" style={{ color: 'var(--fg-3)' }} title={a.reason}>
                    {a.reason}
                  </span>
                )}
                <button
                  type="button"
                  className="ml-auto flex-shrink-0 opacity-70 hover:opacity-100 transition"
                  style={{ color: 'var(--red)', background: 'none', border: 'none', cursor: 'pointer' }}
                  onClick={() => deleteMutation.mutate(a.id)}
                  disabled={deleteMutation.isPending}
                  aria-label="Anular ausência"
                  title="Anular esta ausência"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        </div>

        <p className="text-[10px] leading-relaxed m-0" style={{ color: 'var(--fg-3)' }}>
          O CPO deixa de atribuir trabalho ao operador no intervalo no próximo
          replaneamento (axioma de disponibilidade). Cada registo fica no audit
          trail.
        </p>
      </div>
    </Sheet>
  );
}
