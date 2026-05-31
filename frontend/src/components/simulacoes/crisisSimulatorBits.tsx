// Decomposto de CrisisSimulator.tsx (Q.60.AB).
import { AlertTriangle, Box, Boxes, Truck, User, Zap } from 'lucide-react';
import type { ReactNode } from 'react';
import { Tag, toneBd, toneBg, toneVar } from './atoms';
import type { Tone } from './atoms';
import type { CrisisScenario } from './crisisScenarios';

export const ICONS: Record<CrisisScenario['icon'], ReactNode> = {
  Box: <Box size={16} />,
  User: <User size={16} />,
  Boxes: <Boxes size={16} />,
  AlertTriangle: <AlertTriangle size={16} />,
  Zap: <Zap size={16} />,
  Truck: <Truck size={16} />,
};

export const SEVERITY_TONE: Record<CrisisScenario['severity'], Tone> = {
  critical: 'red',
  high: 'orange',
  medium: 'yellow',
};

export const CASCADE_LABEL: Record<Tone, string> = {
  red: 'crítico',
  orange: 'alto',
  yellow: 'aviso',
  green: 'estabilizado',
  blue: 'info',
  purple: 'info',
  teal: 'info',
  gray: 'info',
};

export interface TwinRunResult {
  scenarioId: string;
  scenarioHash: string | null;
  simulationStatus: string;
  /** `simulation_result` real persistido pelo twin (before/after/delta_summary/mode). */
  simulationResult: Record<string, unknown> | null;
  /** Modo de simulação reportado pelo twin (ex.: `projecao_linear`). */
  mode: string | null;
  /** Explicação honesta do modo (porque não correu o solver). */
  modeReason: string | null;
}

export function CrisisCard({
  scenario,
  onSelect,
}: {
  scenario: CrisisScenario;
  onSelect: () => void;
}): ReactNode {
  const tone = SEVERITY_TONE[scenario.severity];
  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        padding: 14,
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-md)',
        cursor: 'pointer',
        textAlign: 'left',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 8,
        }}
      >
        <div
          style={{
            width: 30,
            height: 30,
            borderRadius: 7,
            background: toneBg(tone),
            color: toneVar(tone),
            display: 'grid',
            placeItems: 'center',
            border: `1px solid ${toneBd(tone)}`,
          }}
        >
          {ICONS[scenario.icon]}
        </div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--fg-0)' }}>
            {scenario.label}
          </div>
          <Tag tone={tone} size="sm">
            {scenario.severity}
          </Tag>
        </div>
      </div>
      <div
        style={{ fontSize: 11.5, color: 'var(--fg-2)', lineHeight: 1.5 }}
      >
        {scenario.detail}
      </div>
    </button>
  );
}
