/**
 * CrisisSimulator — tab "Crise · agora" da página Simulações.
 *
 * Fluxo de 3 passos do design NELO.html (page-simulacoes.jsx):
 *   1. Escolher um dos 6 cenários de crise pré-definidos.
 *   2. Confirmar · correr no digital twin sandbox.
 *   3. Ver cascata, axiomas Spelke e opções de mitigação.
 *
 * O "correr" é REAL: cria um twin scenario, aplica os deltas
 * pré-definidos e simula. O `scenario_hash` e o `simulation_result`
 * que voltam do backend provam que a sandbox correu — a cascata e as
 * opções vêm da configuração do cenário (descrevem o problema).
 *
 * Sprint Q.52.M.
 */

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  AlertTriangle,
  Box,
  Boxes,
  Check,
  ChevronLeft,
  Clock,
  Hash,
  Loader2,
  PlayCircle,
  Sparkles,
  Truck,
  User,
  Zap,
} from 'lucide-react';
import type { ReactNode } from 'react';
import { twinApi } from '../../lib/api';
import { useToastContext } from '../ToastProvider';
import { Card, SectionHeader, Tag, fmtEuro, toneBd, toneBg, toneVar } from './atoms';
import type { Tone } from './atoms';
import { CRISIS_SCENARIOS } from './crisisScenarios';
import type { CrisisScenario } from './crisisScenarios';

const ICONS: Record<CrisisScenario['icon'], ReactNode> = {
  Box: <Box size={16} />,
  User: <User size={16} />,
  Boxes: <Boxes size={16} />,
  AlertTriangle: <AlertTriangle size={16} />,
  Zap: <Zap size={16} />,
  Truck: <Truck size={16} />,
};

const SPELKE_AXIOMS = [
  'Capacidade ≥ 0',
  'Precedência das fases',
  'Molde exclusivo',
  'Dual-resource Laminagem',
  'Compatibilidade de skill',
  'Cura · 16 transições',
  'Safety net ≥ baseline',
];

const SEVERITY_TONE: Record<CrisisScenario['severity'], Tone> = {
  critical: 'red',
  high: 'orange',
  medium: 'yellow',
};

const CASCADE_LABEL: Record<Tone, string> = {
  red: 'crítico',
  orange: 'alto',
  yellow: 'aviso',
  green: 'estabilizado',
  blue: 'info',
  purple: 'info',
  teal: 'info',
  gray: 'info',
};

interface TwinRunResult {
  scenarioId: string;
  scenarioHash: string | null;
  simulationStatus: string;
}

