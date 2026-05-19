/**
 * RuleDetailPanel — painel de detalhe da regra seleccionada (Q.52.L).
 *
 * Port do `RuleDetail` do protótipo NELO: cabeçalho com id+estado,
 * axiomas Spelke preservados, aviso de actions stubbed, YAML colorizado,
 * estatísticas reais (disparos do `GET /v1/governance/rule-firings`) e
 * acções dependentes do estado (aprovar/rejeitar/suspender/reverter).
 *
 * As acções de transição são admin-only no backend; o painel surface
 * o 422 estruturado de safety-check num banner de violações.
 */

import { useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  CheckCircle2,
  XCircle,
  Pause,
  RotateCcw,
  AlertCircle,
  Clock,
  Sparkles,
} from 'lucide-react';
import { DarkCard, DarkButton, DarkBadge } from '../dark';
import type { YamlPolicyRule } from '../../lib/api';
import { YamlBlock } from './YamlBlock';
import {
  payloadToYaml,
  stubbedActions,
  STATUS_VARIANTS,
  STATUS_LABELS,
  AXIOM_DESC,
  listRuleFirings,
  FIRING_OUTCOME_LABELS,
  FIRING_OUTCOME_VARIANTS,
} from './ruleHelpers';

/** Q.17.F.3 — uma violação do 422 estruturado do /approve. */
export interface SafetyViolationRow {
  code: string;
  severity: 'error' | 'warning';
  detail: string;
  context?: Record<string, unknown>;
}

