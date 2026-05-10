/**
 * EmployeeFormModal — Add/Edit Employee em /equipa > Lista (Q.18 fix-workforce).
 *
 * Reutiliza FormModal + employeesApi (POST/PATCH /v1/core/employees).
 * No success faz invalidate de ['equipa', 'employees'] e ['workforce', 'employees']
 * para refresh tanto da lista nova como das vistas legacy.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FormModal, type FormField } from '../ui';
import { employeesApi } from '../../lib/api';

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
];

interface Props {
  isOpen: boolean;
  onClose: () => void;
  /** Quando definido, modal opera em modo edit. */
  editing?: { id: string; [k: string]: any } | null;
  onSuccess?: (msg: string) => void;
  onError?: (msg: string) => void;
}

export function EmployeeFormModal({ isOpen, onClose, editing, onSuccess, onError }: Props) {
  const qc = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: any) => employeesApi.create(data),
    onSuccess: () => {
      onSuccess?.('Operador criado.');
      qc.invalidateQueries({ queryKey: ['equipa', 'employees'] });
      qc.invalidateQueries({ queryKey: ['workforce', 'employees'] });
      qc.invalidateQueries({ queryKey: ['employees'] });
      onClose();
    },
    onError: (err: any) => onError?.(err?.message ?? 'Erro ao criar operador.'),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => employeesApi.update(id, data),
    onSuccess: () => {
      onSuccess?.('Operador actualizado.');
      qc.invalidateQueries({ queryKey: ['equipa', 'employees'] });
      qc.invalidateQueries({ queryKey: ['workforce', 'employees'] });
      qc.invalidateQueries({ queryKey: ['employees'] });
      onClose();
    },
    onError: (err: any) => onError?.(err?.message ?? 'Erro ao actualizar operador.'),
  });

  const handleSubmit = (data: any) => {
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
