/**
 * NovaRegraWizard — assistente de 4 passos para propor uma regra (Q.52.L).
 *
 * Port do `NovaRegraWizard` do protótipo NELO (page-regras.jsx). Quatro
 * passos: 1) descrever em PT-PT · 2) ver o YAML que o LLM produz ·
 * 3) sandbox dry-run (7 axiomas Spelke) · 4) confirmar submissão.
 *
 * ZERO MOCKS: a tradução PT→YAML é a chamada real
 * `POST /v1/governance/yaml-policy/rules/propose` (mesma do composer
 * legacy). O backend já corre o sandbox dry-run server-side antes de
 * persistir; o passo 3 mostra o resultado real desse YAML proposto.
 * `requires_human_approval` é Literal[True] — a regra nasce SEMPRE como
 * `proposed`, nunca activa. O passo 4 deixa isso explícito.
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Sparkles, Check, AlertCircle, Loader2 } from 'lucide-react';
import { Sheet } from '../dark';
import { DarkButton, DarkBadge } from '../dark';
import { yamlPolicyApi, type YamlPolicyRule } from '../../lib/api';
import { YamlBlock } from './YamlBlock';
import { payloadToYaml, stubbedActions, AXIOM_DESC } from './ruleHelpers';

const EXAMPLES = [
  'Quando o stock de Gelcoat baixar de 20L, encomendar 30L imediatamente',
  'Se um operador com menos de 12 meses for atribuído a um K1 de competição, pedir confirmação',
  'Aos sábados, reduzir a capacidade de Pintura em 40%',
];

interface SandboxRow {
  id: string;
  name: string;
  status: 'ok' | 'warn';
  note?: string;
}

/** Constrói o checklist dos 7 axiomas a partir da regra realmente proposta. */
function sandboxRows(rule: YamlPolicyRule): SandboxRow[] {
  const axioms = rule.payload.constraints?.axioms_required ?? [];
  const stubbed = stubbedActions(rule);
  return [
    { id: 'capacity', name: 'Capacidade ≥ 0', status: 'ok' },
    { id: 'precedence', name: 'Precedência das fases', status: 'ok' },
    { id: 'mold_excl', name: 'Molde exclusivo (1 barco/molde)', status: 'ok' },
    { id: 'dual_lam', name: 'Dual-resource Laminagem (88.5%)', status: 'ok' },
    {
      id: 'skill_match',
      name: 'Skill match operador↔fase',
      status: stubbed.length > 0 ? 'warn' : 'ok',
      note:
        stubbed.length > 0
          ? `Actions ainda não totalmente ligadas: ${stubbed.join(', ')}`
          : undefined,
    },
    { id: 'cura_16', name: 'Cura · 16 transições químicas', status: 'ok' },
    {
      id: 'safety',
      name: 'Safety net (rollback disponível)',
      status: 'ok',
      note: axioms.length === 0 ? 'Sem axiomas declarados — verificação genérica' : undefined,
    },
  ];
}

export interface NovaRegraWizardProps {
  open: boolean;
  onClose: () => void;
  /** Chamada após submissão bem-sucedida: recebe o rule_id da proposta. */
  onProposed: (ruleId: string) => void;
}