function ViolationsBanner({ violations }: { violations: SafetyViolationRow[] }) {
  const errors = violations.filter((v) => v.severity === 'error');
  const warnings = violations.filter((v) => v.severity === 'warning');
  return (
    <div className="rounded-md border border-red-bd bg-red-bg p-4 flex flex-col gap-3">
      <div className="flex items-start gap-2">
        <AlertCircle size={16} className="text-red mt-0.5 shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-red">
            Activação bloqueada por verificações de segurança
          </p>
          <p className="text-xs text-fg-2 mt-1">
            {errors.length} {errors.length === 1 ? 'erro' : 'erros'}
            {warnings.length > 0 &&
              ` · ${warnings.length} ${warnings.length === 1 ? 'aviso' : 'avisos'}`}
            . Corrige a regra ou propõe uma alternativa.
          </p>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {[...errors, ...warnings].map((v, idx) => (
          <div
            key={`${v.code}-${idx}`}
            className={`rounded border bg-bg-1 px-3 py-2 flex items-start gap-2 ${
              v.severity === 'error' ? 'border-red-bd' : 'border-yellow-bd'
            }`}
          >
            {v.severity === 'error' ? (
              <XCircle size={14} className="text-red mt-0.5 shrink-0" />
            ) : (
              <AlertCircle size={14} className="text-yellow mt-0.5 shrink-0" />
            )}
            <div className="flex-1 min-w-0">
              <p
                className={`font-mono text-[10px] uppercase tracking-wide mb-0.5 ${
                  v.severity === 'error' ? 'text-red' : 'text-yellow'
                }`}
              >
                {v.code}
              </p>
              <p className="text-xs text-fg-1">{v.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const labelSm = 'text-[10.5px] uppercase tracking-wide font-semibold text-fg-3';

export interface RuleDetailPanelProps {
  rule: YamlPolicyRule;
  onApprove: () => void;
  onReject: (reason: string) => void;
  onSuspend: () => void;
  onRollback: (reason: string) => void;
  pending: boolean;
  violations: SafetyViolationRow[] | null;
}

export function RuleDetailPanel({
  rule,
  onApprove,
  onReject,
  onSuspend,
  onRollback,
  pending,
  violations,
}: RuleDetailPanelProps): ReactNode {
  const [rejectReason, setRejectReason] = useState('');
  const [rollbackReason, setRollbackReason] = useState('');
  const [showRollback, setShowRollback] = useState(false);

  const stubbed = stubbedActions(rule);
  const axioms = rule.payload.constraints?.axioms_required ?? [];
  const yaml = payloadToYaml(rule.payload);

  // Disparos reais — fecha o "porque é que o sistema fez X" do audit trail.
  const firingsQuery = useQuery({
    queryKey: ['ruleFirings', rule.rule_id],
    queryFn: () => listRuleFirings({ rule_id: rule.rule_id, limit: 20 }),
    refetchOnWindowFocus: false,
  });
  const firings = firingsQuery.data ?? [];

  return (
    <DarkCard className="flex flex-col gap-4">
      {/* Cabeçalho */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-fg-3">{rule.rule_id}</span>
            <DarkBadge variant={STATUS_VARIANTS[rule.status]}>
              {STATUS_LABELS[rule.status]}
            </DarkBadge>
          </div>
          <h3 className="text-base font-medium text-fg-0 leading-snug">{rule.description}</h3>
        </div>
      </div>

      {rule.nl_source && (
        <div className="rounded-md border border-bd-1 bg-bg-2 p-3">
          <p className={`${labelSm} mb-1`}>Pedido original</p>
          <p className="text-sm text-fg-1 italic">"{rule.nl_source}"</p>
        </div>
      )}

      {violations && violations.length > 0 && <ViolationsBanner violations={violations} />}

      {/* Axiomas Spelke */}
      {axioms.length > 0 && (
        <div>
          <p className={`${labelSm} mb-2`}>Axiomas Spelke preservados</p>
          <div className="flex flex-wrap gap-1.5">
            {axioms.map((a) => (
              <div
                key={a}
                className="rounded-md border border-bd-1 bg-bg-2 px-2.5 py-1.5 text-xs"
              >
                <span className="font-mono text-fg-0 font-medium">{a}</span>
                {AXIOM_DESC[a] && <span className="text-fg-3 ml-1.5">{AXIOM_DESC[a]}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Aviso de actions stubbed */}
      {stubbed.length > 0 && (
        <div className="rounded-md border border-yellow-bd bg-yellow-bg p-3 flex items-start gap-2">
          <AlertCircle size={14} className="text-yellow mt-0.5 shrink-0" />
          <div className="flex-1 text-xs text-fg-1">
            <span className="font-semibold text-yellow uppercase tracking-wide text-[11px]">
              Actions não totalmente ligadas
            </span>
            <p className="mt-1">
              Esta regra usa <span className="font-mono">{stubbed.join(', ')}</span>. Os
              disparos ficam registados, mas o efeito final na fábrica chega quando esses
              subsistemas forem wired (ver matriz <span className="font-mono">ACTION_WIRING</span>{' '}
              em <span className="font-mono">dispatchers.py</span>).
            </p>
          </div>
        </div>
      )}

      {/* YAML */}
      <div>
        <p className={`${labelSm} mb-2`}>YAML · DSL fechado</p>
        <YamlBlock text={yaml} />
      </div>

      {/* Estatísticas — disparos reais */}
      <div>
        <p className={`${labelSm} mb-2`}>Estatísticas</p>
        <div className="grid grid-cols-3 gap-2">
          <div className="rounded-md bg-bg-2 p-2.5">
            <div className="text-[10px] text-fg-3">Disparos</div>
            <div className="text-lg font-medium text-fg-0 tabular-nums">{rule.fire_count}</div>
          </div>
          <div className="rounded-md bg-bg-2 p-2.5">
            <div className="text-[10px] text-fg-3">Aceites</div>
            <div className="text-lg font-medium text-green tabular-nums">
              {firings.filter((f) => f.outcome === 'accepted').length}
            </div>
          </div>
          <div className="rounded-md bg-bg-2 p-2.5">
            <div className="text-[10px] text-fg-3">Rejeitados</div>
            <div className="text-lg font-medium text-red tabular-nums">
              {firings.filter((f) => f.outcome === 'rejected').length}
            </div>
          </div>
        </div>
      </div>

      {/* Histórico de disparos */}
      <div>
        <p className={`${labelSm} mb-2`}>Disparos recentes</p>
        {firingsQuery.isLoading ? (
          <p className="text-xs text-fg-3 py-3 text-center">A carregar disparos…</p>
        ) : firingsQuery.isError ? (
          <div className="rounded-md border border-red-bd bg-red-bg p-3 flex items-center justify-between gap-2">
            <p className="text-xs text-red">Falha a obter os disparos desta regra.</p>
            <DarkButton variant="ghost" onClick={() => firingsQuery.refetch()}>
              Tentar novamente
            </DarkButton>
          </div>
        ) : firings.length === 0 ? (
          <p className="text-xs text-fg-3 py-3 text-center">
            Esta regra ainda não disparou.
          </p>
        ) : (
          <div className="flex flex-col gap-1.5 max-h-48 overflow-y-auto">
            {firings.map((f) => (
              <div
                key={f.id}
                className="rounded-md border border-bd-1 bg-bg-2 px-3 py-2 flex items-center gap-3"
              >
                <Sparkles size={12} className="text-fg-3 shrink-0" />
                <span className="text-xs text-fg-1 flex-1 inline-flex items-center gap-1">
                  <Clock size={11} className="text-fg-3" />
                  {new Date(f.fired_at).toLocaleString('pt-PT')}
                </span>
                <span className="text-xs text-fg-3 tabular-nums">{f.fire_count}×</span>
                <DarkBadge variant={FIRING_OUTCOME_VARIANTS[f.outcome] ?? 'neutral'}>
                  {FIRING_OUTCOME_LABELS[f.outcome] ?? f.outcome}
                </DarkBadge>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Acções por estado */}
      {rule.status === 'proposed' && (
        <div className="flex flex-col gap-3 border-t border-bd-1 pt-4">
          <p className="text-sm text-fg-1">
            Esta regra ainda não está activa. Aprovar fá-la entrar em vigor; rejeitar
            arquiva-a. O LLM propõe — és tu que aprovas, sempre.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <DarkButton
              variant="primary"
              onClick={onApprove}
              disabled={pending}
              icon={<CheckCircle2 size={14} />}
            >
              Aprovar e activar
            </DarkButton>
            <div className="flex-1 flex gap-2 min-w-[260px]">
              <input
                type="text"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Razão para rejeitar (obrigatório)…"
                className="flex-1 px-3 py-2 rounded-md border border-bd-1 bg-bg-2 text-slate-900 placeholder:text-slate-400 text-sm focus:outline-none focus:border-accent"
              />
              <DarkButton
                variant="ghost"
                onClick={() => onReject(rejectReason)}
                disabled={pending || rejectReason.trim().length < 4}
                icon={<XCircle size={14} />}
              >
                Rejeitar
              </DarkButton>
            </div>
          </div>
        </div>
      )}

      {rule.status === 'active' && (
        <div className="flex flex-wrap items-center gap-3 border-t border-bd-1 pt-4">
          <DarkButton
            variant="ghost"
            onClick={onSuspend}
            disabled={pending}
            icon={<Pause size={14} />}
          >
            Suspender
          </DarkButton>
          {!showRollback ? (
            <DarkButton
              variant="ghost"
              onClick={() => setShowRollback(true)}
              icon={<RotateCcw size={14} />}
            >
              Reverter…
            </DarkButton>
          ) : (
            <div className="flex-1 flex gap-2 min-w-[260px]">
              <input
                type="text"
                value={rollbackReason}
                onChange={(e) => setRollbackReason(e.target.value)}
                placeholder="Razão para reverter (obrigatório)…"
                className="flex-1 px-3 py-2 rounded-md border border-bd-1 bg-bg-2 text-slate-900 placeholder:text-slate-400 text-sm focus:outline-none focus:border-accent"
              />
              <DarkButton
                variant="ghost"
                onClick={() => onRollback(rollbackReason)}
                disabled={pending || rollbackReason.trim().length < 4}
              >
                Confirmar reversão
              </DarkButton>
            </div>
          )}
        </div>
      )}
    </DarkCard>
  );
}
