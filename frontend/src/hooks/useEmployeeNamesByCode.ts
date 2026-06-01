/**
 * useEmployeeNamesByCode — mapa `employee_code → employee_name` (Q.154.A).
 *
 * O plano identifica colaboradores pelo `employee_code` (== `E_ID` do ERP).
 * Vários sítios da UI mostram esse código cru (ex. FaseSheet → Configuração).
 * Este hook centraliza a query + o Map para não duplicar a lógica que já vivia
 * inline no OverallPage (Q.147.C / Q.148.B).
 *
 * ZERO MOCKS: bate em `/v1/core/employees` real. Se vier vazio, o Map fica
 * vazio e os consumidores fazem fallback ao código cru (nunca nomes inventados).
 *
 * Partilha a MESMA query key do editor de plano (`coreKeys.employeesForPlanEditor`,
 * valor idêntico ao literal do OverallPage) → o TanStack Query desduplica o
 * fetch e reaproveita o cache de 10 min (0 fetch extra ao chegar de /overall).
 */
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { employeesApi } from '../lib/api';
import { coreKeys } from '../lib/api/keys';

export function useEmployeeNamesByCode(): Map<string, string> {
  const { data } = useQuery({
    queryKey: coreKeys.employeesForPlanEditor(),
    queryFn: () => employeesApi.list({ limit: 1000 }),
    staleTime: 10 * 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  return useMemo(() => {
    const m = new Map<string, string>();
    for (const e of (data ?? []) as Array<{
      employee_code?: string;
      employee_name?: string;
    }>) {
      if (e.employee_code && e.employee_name) {
        m.set(String(e.employee_code), String(e.employee_name));
      }
    }
    return m;
  }, [data]);
}

export default useEmployeeNamesByCode;