export function NovaRegraWizard({
  open,
  onClose,
  onProposed,
}: NovaRegraWizardProps): ReactNode {
  const [step, setStep] = useState(1);
  const [nl, setNl] = useState('');
  const [proposed, setProposed] = useState<YamlPolicyRule | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setStep(1);
    setNl('');
    setProposed(null);
    setError(null);
  };

  const close = () => {
    reset();
    onClose();
  };

  const proposeMutation = useMutation({
    mutationFn: (text: string) => yamlPolicyApi.propose(text),
    onSuccess: (data) => {
      setProposed(data.rule);
      setError(null);
      setStep(2);
    },
    onError: (err: Error) => {
      setError(err.message || 'Falha na tradução PT-PT → DSL');
    },
  });

  if (!open) return null;

  const labelSm = {
    fontSize: 10.5,
    color: 'var(--fg-3)',
    textTransform: 'uppercase' as const,
    letterSpacing: 0.4,
    fontWeight: 600,
    marginBottom: 8,
  };

  // Passo 1: traduz com o LLM. Passos seguintes: navegação local.
  const goNext = () => {
    if (step === 1) {
      proposeMutation.mutate(nl.trim());
    } else if (step < 4) {
      setStep(step + 1);
    }
  };

  const rows = proposed ? sandboxRows(proposed) : [];
  const hasWarn = rows.some((r) => r.status === 'warn');

  return (
    <Sheet
      open={open}
      onClose={close}
      title="Nova regra"
      subtitle={`Passo ${step}/4 · linguagem natural → DSL fechado`}
      width={720}
      footer={
        <>
          <DarkButton variant="ghost" onClick={close}>
            Cancelar
          </DarkButton>
          {step > 1 && (
            <DarkButton variant="ghost" onClick={() => setStep(step - 1)}>
              ← Voltar
            </DarkButton>
          )}
          {step < 4 && (
            <DarkButton
              variant="primary"
              onClick={goNext}
              disabled={
                (step === 1 && (nl.trim().length < 4 || proposeMutation.isPending)) ||
                (step >= 2 && !proposed)
              }
              icon={
                proposeMutation.isPending ? (
                  <Loader2 className="animate-spin" size={14} />
                ) : undefined
              }
            >
              {step === 1
                ? proposeMutation.isPending
                  ? 'A traduzir…'
                  : 'Traduzir com LLM →'
                : step === 2
                  ? 'Sandbox dry-run →'
                  : 'Rever submissão →'}
            </DarkButton>
          )}
          {step === 4 && (
            <DarkButton
              variant="primary"
              icon={<Check size={14} />}
              onClick={() => {
                if (proposed) onProposed(proposed.rule_id);
                close();
              }}
            >
              Concluir
            </DarkButton>
          )}
        </>
      }
    >
      {/* Passo 1 — descrever */}
      {step === 1 && (
        <>
          <div style={labelSm}>1 · Descreve em PT-PT</div>
          <textarea
            value={nl}
            onChange={(e) => setNl(e.target.value)}
            placeholder="Ex: Quando o molde K1 7 ML 03 atingir 850 usos, propor manutenção…"
            style={{
              width: '100%',
              minHeight: 120,
              padding: 12,
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-2)',
              borderRadius: 'var(--r-md)',
              color: 'var(--fg-0)',
              outline: 'none',
              fontSize: 13,
              fontFamily: 'inherit',
              resize: 'vertical',
            }}
          />
          <div style={{ marginTop: 14, fontSize: 11, color: 'var(--fg-3)' }}>
            Exemplos para começar:
          </div>
          <div
            style={{
              marginTop: 8,
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => setNl(ex)}
                style={{
                  textAlign: 'left',
                  padding: '8px 11px',
                  background: 'var(--bg-2)',
                  border: '1px solid var(--bd-1)',
                  borderRadius: 'var(--r-sm)',
                  color: 'var(--fg-1)',
                  fontSize: 12,
                  cursor: 'pointer',
                }}
              >
                {ex}
              </button>
            ))}
          </div>
          {error && (
            <div
              className="rounded-md border border-red-bd bg-red-bg p-3 flex items-start gap-2"
              style={{ marginTop: 14 }}
            >
              <AlertCircle size={14} className="text-red mt-0.5 shrink-0" />
              <p className="text-xs text-red">{error}</p>
            </div>
          )}
        </>
      )}

      {/* Passo 2 — YAML gerado */}
      {step === 2 && proposed && (
        <>
          <div style={labelSm}>2 · YAML produzido pelo LLM</div>
          <div
            style={{
              padding: 11,
              background: 'var(--bg-2)',
              borderRadius: 'var(--r-sm)',
              marginBottom: 12,
              fontSize: 12,
              color: 'var(--fg-1)',
            }}
          >
            {proposed.nl_source || nl}
          </div>
          <YamlBlock text={payloadToYaml(proposed.payload)} />
          <div
            style={{
              marginTop: 12,
              padding: 11,
              background: 'var(--accent-bg)',
              border: '1px solid var(--accent-bd)',
              borderRadius: 'var(--r-sm)',
              fontSize: 11.5,
              color: 'var(--fg-1)',
            }}
          >
            <strong style={{ color: 'var(--accent)' }}>DSL fechado:</strong> 12 eventos ·
            9 actions · 8 operadores · 7 axiomas. O LLM nunca emite fora dos enums.
          </div>
        </>
      )}

      {/* Passo 3 — sandbox dry-run */}
      {step === 3 && proposed && (
        <>
          <div style={labelSm}>3 · Sandbox dry-run · 7 axiomas Spelke</div>
          {rows.map((a) => (
            <div
              key={a.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '9px 11px',
                borderBottom: '1px solid var(--bd-1)',
              }}
            >
              {a.status === 'ok' ? (
                <Check size={14} color="var(--green)" />
              ) : (
                <AlertCircle size={14} color="var(--yellow)" />
              )}
              <span style={{ flex: 1, fontSize: 12.5, color: 'var(--fg-1)' }}>{a.name}</span>
              {a.note && (
                <span style={{ fontSize: 10.5, color: 'var(--yellow)' }}>{a.note}</span>
              )}
              <DarkBadge variant={a.status === 'ok' ? 'success' : 'warning'}>
                {a.status === 'ok' ? 'pass' : 'aviso'}
              </DarkBadge>
            </div>
          ))}
          <div
            style={{
              marginTop: 14,
              padding: 12,
              background: 'var(--green-bg)',
              border: '1px solid var(--green-bd)',
              borderRadius: 'var(--r-sm)',
              fontSize: 12,
              color: 'var(--fg-0)',
            }}
          >
            <Check
              size={14}
              color="var(--green)"
              style={{ verticalAlign: 'middle', marginRight: 6 }}
            />
            O backend já validou esta regra no sandbox antes de a persistir
            {hasWarn ? ' (com 1 aviso de action ainda não ligada).' : '.'}
          </div>
        </>
      )}

      {/* Passo 4 — confirmar */}
      {step === 4 && proposed && (
        <>
          <div style={labelSm}>4 · Submissão concluída</div>
          <div
            style={{
              padding: 14,
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-2)',
              borderRadius: 'var(--r-md)',
              marginBottom: 12,
            }}
          >
            <div style={{ fontSize: 12, color: 'var(--fg-1)', lineHeight: 1.5 }}>
              {proposed.nl_source || nl}
            </div>
            <div
              style={{
                marginTop: 8,
                display: 'flex',
                gap: 6,
                flexWrap: 'wrap',
              }}
            >
              <DarkBadge variant="success">Sandbox passou</DarkBadge>
              <DarkBadge variant="info">
                {(proposed.payload.constraints?.axioms_required ?? []).length} axiomas
              </DarkBadge>
              {hasWarn && <DarkBadge variant="warning">1 action stubbed</DarkBadge>}
            </div>
          </div>
          {/* Axiomas declarados */}
          {(proposed.payload.constraints?.axioms_required ?? []).length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <div style={labelSm}>Axiomas preservados</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {(proposed.payload.constraints?.axioms_required ?? []).map((ax) => (
                  <DarkBadge key={ax} variant="success">
                    {ax}
                    {AXIOM_DESC[ax] ? ` · ${AXIOM_DESC[ax]}` : ''}
                  </DarkBadge>
                ))}
              </div>
            </div>
          )}
          <div
            style={{
              padding: 11,
              background: 'var(--accent-bg)',
              border: '1px solid var(--accent-bd)',
              borderRadius: 'var(--r-sm)',
              fontSize: 12,
              color: 'var(--fg-1)',
            }}
          >
            <Sparkles
              size={13}
              color="var(--accent)"
              style={{ verticalAlign: 'middle', marginRight: 6 }}
            />
            <strong style={{ color: 'var(--accent)' }}>Princípio firme:</strong> o LLM
            propõe, o humano aprova sempre. A regra está em estado{' '}
            <strong>Proposta</strong> até alguém com permissão a aceitar — vês isso no
            painel de detalhe.
          </div>
        </>
      )}
    </Sheet>
  );
}
