/**
 * MasterDataBrowser — navegador de dados-mestre (Q.118.P).
 * =========================================================
 *
 * A tab master só tinha acções destrutivas (cancelar/reformar). Isto liga os
 * dados-mestre core que estavam órfãos: produtos/clientes/operadores/máquinas
 * (GET /v1/core/{products,customers,employees,machines}, masterDataApi já
 * existente). Read-only, com ficha clicável onde existe (modelo/cliente/
 * operador). ZERO MOCKS: empty/loading/erro explícitos.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Boxes } from 'lucide-react';
import { DarkCard, DarkBadge, EmptyState, Segmented } from '../dark';
import { Clickable } from '../entitySheets';
import { productsApi, customersApi, employeesApi, machinesApi } from '../../lib/api';

type Entity = 'produtos' | 'clientes' | 'operadores' | 'maquinas';

// Formas core (espelham src/core/api/schemas.py) — só os campos usados.
interface CoreProduct { id: string; product_code: string; product_name: string; product_type?: string; category?: string | null; status?: string; }
interface CoreCustomer { id: string; customer_code: string; customer_name: string; segment?: string; price_tier?: string; }
interface CoreEmployee { id: string; employee_code: string; employee_name: string; department?: string | null; job_title?: string | null; status?: string; }
interface CoreMachine { id: string; machine_code: string; machine_name: string; machine_type?: string; location?: string | null; status?: string; }

interface Row {
  key: string;
  code: string;
  name: string;
  meta: string;
  status: string;
  clickable?: { kind: 'modelo' | 'cliente' | 'operador'; id: string };
}

const OPTIONS: { value: Entity; label: string }[] = [
  { value: 'produtos', label: 'Produtos' },
  { value: 'clientes', label: 'Clientes' },
  { value: 'operadores', label: 'Operadores' },
  { value: 'maquinas', label: 'Máquinas' },
];

function statusVariant(s: string): 'success' | 'neutral' | 'warning' {
  const v = (s || '').toLowerCase();
  if (v.includes('active') || v.includes('activ')) return 'success';
  if (v.includes('inactive') || v.includes('retired') || v.includes('deprec')) return 'warning';
  return 'neutral';
}

export function MasterDataBrowser() {
  const [entity, setEntity] = useState<Entity>('produtos');

  const query = useQuery({
    queryKey: ['core', 'master-data', entity],
    queryFn: async (): Promise<Row[]> => {
      if (entity === 'produtos') {
        const items = ((await productsApi.list({ limit: 200 })) ?? []) as CoreProduct[];
        return items.map((p) => ({
          key: String(p.id),
          code: p.product_code,
          name: p.product_name,
          meta: [p.product_type, p.category].filter(Boolean).join(' · '),
          status: String(p.status ?? ''),
          clickable: { kind: 'modelo' as const, id: String(p.product_name) },
        }));
      }
      if (entity === 'clientes') {
        const items = ((await customersApi.list({ limit: 200 })) ?? []) as CoreCustomer[];
        return items.map((c) => ({
          key: String(c.id),
          code: c.customer_code,
          name: c.customer_name,
          meta: [c.segment, c.price_tier].filter(Boolean).join(' · '),
          status: '',
          clickable: { kind: 'cliente' as const, id: String(c.id) },
        }));
      }
      if (entity === 'operadores') {
        const items = ((await employeesApi.list({ limit: 200 })) ?? []) as CoreEmployee[];
        return items.map((e) => ({
          key: String(e.id),
          code: e.employee_code,
          name: e.employee_name,
          meta: [e.department, e.job_title].filter(Boolean).join(' · '),
          status: String(e.status ?? ''),
          clickable: { kind: 'operador' as const, id: String(e.id) },
        }));
      }
      const items = ((await machinesApi.list({ limit: 200 })) ?? []) as CoreMachine[];
      return items.map((m) => ({
        key: String(m.id),
        code: m.machine_code,
        name: m.machine_name,
        meta: [m.machine_type, m.location].filter(Boolean).join(' · '),
        status: String(m.status ?? ''),
      }));
    },
    retry: false,
    refetchOnWindowFocus: false,
  });

  const rows = query.data ?? [];

  return (
    <DarkCard>
      <div className="flex items-center gap-2 mb-1">
        <Boxes size={15} className="text-fg-2" />
        <h3 className="text-sm font-semibold text-text-dark-primary">Dados-mestre</h3>
      </div>
      <p className="text-xs text-text-dark-tertiary mb-4">
        Produtos, clientes, operadores e máquinas do ERP — clica para abrir a ficha.
      </p>

      <div className="mb-4">
        <Segmented<Entity> options={OPTIONS} value={entity} onChange={setEntity} ariaLabel="Tipo de dado-mestre" />
      </div>

      {query.isError ? (
        <p className="text-xs text-text-dark-tertiary">Indisponível.</p>
      ) : query.isLoading ? (
        <p className="text-sm text-text-dark-tertiary">A carregar…</p>
      ) : rows.length === 0 ? (
        <EmptyState mascot={false} icon={<Boxes size={24} />} title="Sem registos" hint="Sincroniza o ERP para popular os dados-mestre." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text-dark-tertiary text-xs">
                <th className="text-left font-medium py-1 pr-3">Código</th>
                <th className="text-left font-medium py-1 pr-3">Nome</th>
                <th className="text-left font-medium py-1 pr-3">Detalhe</th>
                <th className="text-left font-medium py-1">Estado</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 100).map((r) => (
                <tr key={r.key} className="border-t border-white/5">
                  <td className="py-1.5 pr-3 font-mono text-xs text-text-dark-secondary">{r.code}</td>
                  <td className="py-1.5 pr-3 text-text-dark-primary">
                    {r.clickable ? (
                      <Clickable kind={r.clickable.kind} id={r.clickable.id}>
                        {r.name}
                      </Clickable>
                    ) : (
                      r.name
                    )}
                  </td>
                  <td className="py-1.5 pr-3 text-text-dark-tertiary text-xs">{r.meta || '—'}</td>
                  <td className="py-1.5">
                    {r.status ? (
                      <DarkBadge variant={statusVariant(r.status)} size="sm">
                        {r.status}
                      </DarkBadge>
                    ) : (
                      '—'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length > 100 ? (
            <p className="text-xs text-text-dark-tertiary mt-2">A mostrar 100 de {rows.length}.</p>
          ) : null}
        </div>
      )}
    </DarkCard>
  );
}
