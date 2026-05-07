/**
 * OperadoresPage — Plan v4 §10 (Equipa) operator list.
 *
 * Wraps GET /v1/core/employees with filters (status, search) and
 * routes click-through to /operadores/:id for the detail view. ZERO
 * MOCKS — empty / error / loading states explicit.
 *
 * Pode ser substituído eventualmente pelo Equipa do design v4 (com
 * fotos, scores, skills inline). Para já é a lista canónica e cumpre
 * o contrato "tudo editável" via link para o detalhe.
 */

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Loader2, RefreshCw, Search, ServerCrash, Users } from 'lucide-react';
import { employeesApi } from '../lib/api';
import { DarkPageLayout } from '../layouts';
import {
  DarkBadge,
  DarkButton,
  DarkCard,
  DarkInput,
  DarkSelect,
  DarkTable,
  DarkTableBody,
  DarkTableCell,
  DarkTableHead,
  DarkTableHeader,
  DarkTableRow,
} from '../components/dark';

type StatusFilter = 'all' | 'active' | 'on_leave' | 'terminated';

interface EmployeeRow {
  id: string;
  employee_code: string;
  employee_name: string;
  status: string;
  department?: string | null;
  job_title?: string | null;
  hire_date?: string | null;
  hourly_loaded_rate?: string | number | null;
}

const STATUS_BADGE: Record<string, { label: string; variant: 'success' | 'warning' | 'danger' | 'neutral' }> = {
  active: { label: 'Activo', variant: 'success' },
  on_leave: { label: 'Ausente', variant: 'warning' },
  terminated: { label: 'Cessado', variant: 'danger' },
};

function statusChip(status: string) {
  const s = STATUS_BADGE[status];
  if (!s) return <DarkBadge variant="neutral">{status}</DarkBadge>;
  return <DarkBadge variant={s.variant}>{s.label}</DarkBadge>;
}

function fmtRate(raw: string | number | null | undefined): string {
  if (raw == null || raw === '') return '—';
  const n = typeof raw === 'string' ? Number(raw) : raw;
  if (!Number.isFinite(n)) return '—';
  return `€${n.toFixed(2)}/h`;
}

export default function OperadoresPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('active');
  const [search, setSearch] = useState('');

  const { data, isLoading, error, refetch, isFetching } = useQuery({
    queryKey: ['operadores', statusFilter],
    queryFn: () =>
      employeesApi.list({
        limit: 200,
        status: statusFilter === 'all' ? undefined : statusFilter,
      }),
    staleTime: 30_000,
  });

  const rows: EmployeeRow[] = useMemo(() => {
    const base: unknown = data;
    let list: EmployeeRow[] = [];
    if (Array.isArray(base)) {
      list = base as EmployeeRow[];
    } else if (base && typeof base === 'object' && 'items' in (base as object)) {
      list = ((base as { items: EmployeeRow[] }).items) ?? [];
    }
    if (!search) return list;
    const q = search.toLowerCase();
    return list.filter(
      (e) =>
        e.employee_name.toLowerCase().includes(q) ||
        e.employee_code.toLowerCase().includes(q) ||
        (e.department ?? '').toLowerCase().includes(q),
    );
  }, [data, search]);

  return (
    <DarkPageLayout
      title="Operadores"
      subtitle="Equipa da fábrica — clica num operador para ver score, skills e histórico."
      icon={<Users className="w-6 h-6 text-emerald-300" />}
      actions={
        <DarkButton
          onClick={() => refetch()}
          variant="secondary"
          disabled={isFetching}
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          Actualizar
        </DarkButton>
      }
    >
      <div className="flex flex-col gap-4">
        <DarkCard className="p-3 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <DarkInput
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Pesquisar por nome, código ou departamento..."
              className="pl-9"
            />
          </div>
          <DarkSelect
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            options={[
              { value: 'active', label: 'Activos' },
              { value: 'on_leave', label: 'Ausentes' },
              { value: 'terminated', label: 'Cessados' },
              { value: 'all', label: 'Todos' },
            ]}
          />
        </DarkCard>

        {isLoading ? (
          <DarkCard className="p-10 flex items-center justify-center gap-2 text-slate-300">
            <Loader2 className="w-5 h-5 animate-spin text-sky-300" /> A carregar operadores...
          </DarkCard>
        ) : error ? (
          <DarkCard className="p-10 flex flex-col items-center justify-center gap-3 border-rose-500/30 bg-rose-500/5 text-rose-200">
            <ServerCrash className="w-8 h-8" />
            <div className="text-base font-semibold">
              Não consegui ler os operadores.
            </div>
            <div className="text-sm text-rose-200/80 max-w-lg text-center">
              {error instanceof Error ? error.message : String(error)}
            </div>
            <DarkButton onClick={() => refetch()} variant="primary">
              Tentar de novo
            </DarkButton>
          </DarkCard>
        ) : rows.length === 0 ? (
          <DarkCard className="p-10 flex flex-col items-center justify-center gap-2 text-slate-400">
            <Users className="w-10 h-10 text-slate-600" />
            <div className="text-base text-slate-200">Sem operadores neste filtro.</div>
            <div className="text-sm">Tenta mudar o estado ou limpar a pesquisa.</div>
          </DarkCard>
        ) : (
          <DarkCard className="p-0 overflow-hidden">
            <DarkTable>
              <DarkTableHead>
                <DarkTableRow>
                  <DarkTableHeader>Código</DarkTableHeader>
                  <DarkTableHeader>Nome</DarkTableHeader>
                  <DarkTableHeader>Departamento</DarkTableHeader>
                  <DarkTableHeader>Função</DarkTableHeader>
                  <DarkTableHeader>Estado</DarkTableHeader>
                  <DarkTableHeader>Custo/h</DarkTableHeader>
                </DarkTableRow>
              </DarkTableHead>
              <DarkTableBody>
                {rows.map((e) => (
                  <DarkTableRow key={e.id} className="hover:bg-slate-800/40">
                    <DarkTableCell className="font-mono text-xs">
                      {e.employee_code}
                    </DarkTableCell>
                    <DarkTableCell>
                      <Link
                        to={`/operadores/${encodeURIComponent(e.id)}`}
                        className="text-sky-300 hover:text-sky-200 font-medium"
                      >
                        {e.employee_name}
                      </Link>
                    </DarkTableCell>
                    <DarkTableCell className="text-slate-300">
                      {e.department ?? '—'}
                    </DarkTableCell>
                    <DarkTableCell className="text-slate-300">
                      {e.job_title ?? '—'}
                    </DarkTableCell>
                    <DarkTableCell>{statusChip(e.status)}</DarkTableCell>
                    <DarkTableCell className="font-mono">
                      {fmtRate(e.hourly_loaded_rate)}
                    </DarkTableCell>
                  </DarkTableRow>
                ))}
              </DarkTableBody>
            </DarkTable>
            <div className="px-4 py-2 text-[11px] text-slate-500 border-t border-slate-800">
              {rows.length} operador{rows.length === 1 ? '' : 'es'}
            </div>
          </DarkCard>
        )}
      </div>
    </DarkPageLayout>
  );
}
