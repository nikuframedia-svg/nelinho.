/**
 * ScenarioSimulator — simulador de cenários what-if sobre o COGS (Q.53.I).
 *
 * Cinco multiplicadores (material, mão-de-obra, máquina, estrutura,
 * refugo) + volume aplicados ao COGS de um barco base. Liga ao endpoint
 * REAL `POST /v1/profit/scenarios/simulate`. ZERO MOCKS — sem barco base
 * seleccionado o botão fica desactivado; o resultado vem só do backend.
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Play, RotateCcw } from 'lucide-react';
import { DarkButton } from '../dark';
import { custosApi } from '../../pages/custos/custosApi';
import type {
  BoatCostRow,
  ScenarioSimulateResult,
} from '../../pages/custos/custosApi';

interface MultiplierField {
  key:
    | 'material_multiplier'
    | 'labor_multiplier'
    | 'machine_multiplier'
    | 'overhead_multiplier'
    | 'scrap_multiplier'
    | 'volume_multiplier';
  label: string;
}

const FIELDS: MultiplierField[] = [
  { key: 'material_multiplier', label: 'Material' },
  { key: 'labor_multiplier', label: 'Mão-de-obra' },
  { key: 'machine_multiplier', label: 'Máquina' },
  { key: 'overhead_multiplier', label: 'Estrutura' },
  { key: 'scrap_multiplier', label: 'Refugo' },
  { key: 'volume_multiplier', label: 'Volume' },
];

const NEUTRAL: Record<MultiplierField['key'], number> = {
  material_multiplier: 1,
  labor_multiplier: 1,
  machine_multiplier: 1,
  overhead_multiplier: 1,
  scrap_multiplier: 1,
  volume_multiplier: 1,
};

export interface ScenarioSimulatorProps {
  /** Barcos com COGS calculado — candidatos a base do cenário. */
  boats: BoatCostRow[];
}

function fmtEur(n: number): string {
  return `€${n.toLocaleString('pt-PT', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function ScenarioSimulator({
  boats,
}: ScenarioSimulatorProps): ReactNode {
  const [baseOrderId, setBaseOrderId] = useState('');
  const [mults, setMults] =
    useState<Record<MultiplierField['key'], number>>(NEUTRAL);

  const simulation = useMutation<ScenarioSimulateResult, Error>({
    mutationFn: () =>
      custosApi.simulateScenario({
        base_order_id: baseOrderId,
        scenario_name: 'Cenário manual',
        ...mults,
      }),
  });

  const result = simulation.data;
  const canRun = baseOrderId !== '' && !simulation.isPending;

  function reset(): void {
    setMults(NEUTRAL);
    simulation.reset();
  }

  if (boats.length === 0) {
    return (
      <div
        style={{
          padding: 24,
          textAlign: 'center',
          fontSize: 12,
          color: 'var(--fg-3)',
        }}
      >
        Sem barcos com COGS calculado — não há base para simular um cenário.
        Calcula o COGS de pelo menos um barco primeiro.
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Barco base */}
      <div>
        <label
          htmlFor="custos-scenario-base"
          style={{
            display: 'block',
            fontSize: 11,
            color: 'var(--fg-2)',
            marginBottom: 4,
            textTransform: 'uppercase',
            letterSpacing: 0.4,
          }}
        >
          Barco base
        </label>
        <select
          id="custos-scenario-base"
          value={baseOrderId}
          onChange={(e) => setBaseOrderId(e.target.value)}
          className="text-slate-900 placeholder:text-slate-400"
          style={{
            width: '100%',
            padding: '6px 10px',
            borderRadius: 'var(--r-sm)',
            border: '1px solid var(--bd-2)',
            background: '#fff',
            fontSize: 12,
          }}
        >
          <option value="">— escolher barco —</option>
          {boats.map((b) => (
            <option key={b.order_id} value={b.order_id}>
              #{b.hull} · {b.product_name ?? b.product_type ?? 'modelo —'}
            </option>
          ))}
        </select>
      </div>

      {/* Multiplicadores */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 8,
        }}
      >
        {FIELDS.map((f) => (
          <div key={f.key}>
            <label
              htmlFor={`custos-mult-${f.key}`}
              style={{
                display: 'block',
                fontSize: 10.5,
                color: 'var(--fg-2)',
                marginBottom: 3,
              }}
            >
              {f.label} ×
            </label>
            <input
              id={`custos-mult-${f.key}`}
              type="number"
              step="0.05"
              min="0"
              value={mults[f.key]}
              onChange={(e) =>
                setMults((m) => ({
                  ...m,
                  [f.key]: Number(e.target.value) || 0,
                }))
              }
              className="text-slate-900 placeholder:text-slate-400"
              style={{
                width: '100%',
                padding: '5px 8px',
                borderRadius: 'var(--r-sm)',
                border: '1px solid var(--bd-2)',
                background: '#fff',
                fontSize: 12,
              }}
            />
          </div>
        ))}
      </div>

      {/* Acções */}
      <div style={{ display: 'flex', gap: 8 }}>
        <DarkButton
          size="sm"
          onClick={() => simulation.mutate()}
          disabled={!canRun}
        >
          <Play size={12} />
          {simulation.isPending ? 'A simular…' : 'Simular cenário'}
        </DarkButton>
        <DarkButton variant="ghost" size="sm" onClick={reset}>
          <RotateCcw size={12} />
          Repor
        </DarkButton>
      </div>

      {/* Erro */}
      {simulation.isError && (
        <div
          style={{
            padding: '8px 10px',
            borderRadius: 'var(--r-sm)',
            background: 'var(--red-bg)',
            border: '1px solid var(--red-bd)',
            fontSize: 11.5,
            color: 'var(--red)',
          }}
        >
          A simulação falhou: {simulation.error.message}
        </div>
      )}

      {/* Resultado */}
      {result && (
        <div
          style={{
            padding: 12,
            borderRadius: 'var(--r-md)',
            background: 'var(--bg-2)',
            border: '1px solid var(--bd-2)',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 12,
            }}
          >
            <div>
              <div style={{ fontSize: 10, color: 'var(--fg-3)' }}>
                COGS base / unidade
              </div>
              <div
                className="tabular"
                style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-0)' }}
              >
                {fmtEur(result.base_cogs_per_unit)}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 10, color: 'var(--fg-3)' }}>
                COGS cenário / unidade
              </div>
              <div
                className="tabular"
                style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-0)' }}
              >
                {fmtEur(result.scenario_cogs_per_unit)}
              </div>
            </div>
          </div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              paddingTop: 8,
              borderTop: '1px solid var(--bd-1)',
            }}
          >
            <span
              style={{
                fontSize: 10.5,
                color: 'var(--fg-3)',
                textTransform: 'uppercase',
                letterSpacing: 0.4,
              }}
            >
              Variação
            </span>
            <span
              className="tabular"
              style={{
                fontSize: 14,
                fontWeight: 700,
                color:
                  result.delta_amount > 0
                    ? 'var(--red)'
                    : result.delta_amount < 0
                    ? 'var(--green)'
                    : 'var(--fg-2)',
              }}
            >
              {result.delta_amount > 0 ? '+' : ''}
              {fmtEur(result.delta_amount)} ({result.delta_percent > 0 ? '+' : ''}
              {result.delta_percent.toFixed(1)}%)
            </span>
          </div>
          {result.recommendation && (
            <div
              style={{
                fontSize: 11.5,
                color: 'var(--fg-1)',
                lineHeight: 1.5,
              }}
            >
              {result.recommendation}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