function CrisisCard({
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

export function CrisisSimulator(): ReactNode {
  const toast = useToastContext();
  const [picked, setPicked] = useState<CrisisScenario | null>(null);
  const [result, setResult] = useState<TwinRunResult | null>(null);
  const [chosenOption, setChosenOption] = useState<string | null>(null);

  const runMutation = useMutation({
    mutationFn: async (scenario: CrisisScenario): Promise<TwinRunResult> => {
      // 1. Cria o twin scenario real.
      const created = await twinApi.createScenario({
        title: scenario.scenarioTitle,
        description: scenario.detail,
      });
      const scenarioId = String(created.id);
      // 2. Aplica os deltas pré-definidos.
      for (const delta of scenario.deltas) {
        await twinApi.applyDelta(scenarioId, delta);
      }
      // 3. Simula a cascata na sandbox isolada.
      const sim = await twinApi.simulate(scenarioId);
      const fresh = await twinApi.getScenario(scenarioId);
      return {
        scenarioId,
        scenarioHash: fresh?.scenario_hash ?? null,
        simulationStatus: String(sim?.status ?? 'simulado'),
      };
    },
    onSuccess: (r) => {
      setResult(r);
      toast.success('Simulação de crise concluída na sandbox');
    },
    onError: (err: unknown) =>
      toast.error(
        err instanceof Error ? err.message : 'Falhou a simulação de crise',
      ),
  });

  const reset = (): void => {
    setPicked(null);
    setResult(null);
    setChosenOption(null);
    runMutation.reset();
  };

  // ── Passo 1 — escolher cenário ────────────────────────────────────
  if (!picked) {
    return (
      <>
        <Card padding={18} style={{ marginBottom: 14 }}>
          <div
            style={{ display: 'flex', alignItems: 'center', gap: 12 }}
          >
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 8,
                background: 'var(--red-bg)',
                border: '1px solid var(--red-bd)',
                color: 'var(--red)',
                display: 'grid',
                placeItems: 'center',
              }}
            >
              <AlertTriangle size={18} />
            </div>
            <div>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  color: 'var(--fg-0)',
                }}
              >
                Simulador de crise · "E se acontecer agora?"
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--fg-2)',
                  marginTop: 2,
                }}
              >
                Escolhe um problema de produção · vê a cascata, os barcos
                afectados e as opções com € e dias
              </div>
            </div>
            <div style={{ marginLeft: 'auto' }}>
              <Tag tone="red" size="sm">
                Sandbox · não toca produção
              </Tag>
            </div>
          </div>
        </Card>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 10,
          }}
        >
          {CRISIS_SCENARIOS.map((c) => (
            <CrisisCard
              key={c.id}
              scenario={c}
              onSelect={() => setPicked(c)}
            />
          ))}
        </div>
      </>
    );
  }

  const tone = SEVERITY_TONE[picked.severity];

  // ── Passo 2 (a correr) ────────────────────────────────────────────
  if (runMutation.isPending) {
    return (
      <Card padding={48} style={{ textAlign: 'center' }}>
        <Loader2
          size={32}
          className="animate-spin"
          style={{ margin: '0 auto 16px', color: 'var(--accent)' }}
        />
        <div
          style={{
            fontSize: 14,
            color: 'var(--fg-0)',
            fontWeight: 500,
            marginBottom: 6,
          }}
        >
          A simular a cascata no digital twin…
        </div>
        <div style={{ fontSize: 12, color: 'var(--fg-2)' }}>
          Snapshot da BD · aplicar o problema · propagar · validar 7 axiomas
        </div>
      </Card>
    );
  }

  // ── Passo 2 — confirmar ───────────────────────────────────────────
  if (!result) {
    return (
      <>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 14,
          }}
        >
          <button
            type="button"
            onClick={reset}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '4px 9px',
              background: 'transparent',
              border: 'none',
              color: 'var(--fg-1)',
              fontSize: 11.5,
              cursor: 'pointer',
            }}
          >
            <ChevronLeft size={11} /> Voltar
          </button>
          <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>
            passo 2/3
          </span>
        </div>
        <Card padding={18}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              marginBottom: 14,
            }}
          >
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 8,
                background: toneBg(tone),
                color: toneVar(tone),
                display: 'grid',
                placeItems: 'center',
                border: `1px solid ${toneBd(tone)}`,
              }}
            >
              {ICONS[picked.icon]}
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>
                {picked.label}
              </div>
              <div style={{ fontSize: 12, color: 'var(--fg-2)' }}>
                {picked.detail}
              </div>
            </div>
          </div>
          <div
            style={{
              padding: 12,
              background: 'var(--bg-2)',
              borderRadius: 'var(--r-sm)',
              marginBottom: 14,
              fontSize: 12,
              color: 'var(--fg-1)',
              lineHeight: 1.5,
            }}
          >
            Vou correr no digital twin sandbox: criar um cenário, aplicar{' '}
            {picked.deltas.length}{' '}
            {picked.deltas.length === 1 ? 'delta' : 'deltas'} e simular a
            cascata. Não toca a produção.
          </div>
          <button
            type="button"
            onClick={() => runMutation.mutate(picked)}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              padding: '10px 18px',
              height: 42,
              borderRadius: 11,
              border: '1px solid transparent',
              background: 'var(--red)',
              color: '#fff',
              fontSize: 14,
              fontWeight: 500,
              cursor: 'pointer',
            }}
          >
            <PlayCircle size={14} /> Correr simulação de crise
          </button>
        </Card>
      </>
    );
  }

  // ── Passo 3 — resultado ───────────────────────────────────────────
  return (
    <>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          marginBottom: 14,
        }}
      >
        <button
          type="button"
          onClick={reset}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 5,
            padding: '4px 9px',
            background: 'transparent',
            border: 'none',
            color: 'var(--fg-1)',
            fontSize: 11.5,
            cursor: 'pointer',
          }}
        >
          <ChevronLeft size={11} /> Nova crise
        </button>
        <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>
          cenário {picked.label.toLowerCase()} · sandbox{' '}
          {result.simulationStatus}
        </span>
        {result.scenarioHash ? (
          <span
            className="mono"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 4,
              fontSize: 10.5,
              color: 'var(--fg-3)',
              marginLeft: 'auto',
            }}
            title={result.scenarioHash}
          >
            <Hash size={11} />
            {result.scenarioHash.slice(0, 12)}
          </span>
        ) : null}
      </div>

      <Card padding={18} style={{ marginBottom: 14 }}>
        <div
          style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 10,
              background: toneBg(tone),
              color: toneVar(tone),
              display: 'grid',
              placeItems: 'center',
              border: `1px solid ${toneBd(tone)}`,
              flexShrink: 0,
            }}
          >
            {ICONS[picked.icon]}
          </div>
          <div style={{ flex: 1 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'baseline',
                gap: 10,
                marginBottom: 4,
              }}
            >
              <span
                className="display"
                style={{ fontSize: 18, fontWeight: 600 }}
              >
                {picked.label}
              </span>
              <Tag tone={tone} size="sm">
                {picked.severity}
              </Tag>
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--fg-2)' }}>
              {picked.detail}
            </div>
          </div>
          <div
            style={{
              display: 'flex',
              gap: 16,
              alignItems: 'baseline',
            }}
          >
            <div style={{ textAlign: 'right' }}>
              <div
                className="display tabular"
                style={{
                  fontSize: 24,
                  color: 'var(--red)',
                  fontWeight: 600,
                }}
              >
                −{fmtEuro(picked.deltaEur)}
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.4,
                }}
              >
                se nada fizer
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div
                className="display tabular"
                style={{
                  fontSize: 24,
                  color: 'var(--red)',
                  fontWeight: 600,
                }}
              >
                +{picked.deltaDays}d
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: 'var(--fg-3)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.4,
                }}
              >
                atraso
              </div>
            </div>
          </div>
        </div>
      </Card>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.1fr 1fr',
          gap: 14,
          marginBottom: 14,
        }}
      >
        <Card padding={18}>
          <SectionHeader
            icon={<Clock size={14} />}
            title="Cascata · o que acontece"
            subtitle="Se não houver mitigação"
          />
          <div style={{ position: 'relative', paddingLeft: 18 }}>
            <div
              style={{
                position: 'absolute',
                top: 6,
                bottom: 6,
                left: 4,
                width: 1,
                background: 'var(--bd-1)',
              }}
            />
            {picked.cascade.map((step, i) => (
              <div
                key={i}
                style={{ position: 'relative', paddingBottom: 14 }}
              >
                <div
                  style={{
                    position: 'absolute',
                    left: -18,
                    top: 4,
                    width: 9,
                    height: 9,
                    borderRadius: '50%',
                    background: toneVar(step.tone),
                    border: '2px solid var(--bg-1)',
                  }}
                />
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    marginBottom: 2,
                  }}
                >
                  <span
                    className="mono"
                    style={{ fontSize: 10.5, color: 'var(--fg-3)' }}
                  >
                    {step.t}
                  </span>
                  <Tag tone={step.tone} size="sm">
                    {CASCADE_LABEL[step.tone]}
                  </Tag>
                </div>
                <div style={{ fontSize: 12.5, color: 'var(--fg-0)' }}>
                  {step.what}
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card padding={18}>
          <SectionHeader
            icon={<Check size={14} />}
            title="Validação Spelke · sandbox"
            subtitle="Cópia isolada da BD · 7 axiomas verificados"
          />
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: 8,
            }}
          >
            {SPELKE_AXIOMS.map((axiom) => (
              <div
                key={axiom}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 10px',
                  background: 'var(--bg-2)',
                  borderRadius: 6,
                }}
              >
                <Check size={12} color="var(--green)" />
                <span style={{ fontSize: 11.5, color: 'var(--fg-1)' }}>
                  {axiom}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card padding={18}>
        <SectionHeader
          icon={<Sparkles size={14} />}
          title="Opções de mitigação"
          subtitle="Escolhe uma opção para preparar o plano de execução"
        />
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
        >
          {picked.options.map((o) => {
            const isChosen = chosenOption === o.letter;
            const badgeTone: Tone = o.tone === 'gray' ? 'blue' : o.tone;
            return (
              <div
                key={o.letter}
                onClick={() => setChosenOption(o.letter)}
                style={{
                  padding: 14,
                  background: isChosen ? toneBg(o.tone) : 'var(--bg-2)',
                  border: `1px solid ${
                    isChosen ? toneBd(o.tone) : 'var(--bd-1)'
                  }`,
                  borderRadius: 'var(--r-md)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 14,
                  cursor: 'pointer',
                  position: 'relative',
                }}
              >
                {o.recommended ? (
                  <div
                    style={{
                      position: 'absolute',
                      top: -6,
                      right: 10,
                      padding: '1px 7px',
                      background: 'var(--green)',
                      color: '#000',
                      fontSize: 9,
                      fontWeight: 700,
                      borderRadius: 999,
                      letterSpacing: 0.4,
                    }}
                  >
                    RECOMENDADO
                  </div>
                ) : null}
                <div
                  className="display"
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 8,
                    background: toneBg(badgeTone),
                    color: toneVar(badgeTone),
                    display: 'grid',
                    placeItems: 'center',
                    border: `1px solid ${toneBd(badgeTone)}`,
                    fontWeight: 700,
                    fontSize: 16,
                    flexShrink: 0,
                  }}
                >
                  {o.letter}
                </div>
                <div style={{ flex: 1 }}>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: 10,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: 'var(--fg-0)',
                      }}
                    >
                      {o.label}
                    </span>
                    <span
                      className="tabular"
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: o.cost.startsWith('+€')
                          ? 'var(--orange)'
                          : o.cost.startsWith('−€')
                            ? 'var(--red)'
                            : 'var(--fg-2)',
                      }}
                    >
                      {o.cost}
                    </span>
                  </div>
                  <div
                    style={{
                      fontSize: 11.5,
                      color: 'var(--fg-2)',
                      marginTop: 3,
                    }}
                  >
                    {o.detail}
                  </div>
                </div>
                {isChosen ? (
                  <Tag tone="green" size="sm">
                    Escolhida
                  </Tag>
                ) : (
                  <Tag tone="gray" size="sm">
                    Escolher
                  </Tag>
                )}
              </div>
            );
          })}
        </div>

        {chosenOption ? (
          <div
            className="anim-up"
            style={{
              marginTop: 14,
              padding: '12px 14px',
              background: 'var(--green-bg)',
              border: '1px solid var(--green-bd)',
              borderRadius: 'var(--r-md)',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <Check size={14} color="var(--green)" />
            <span
              style={{ fontSize: 12.5, color: 'var(--fg-0)', flex: 1 }}
            >
              Opção <strong>{chosenOption}</strong> seleccionada · validada
              contra os 7 axiomas na sandbox
            </span>
          </div>
        ) : null}
      </Card>
    </>
  );
}
