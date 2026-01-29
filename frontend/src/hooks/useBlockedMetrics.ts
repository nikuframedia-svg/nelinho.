/**
 * useBlockedMetrics — Hook for fetching blocked metrics
 * Part of TIER 1: THE FOUNDATION OF TRUTH
 */

import { useEffect, useState, useCallback } from 'react';
import type { BlockedMetric } from '@/types';

// NOTE: API_BASE would be used when backend endpoint is implemented
// const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useBlockedMetrics() {
  const [metrics, setMetrics] = useState<BlockedMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchMetrics = useCallback(async () => {
    try {
      setLoading(true);
      
      // NOTE: The blocked-metrics endpoint doesn't exist in the backend yet.
      // Using mock data based on real PP1 blocked metrics from config.py
      // TODO: Create /v1/factory/semantic/blocked-metrics endpoint when needed
      
      // Mock data based on real PP1 blocked metrics
      const mockMetrics: BlockedMetric[] = [
        {
          id: 'oee_real',
          name: 'OEE Real',
          name_pt: 'OEE Real',
          reason: 'Não existem dados de paragens/máquinas',
          required_data: [
            { field: 'machine_downtime', coverage: 0, status: 'missing' },
            { field: 'planned_production_time', coverage: 0, status: 'missing' },
          ],
          how_to_unlock: [
            'Integrar sistema MES com registos de paragens',
            'Definir calendário de turnos no ERP',
            'Configurar sensores IoT nas máquinas críticas',
          ],
          alternative: {
            id: 'oee_theoretical',
            name: 'OEE Teórico',
            trust_index: 65,
          },
        },
        {
          id: 'productivity_individual_real',
          name: 'Productivity Individual Real',
          name_pt: 'Produtividade Individual Real',
          reason: 'Não existem horas reais por funcionário',
          required_data: [
            { field: 'actual_labor_hours_per_employee', coverage: 0, status: 'missing' },
          ],
          how_to_unlock: [
            'Implementar registo de ponto por funcionário',
            'Integrar com sistema de RH',
          ],
        },
        {
          id: 'cost_real_per_order',
          name: 'Cost Real Per Order',
          name_pt: 'Custo Real por Ordem',
          reason: 'Não existem horas reais por funcionário',
          required_data: [
            { field: 'actual_labor_hours_per_employee', coverage: 0, status: 'missing' },
          ],
          how_to_unlock: [
            'Implementar registo de ponto por funcionário',
            'Registar materiais consumidos por ordem',
          ],
          alternative: {
            id: 'cost_theoretical_per_order',
            name: 'Custo Teórico por Ordem',
            trust_index: 70,
          },
        },
        {
          id: 'otd_official',
          name: 'OTD Official',
          name_pt: 'OTD Oficial',
          reason: 'Não existe promessa comercial inequívoca (due date)',
          required_data: [
            { field: 'promised_delivery_date', coverage: 0, status: 'missing' },
          ],
          how_to_unlock: [
            'Adicionar campo de data prometida no ERP',
            'Integrar com CRM para obter compromissos comerciais',
          ],
        },
        {
          id: 'capacity_real_per_day',
          name: 'Capacity Real Per Day',
          name_pt: 'Capacidade Real por Dia',
          reason: 'Não existem dados de turnos/paragens',
          required_data: [
            { field: 'shift_calendar', coverage: 0, status: 'missing' },
            { field: 'machine_downtime', coverage: 0, status: 'missing' },
          ],
          how_to_unlock: [
            'Definir calendário de turnos',
            'Implementar registo de paragens',
          ],
        },
        {
          id: 'mold_conflict_confirmed',
          name: 'Mold Conflict Confirmed',
          name_pt: 'Conflito de Moldes Confirmado',
          reason: 'DataPrevista tem apenas 4.8% de cobertura',
          required_data: [
            { field: 'complete_scheduled_dates', coverage: 4.8, status: 'partial' },
          ],
          how_to_unlock: [
            'Exigir preenchimento de DataPrevista no ERP',
            'Implementar preenchimento automático baseado em lead time médio',
          ],
          alternative: {
            id: 'mold_conflict_theoretical',
            name: 'Conflito de Moldes (Teórico)',
            trust_index: 45,
          },
        },
        {
          id: 'availability_oee',
          name: 'Availability OEE',
          name_pt: 'Disponibilidade OEE',
          reason: 'Não existem dados de paragens/máquinas',
          required_data: [
            { field: 'machine_downtime', coverage: 0, status: 'missing' },
            { field: 'planned_production_time', coverage: 0, status: 'missing' },
          ],
          how_to_unlock: [
            'Integrar sistema MES',
            'Definir calendário de produção',
          ],
        },
      ];
      
      setMetrics(mockMetrics);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  return { metrics, loading, error, refresh: fetchMetrics };
}

export default useBlockedMetrics;

