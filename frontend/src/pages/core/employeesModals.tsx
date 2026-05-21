// EmployeesPage — modais Histórico/Qualidade/Comparar (Q.60.W).
import { useState } from 'react';
import { useQueries, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { DarkCard, DarkButton, DarkBadge, DarkIconButton } from '../../components/dark';
import { workforceEmployeesApi } from '../../lib/api';
import type { MutationError } from '../../lib/api-helpers';
import { type Employee } from './employeesTypes';

export const HISTORY_PAGE_SIZE = 25;

export function EmployeeHistoryModal({
  employee,
  onClose,
}: {
  employee: Employee;
  onClose: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const { data, isLoading, error } = useQuery({
    queryKey: ['workforce', 'history', employee.id, offset],
    queryFn: () =>
      workforceEmployeesApi.history(employee.id, {
        limit: HISTORY_PAGE_SIZE,
        offset,
      }),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <DarkCard className="w-[800px] max-w-[95vw] max-h-[85vh] overflow-auto p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-lg font-semibold text-white">{employee.name}</h3>
            <p className="text-xs text-slate-400">Histórico de operações</p>
          </div>
          <DarkIconButton icon={<X size={16} />} size="sm" variant="ghost" onClick={onClose} />
        </div>

        {isLoading && <p className="text-sm text-slate-400 py-4">A carregar…</p>}
        {error && (
          <p className="text-sm text-red-400 py-4">
            Falha: {(error as Error).message}
          </p>
        )}
        {data && data.operations.length === 0 && (
          <p className="text-sm text-slate-500 py-6 text-center">
            Sem operações registadas para este colaborador.
          </p>
        )}
        {data && data.operations.length > 0 && (
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-slate-400 border-b border-slate-700">
              <tr>
                <th className="py-2 pr-2">OF</th>
                <th className="py-2 pr-2">Início</th>
                <th className="py-2 pr-2">Fim</th>
                <th className="py-2 pr-2">Estado</th>
                <th className="py-2 pr-2 text-right">Duração (h)</th>
              </tr>
            </thead>
            <tbody>
              {data.operations.map((op) => (
                <tr key={op.schedule_id} className="border-b border-slate-800/50">
                  <td className="py-2 pr-2 font-mono text-slate-300">{op.order_id}</td>
                  <td className="py-2 pr-2 text-slate-400">{op.scheduled_start_date}</td>
                  <td className="py-2 pr-2 text-slate-400">{op.scheduled_end_date}</td>
                  <td className="py-2 pr-2">
                    <DarkBadge
                      variant={
                        op.status === 'COMPLETED'
                          ? 'success'
                          : op.status === 'IN_PROGRESS'
                          ? 'warning'
                          : 'neutral'
                      }
                      size="sm"
                    >
                      {op.status}
                    </DarkBadge>
                  </td>
                  <td className="py-2 pr-2 text-right text-slate-300">
                    {op.actual_duration_hours ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {data && (
          <div className="flex justify-between items-center mt-4 text-xs text-slate-400">
            <span>
              {offset + 1}–{offset + data.returned}
            </span>
            <div className="flex gap-2">
              <DarkButton
                variant="secondary"
                size="sm"
                onClick={() => setOffset(Math.max(0, offset - HISTORY_PAGE_SIZE))}
                disabled={offset === 0}
              >
                ← Anterior
              </DarkButton>
              <DarkButton
                variant="secondary"
                size="sm"
                onClick={() => setOffset(offset + HISTORY_PAGE_SIZE)}
                disabled={data.returned < HISTORY_PAGE_SIZE}
              >
                Seguinte →
              </DarkButton>
            </div>
          </div>
        )}
      </DarkCard>
    </div>
  );
}

export function EmployeeQualityModal({
  employee,
  onClose,
  onSuccess,
  onError,
}: {
  employee: Employee;
  onClose: () => void;
  onSuccess: () => void;
  onError: (msg: string) => void;
}) {
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ['workforce', 'quality-score', employee.id],
    queryFn: () => workforceEmployeesApi.qualityScore(employee.id),
  });

  const [override, setOverride] = useState<number | null>(null);
  const [reason, setReason] = useState('');

  const mutation = useMutation({
    mutationFn: (payload: { score: number; reason: string }) =>
      workforceEmployeesApi.overrideQualityScore(employee.id, payload),
    onSuccess: () => {
      onSuccess();
      queryClient.invalidateQueries({ queryKey: ['workforce', 'quality-score', employee.id] });
      onClose();
    },
    onError: (err: MutationError) => onError(err.message || 'Erro ao guardar override'),
  });

  const currentScore = override ?? data?.score ?? 5;
  const canSave = override != null && reason.trim().length >= 10;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <DarkCard className="w-[520px] max-w-[95vw] p-5">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-lg font-semibold text-white">Quality Score</h3>
            <p className="text-xs text-slate-400">{employee.name}</p>
          </div>
          <DarkIconButton icon={<X size={16} />} size="sm" variant="ghost" onClick={onClose} />
        </div>

        {isLoading && <p className="text-sm text-slate-400 py-4">A calcular…</p>}
        {error && <p className="text-sm text-red-400 py-4">{(error as Error).message}</p>}
        {data && (
          <>
            <div className="bg-slate-800/40 rounded-lg p-3 mb-4">
              <p className="text-xs text-slate-400">Score ML (Laplace-smoothed)</p>
              <p className="text-3xl font-bold text-white">
                {data.score.toFixed(1)}
                <span className="text-base text-slate-500"> / 10</span>
              </p>
              <p className="text-xs text-slate-500 mt-1">
                {data.operations} operações · {data.defects} retrabalhos · método:{' '}
                {data.method}
              </p>
            </div>

            <label className="block text-xs text-slate-400 mb-2">
              Override manual: {currentScore.toFixed(1)}
            </label>
            <input
              type="range"
              min={1}
              max={10}
              step={0.1}
              value={currentScore}
              onChange={(e) => setOverride(Number(e.target.value))}
              className="w-full mb-4"
            />

            <label className="block text-xs text-slate-400 mb-1">
              Porquê? (mínimo 10 caracteres — alimenta a Camada 1 de aprendizagem)
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              placeholder="Ex: trabalha bem em K1 mas o ML não viu retrabalho recente."
              className="w-full mb-4 px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm text-white"
            />

            <div className="flex justify-end gap-2">
              <DarkButton variant="secondary" size="sm" onClick={onClose}>
                Cancelar
              </DarkButton>
              <DarkButton
                size="sm"
                onClick={() => override != null && mutation.mutate({ score: override, reason })}
                disabled={!canSave || mutation.isPending}
              >
                {mutation.isPending ? 'A guardar…' : 'Guardar override'}
              </DarkButton>
            </div>
          </>
        )}
      </DarkCard>
    </div>
  );
}

export function EmployeeCompareModal({
  employees,
  onClose,
}: {
  employees: Employee[];
  onClose: () => void;
}) {
  // useQueries — array-based hook keeps React's hooks-call ordering stable
  // even when `employees.length` varies across renders.
  const qualityQueries = useQueries({
    queries: employees.map((e) => ({
      queryKey: ['workforce', 'quality-score', e.id] as const,
      queryFn: () => workforceEmployeesApi.qualityScore(e.id),
    })),
  });
  const skillQueries = useQueries({
    queries: employees.map((e) => ({
      queryKey: ['workforce', 'skill-matrix', e.id] as const,
      queryFn: () => workforceEmployeesApi.skillMatrix(e.id),
    })),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <DarkCard className="w-[1000px] max-w-[95vw] max-h-[85vh] overflow-auto p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white">
            Comparação de {employees.length} colaboradores
          </h3>
          <DarkIconButton icon={<X size={16} />} size="sm" variant="ghost" onClick={onClose} />
        </div>

        <div
          className="grid gap-4"
          style={{ gridTemplateColumns: `repeat(${employees.length}, minmax(0, 1fr))` }}
        >
          {employees.map((employee, idx) => {
            const quality = qualityQueries[idx];
            const skills = skillQueries[idx];
            return (
              <div key={employee.id} className="bg-slate-800/40 rounded-lg p-3">
                <h4 className="text-base font-semibold text-white mb-1">{employee.name}</h4>
                <p className="text-xs text-slate-500 mb-3">{employee.department}</p>

                <div className="text-xs text-slate-400 mb-1">Quality score</div>
                {quality.isLoading ? (
                  <p className="text-slate-500">…</p>
                ) : quality.error ? (
                  <p className="text-red-400">erro</p>
                ) : quality.data ? (
                  <p className="text-2xl font-bold text-white">
                    {quality.data.score.toFixed(1)}
                    <span className="text-sm text-slate-500"> /10</span>
                  </p>
                ) : null}

                <div className="text-xs text-slate-400 mt-3 mb-1">
                  Operações | Retrabalhos
                </div>
                {quality.data && (
                  <p className="text-sm text-slate-300">
                    {quality.data.operations} | {quality.data.defects}
                  </p>
                )}

                <div className="text-xs text-slate-400 mt-3 mb-1">
                  Skills ({skills.data?.total ?? 0})
                </div>
                {skills.isLoading ? (
                  <p className="text-slate-500">…</p>
                ) : skills.data ? (
                  <ul className="space-y-1 max-h-48 overflow-auto">
                    {skills.data.phases.slice(0, 12).map((s) => (
                      <li key={s.phase_id} className="flex justify-between text-xs">
                        <span className={s.can_do ? 'text-emerald-400' : 'text-slate-500'}>
                          {s.phase_name ?? s.phase_id}
                        </span>
                        <span className="text-slate-400">{s.ops_count}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            );
          })}
        </div>
      </DarkCard>
    </div>
  );
}
