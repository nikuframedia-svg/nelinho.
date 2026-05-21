/**
 * EmployeeFormModal — Add/Edit Employee em /equipa > Lista (Q.18 fix-workforce).
 *
 * Reutiliza FormModal + employeesApi (POST/PATCH /v1/core/employees).
 * No success faz invalidate de ['equipa', 'employees'] e ['workforce', 'employees']
 * para refresh tanto da lista nova como das vistas legacy.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FormModal, type FormField } from '../ui';
import { employeesApi, workforceEmployeesApi } from '../../lib/api';
import type { MutationError, MutationPayload } from '../../lib/api-helpers';

// Q.18 fix-workforce — mapping nível inicial (1-3, 1=melhor) → quality score
// Laplace [1-10] que o sistema usa para derivar o nível. Útil para definir
// nível inicial quando o operador é novo (sem histórico → score default ≈9).
//   1 (Top)        → 9.0 (acima do limiar 8.0)
//   2 (Médio)      → 6.5 (entre 5.0 e 7.9)
//   3 (Em formação)→ 3.0 (abaixo de 5.0)
const LEVEL_TO_SCORE: Record<string, number> = {
  '1': 9.0,
  '2': 6.5,
  '3': 3.0,
};

const FIELDS: FormField[] = [
  { name: 'employee_code', label: 'Código', type: 'text', required: true },
  { name: 'employee_name', label: 'Nome', type: 'text', required: true },
  { name: 'department', label: 'Departamento', type: 'text', required: true },
  { name: 'job_title', label: 'Função', type: 'text' },
  { name: 'hire_date', label: 'Data de admissão (YYYY-MM-DD)', type: 'text' },
  { name: 'base_monthly_salary', label: 'Salário mensal base (€)', type: 'number' },
  { name: 'burden_rate', label: 'Burden rate (0–1, ex: 0.25)', type: 'number' },
  {
    name: 'shift_pattern',
    label: 'Turno',
    type: 'select',
    options: [
      { value: 'DAY', label: 'Manhã' },
      { value: 'NIGHT', label: 'Noite' },
      { value: 'ROTATING', label: 'Rotativo' },
      { value: 'FLEXIBLE', label: 'Flexível' },
    ],
    defaultValue: 'DAY',
  },
  {
    name: 'status',
    label: 'Estado',
    type: 'select',
    options: [
      { value: 'ACTIVE', label: 'Activo' },
      { value: 'ON_LEAVE', label: 'Férias / Licença' },
      { value: 'SUSPENDED', label: 'Suspenso' },
      { value: 'TERMINATED', label: 'Terminado' },
    ],
    defaultValue: 'ACTIVE',
  },
  {
    name: 'nivel_inicial',
    label: 'Nível (1=Top, 2=Médio, 3=Em formação) — opcional',
    type: 'select',
    options: [
      { value: '', label: 'Deixar derivar dos defeitos automaticamente' },
      { value: '1', label: '1 — Top (faz K1 elite + K4)' },
      { value: '2', label: '2 — Médio (faz K2 + K1 standard)' },
      { value: '3', label: '3 — Em formação (recreio supervisionado)' },
    ],
  },
];

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** Quando definido, modal opera em modo edit. */
  editing?: { id: string; [k: string]: unknown } | null;
  onSuccess?: (msg: string) => void;
  onError?: (msg: string) => void;
}

export function EmployeeFormModal({ isOpen, onClose, editing, onSuccess, onError }: Props) {
  const qc = useQueryClient();

  function invalidate() {
    qc.invalidateQueries({ queryKey: ['equipa', 'employees'] });
    qc.invalidateQueries({ queryKey: ['equipa', 'employee-levels'] });
    qc.invalidateQueries({ queryKey: ['workforce', 'employees'] });
    qc.invalidateQueries({ queryKey: ['employees'] });
    qc.invalidateQueries({ queryKey: ['employee-level-summary'] });
  }

  /** Faz override do quality score quando user seleccionou um nível inicial.
   * Aceita falha silenciosa: o employee já foi criado/actualizado. */
  async function maybeOverrideLevel(employeeId: string, nivelStr: string | undefined) {
    if (!nivelStr) return;
    const score = LEVEL_TO_SCORE[String(nivelStr)];
    if (typeof score !== 'number') return;
    try {
      await workforceEmployeesApi.overrideQualityScore(employeeId, {
        score,
        reason: `Nível inicial ${nivelStr} definido manualmente via /equipa Add/Edit form`,
      });
    } catch (rawErr: unknown) {
      // Não falha o flow — só avisa.
      const err = rawErr as { message?: string };
      onError?.(`Operador gravado, mas nível não foi gravado: ${err?.message ?? 'erro'}`);
    }
  }

  const createMutation = useMutation({
    mutationFn: async (data: MutationPayload) => {
      const { nivel_inicial, ...payload } = data;
      const created = await employeesApi.create(payload as MutationPayload);
      const createdShape = created as { id?: string; employee_id?: string } | null;
      const newId = createdShape?.id ?? createdShape?.employee_id;
      if (newId) await maybeOverrideLevel(String(newId), nivel_inicial as string | undefined);
      return created;
    },
    onSuccess: () => {
      onSuccess?.('Operador criado.');
      invalidate();
      onClose();
    },
    onError: (err: MutationError) => onError?.(err?.message ?? 'Erro ao criar operador.'),
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: MutationPayload }) => {
      const { nivel_inicial, ...payload } = data;
      const updated = await employeesApi.update(id, payload as MutationPayload);
      await maybeOverrideLevel(id, nivel_inicial as string | undefined);
      return updated;
    },
    onSuccess: () => {
      onSuccess?.('Operador actualizado.');
      invalidate();
      onClose();
    },
    onError: (err: MutationError) => onError?.(err?.message ?? 'Erro ao actualizar operador.'),
  });

  const handleSubmit = (data: MutationPayload) => {
    if (editing?.id) {
      updateMutation.mutate({ id: editing.id, data });
    } else {
      createMutation.mutate(data);
    }
  };

  return (
    <FormModal
      title={editing ? 'Editar operador' : 'Adicionar operador'}
      isOpen={isOpen}
      onClose={onClose}
      onSubmit={handleSubmit}
      initialData={editing ?? {}}
      fields={FIELDS}
      isLoading={createMutation.isPending || updateMutation.isPending}
    />
  );
}
