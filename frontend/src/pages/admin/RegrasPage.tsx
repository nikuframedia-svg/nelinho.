/**
 * RegrasPage (Sprint Q.17.C)
 * ===========================
 *
 * `/admin/regras` — admin/manager surface for declarative business
 * rules. The operator types in PT-PT what they want; the LLM (Q.17.C
 * ``nl_translator``) translates to a YAML rule constrained by the DSL
 * whitelist (12 events × 9 actions × 8 ops × 7 axioms).
 *
 * The proposed rule appears in a diff modal where the human reviews
 * the YAML, the axioms it preserves, and approves or rejects. Once
 * approved, the rule transitions to ``active`` and the runtime engine
 * (Q.17.D) starts dispatching.
 *
 * Always-human-approval (Luis 2026-05-06): the LLM proposes, the human
 * always approves. No auto-apply path.
 */

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  BookOpen,
  Sparkles,
  CheckCircle2,
  XCircle,
  Pause,
  RotateCcw,
  AlertCircle,
  Send,
  Clock,
  Activity,
  Loader2,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkButton, DarkBadge } from '../../components/dark';
import { yamlPolicyApi, type YamlPolicyRule } from '../../lib/api';

// ─── Status visual mapping ────────────────────────────────────────────────

const STATUS_VARIANTS: Record<
  YamlPolicyRule['status'],
  'success' | 'warning' | 'danger' | 'info' | 'neutral'
> = {
  proposed: 'warning',
  approved: 'info',
  active: 'success',
  suspended: 'neutral',
  rolled_back: 'danger',
  rejected: 'danger',
};

const STATUS_LABELS: Record<YamlPolicyRule['status'], string> = {
  proposed: 'Proposta',
  approved: 'Aprovada',
  active: 'Activa',
  suspended: 'Suspensa',
  rolled_back: 'Revertida',
  rejected: 'Rejeitada',
};

const EVENT_LABELS: Record<string, string> = {
  schedule_propose: 'Schedule proposto',
  schedule_committed: 'Schedule comitado',
  kpi_threshold_crossed: 'KPI cruza limite',
  mold_usage_threshold: 'Molde atinge ciclo',
  worker_absent: 'Operador ausente',
  quality_event_logged: 'Evento qualidade',
  transport_loaded: 'Camião carregado',
  phase_drift_detected: 'Drift de fase',
  decision_pending: 'Decisão pendente',
  rule_rejected: 'Regra rejeitada',
  wip_threshold: 'WIP atinge limite',
  time_trigger: 'Trigger temporal',
};


// ─── YAML preview helper ──────────────────────────────────────────────────

function payloadToYaml(payload: YamlPolicyRule['payload']): string {
  // Simple deterministic YAML serializer for the diff preview.
  // Avoids js-yaml dep — payload is small and well-typed.
  const lines: string[] = [];
  lines.push(`id: ${payload.id}`);
  lines.push(`description: |`);
  for (const ln of payload.description.split('\n')) lines.push(`  ${ln}`);
  lines.push(`when:`);
  lines.push(`  event: ${payload.when.event}`);
  if (payload.when.conditions?.length) {
    lines.push(`  conditions:`);
    for (const c of payload.when.conditions) {
      lines.push(`    - field: ${c.field}`);
      lines.push(`      op: ${c.op}`);
      lines.push(`      value: ${JSON.stringify(c.value)}`);
    }
  } else {
    lines.push(`  conditions: []`);
  }
  lines.push(`then:`);
  for (const a of payload.then) {
    lines.push(`  - action: ${a.action}`);
    if (Object.keys(a.params).length) {
      lines.push(`    params:`);
      for (const [k, v] of Object.entries(a.params)) {
        lines.push(`      ${k}: ${JSON.stringify(v)}`);
      }
    } else {
      lines.push(`    params: {}`);
    }
  }
  if (payload.constraints?.axioms_required?.length) {
    lines.push(`constraints:`);
    lines.push(`  axioms_required:`);
    for (const ax of payload.constraints.axioms_required) {
      lines.push(`    - ${ax}`);
    }
  }
  if (payload.safety) {
    lines.push(`safety:`);
    if (payload.safety.max_fires_per_day !== undefined) {
      lines.push(`  max_fires_per_day: ${payload.safety.max_fires_per_day}`);
    }
    if (payload.safety.expires) {
      lines.push(`  expires: ${payload.safety.expires}`);
    }
  }
  return lines.join('\n');
}

// ─── Components ───────────────────────────────────────────────────────────

function RuleRow({
  rule,
  onSelect,
  selected,
}: {
  rule: YamlPolicyRule;
  onSelect: () => void;
  selected: boolean;
}) {
  const variant = STATUS_VARIANTS[rule.status];
  return (
    <button
      onClick={onSelect}
      className={`w-full text-left rounded-lg border px-4 py-3 transition-all ${
        selected
          ? 'border-accent bg-bg-2'
          : 'border-bd-1 bg-bg-1 hover:border-bd-2 hover:bg-bg-2'
      }`}
    >
      <div className="flex items-start justify-between gap-3 mb-1">
        <span className="font-mono text-xs text-fg-2 truncate flex-1">{rule.rule_id}</span>
        <DarkBadge variant={variant}>{STATUS_LABELS[rule.status]}</DarkBadge>
      </div>
      <p className="text-sm text-fg-0 line-clamp-2 mb-2">{rule.description}</p>
      <div className="flex items-center gap-3 text-xs text-fg-3">
        <span className="inline-flex items-center gap-1">
          <Activity size={12} />
          {EVENT_LABELS[rule.event_type] ?? rule.event_type}
        </span>
        {rule.fire_count > 0 && (
          <span className="inline-flex items-center gap-1">
            <Sparkles size={12} />
            {rule.fire_count}× disparos
          </span>
        )}
      </div>
    </button>
  );
}

/** Q.17.F.3 — shape of a single violation surfaced in the 422 response. */
interface SafetyViolationRow {
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
            {warnings.length > 0 && ` · ${warnings.length} ${warnings.length === 1 ? 'aviso' : 'avisos'}`}
            . Corrige a regra ou propõe uma alternativa.
          </p>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        {errors.map((v, idx) => (
          <div
            key={`err-${idx}`}
            className="rounded border border-red-bd bg-bg-1 px-3 py-2 flex items-start gap-2"
          >
            <XCircle size={14} className="text-red mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="font-mono text-[10px] uppercase tracking-wide text-red mb-0.5">
                {v.code}
              </p>
              <p className="text-xs text-fg-1">{v.detail}</p>
            </div>
          </div>
        ))}
        {warnings.map((v, idx) => (
          <div
            key={`warn-${idx}`}
            className="rounded border border-yellow-bd bg-bg-1 px-3 py-2 flex items-start gap-2"
          >
            <AlertCircle size={14} className="text-yellow mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="font-mono text-[10px] uppercase tracking-wide text-yellow mb-0.5">
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

/** Q.17.F.1 — visual marker for actions whose subsystem isn't wired yet. */
function StubbedActionsBadge({ rule }: { rule: YamlPolicyRule }) {
  // Wiring matrix mirrored from src/governance/yaml_policy/dispatchers.py.
  // Update both when a dispatcher gets wired.
  const WIRED: Record<string, boolean> = {
    alert: true, // Q.17.F.4 — wired to CopilotAlert row
    block: true,
    modify_fitness: true,
    reassign_worker: true, // Q.17.F.7 — wired to governance.decision_run
    propose_maintenance: true, // Q.17.F.6 — wired to governance.decision_run
    notify: true, // Q.17.F.8 — wired to RealtimeBridge SSE fan-out
    set_config: true,
    create_decision: true, // Q.17.F.6 — wired to governance.decision_run
    pause_writes: false,
  };
  const stubbed = (rule.payload.then ?? [])
    .map((step) => step.action)
    .filter((a) => WIRED[a] === false);
  if (stubbed.length === 0) return null;
  return (
    <div className="rounded-md border border-yellow-bd bg-yellow-bg p-3 flex items-start gap-2">
      <AlertCircle size={14} className="text-yellow mt-0.5 shrink-0" />
      <div className="flex-1 text-xs text-fg-1">
        Esta regra usa actions ainda não totalmente ligadas:{' '}
        <span className="font-mono">{Array.from(new Set(stubbed)).join(', ')}</span>. Os disparos
        ficam registados mas o efeito final na fábrica chega quando esses subsistemas forem
        wired (ver wiring matrix em `dispatchers.py`).
      </div>
    </div>
  );
}

function RuleDetailPanel({
  rule,
  onApprove,
  onReject,
  onSuspend,
  onRollback,
  pending,
  violations,
}: {
  rule: YamlPolicyRule;
  onApprove: (reason?: string) => void;
  onReject: (reason: string) => void;
  onSuspend: () => void;
  onRollback: (reason: string) => void;
  pending: boolean;
  violations: SafetyViolationRow[] | null;
}) {
  const [rejectReason, setRejectReason] = useState('');
  const [rollbackReason, setRollbackReason] = useState('');
  const [showRollback, setShowRollback] = useState(false);

  const yaml = payloadToYaml(rule.payload);

  return (
    <DarkCard className="flex flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-fg-0">{rule.description}</h3>
          <p className="font-mono text-xs text-fg-2 mt-1">{rule.rule_id}</p>
        </div>
        <DarkBadge variant={STATUS_VARIANTS[rule.status]}>{STATUS_LABELS[rule.status]}</DarkBadge>
      </div>

      {rule.nl_source && (
        <div className="rounded-md border border-bd-1 bg-bg-2 p-3">
          <p className="text-xs uppercase tracking-wide text-fg-3 mb-1">Pedido original</p>
          <p className="text-sm text-fg-1 italic">"{rule.nl_source}"</p>
        </div>
      )}

      {violations && violations.length > 0 && <ViolationsBanner violations={violations} />}

      {rule.status === 'proposed' && <StubbedActionsBadge rule={rule} />}

      <div>
        <p className="text-xs uppercase tracking-wide text-fg-3 mb-2">YAML produzido pelo LLM</p>
        <pre className="rounded-md border border-bd-1 bg-bg-0 p-3 text-xs text-fg-1 overflow-auto max-h-96">
          <code>{yaml}</code>
        </pre>
      </div>

      {rule.payload.constraints?.axioms_required && rule.payload.constraints.axioms_required.length > 0 && (
        <div>
          <p className="text-xs uppercase tracking-wide text-fg-3 mb-2">Axiomas Spelke preservados</p>
          <div className="flex flex-wrap gap-2">
            {rule.payload.constraints.axioms_required.map((ax) => (
              <DarkBadge key={ax} variant="success">
                <CheckCircle2 size={12} className="inline mr-1" />
                {ax}
              </DarkBadge>
            ))}
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 text-xs text-fg-3">
        {rule.proposed_at && (
          <span className="inline-flex items-center gap-1">
            <Clock size={12} /> proposta {new Date(rule.proposed_at).toLocaleString('pt-PT')}
          </span>
        )}
        {rule.activated_at && (
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 size={12} /> activa desde {new Date(rule.activated_at).toLocaleString('pt-PT')}
          </span>
        )}
        {rule.fire_count > 0 && (
          <span className="inline-flex items-center gap-1">
            <Sparkles size={12} /> {rule.fire_count} disparos
          </span>
        )}
      </div>

      {/* Actions per status */}
      {rule.status === 'proposed' && (
        <div className="flex flex-col gap-3 border-t border-bd-1 pt-4">
          <p className="text-sm text-fg-1">
            Esta regra ainda não está activa. Aprovar fá-la entrar em vigor; rejeitar arquiva-a.
          </p>
          <div className="flex flex-wrap gap-3">
            <DarkButton
              variant="primary"
              onClick={() => onApprove()}
              disabled={pending}
              icon={<CheckCircle2 size={14} />}
            >
              Aprovar e activar
            </DarkButton>
            <div className="flex-1 flex gap-2">
              <input
                type="text"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Razão para rejeitar (obrigatório)…"
                className="flex-1 px-3 py-2 rounded-md border border-bd-1 bg-bg-2 text-fg-0 text-sm placeholder:text-fg-3 focus:outline-none focus:border-accent"
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
        <div className="flex flex-wrap gap-3 border-t border-bd-1 pt-4">
          <DarkButton variant="ghost" onClick={onSuspend} disabled={pending} icon={<Pause size={14} />}>
            Suspender
          </DarkButton>
          {!showRollback ? (
            <DarkButton variant="ghost" onClick={() => setShowRollback(true)} icon={<RotateCcw size={14} />}>
              Reverter…
            </DarkButton>
          ) : (
            <div className="flex-1 flex gap-2">
              <input
                type="text"
                value={rollbackReason}
                onChange={(e) => setRollbackReason(e.target.value)}
                placeholder="Razão para reverter (obrigatório)…"
                className="flex-1 px-3 py-2 rounded-md border border-bd-1 bg-bg-2 text-fg-0 text-sm placeholder:text-fg-3 focus:outline-none focus:border-accent"
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

// ─── Page ─────────────────────────────────────────────────────────────────

/** Q.17.F.3 — parse the structured 422 from /approve so we can render
 * each violation in its own row. The api.ts request() helper throws an
 * Error whose message is the JSON-stringified body when status is 4xx;
 * we try to parse it back here. If parsing fails (regular 5xx etc),
 * fall back to the raw message. */
function parseSafetyViolations(err: Error): SafetyViolationRow[] | null {
  try {
    const parsed = JSON.parse(err.message);
    const detail = parsed?.detail ?? parsed;
    if (detail?.error === 'safety_check_failed' && Array.isArray(detail?.violations)) {
      return detail.violations as SafetyViolationRow[];
    }
  } catch {
    // not JSON — caller renders fallback
  }
  return null;
}

export default function RegrasPage() {
  const queryClient = useQueryClient();
  const [nlInput, setNlInput] = useState('');
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [proposeError, setProposeError] = useState<string | null>(null);
  const [violations, setViolations] = useState<SafetyViolationRow[] | null>(null);

  const rulesQuery = useQuery({
    queryKey: ['yamlPolicy', 'rules'],
    queryFn: () => yamlPolicyApi.list({ limit: 100 }),
    refetchOnWindowFocus: false,
  });

  const detailQuery = useQuery({
    queryKey: ['yamlPolicy', 'rule', selectedRuleId],
    queryFn: () => yamlPolicyApi.get(selectedRuleId!),
    enabled: !!selectedRuleId,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['yamlPolicy'] });
  };

  const proposeMutation = useMutation({
    mutationFn: (nlText: string) => yamlPolicyApi.propose(nlText),
    onSuccess: (data) => {
      setNlInput('');
      setProposeError(null);
      setSelectedRuleId(data.rule.rule_id);
      invalidate();
    },
    onError: (err: Error) => {
      setProposeError(err.message || 'Falha na proposta');
    },
  });

  const approveMutation = useMutation({
    mutationFn: ({ ruleId, reason }: { ruleId: string; reason?: string }) =>
      yamlPolicyApi.approve(ruleId, reason),
    onSuccess: () => {
      setViolations(null);
      invalidate();
    },
    onError: (err: Error) => {
      const v = parseSafetyViolations(err);
      setViolations(v && v.length > 0 ? v : null);
    },
  });
  const rejectMutation = useMutation({
    mutationFn: ({ ruleId, reason }: { ruleId: string; reason: string }) =>
      yamlPolicyApi.reject(ruleId, reason),
    onSuccess: invalidate,
  });
  const suspendMutation = useMutation({
    mutationFn: (ruleId: string) => yamlPolicyApi.suspend(ruleId),
    onSuccess: invalidate,
  });
  const rollbackMutation = useMutation({
    mutationFn: ({ ruleId, reason }: { ruleId: string; reason: string }) =>
      yamlPolicyApi.rollback(ruleId, reason),
    onSuccess: invalidate,
  });

  const transitionPending =
    approveMutation.isPending ||
    rejectMutation.isPending ||
    suspendMutation.isPending ||
    rollbackMutation.isPending;

  const rules = rulesQuery.data?.rules ?? [];
  const selectedRule = detailQuery.data?.rule;

  return (
    <DarkPageLayout
      title="Regras de Negócio"
      subtitle="Escreve em PT, o sistema traduz para policy declarativa. Aprovas, e a regra entra em vigor."
      icon={<BookOpen className="h-6 w-6" />}
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: NL composer + list */}
        <div className="flex flex-col gap-4">
          <DarkCard className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-accent" />
              <h3 className="text-sm font-semibold text-fg-0">Propor nova regra</h3>
            </div>
            <p className="text-xs text-fg-2">
              Descreve em PT-PT o que queres que o sistema faça. Exemplos:
              "Quando o molde K1 7 ML 03 atingir 850 usos, propor manutenção." /
              "Se o Paulo Gomes faltar à 6ªf de manhã, alocar Laminagem ao Carlos."
            </p>
            <textarea
              value={nlInput}
              onChange={(e) => setNlInput(e.target.value)}
              placeholder="Escreve aqui a regra…"
              rows={4}
              className="w-full rounded-md border border-bd-1 bg-bg-2 text-fg-0 placeholder:text-fg-3 px-3 py-2 text-sm focus:outline-none focus:border-accent resize-none"
              disabled={proposeMutation.isPending}
            />
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs text-fg-3">
                A regra é proposta — só entra em vigor depois de seres tu a aprovar.
              </p>
              <DarkButton
                variant="primary"
                onClick={() => proposeMutation.mutate(nlInput.trim())}
                disabled={proposeMutation.isPending || nlInput.trim().length < 4}
                icon={proposeMutation.isPending ? <Loader2 className="animate-spin" size={14} /> : <Send size={14} />}
              >
                {proposeMutation.isPending ? 'A traduzir…' : 'Propor'}
              </DarkButton>
            </div>
            {proposeError && (
              <div className="rounded-md border border-red-bd bg-red-bg p-3 flex items-start gap-2">
                <AlertCircle size={14} className="text-red mt-0.5 shrink-0" />
                <p className="text-xs text-red">{proposeError}</p>
              </div>
            )}
          </DarkCard>

          <DarkCard className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-fg-0">Regras existentes</h3>
              <span className="text-xs text-fg-3">{rules.length} regras</span>
            </div>
            {rulesQuery.isLoading ? (
              <p className="text-sm text-fg-3 text-center py-6">A carregar…</p>
            ) : rules.length === 0 ? (
              <div className="text-center py-6">
                <BookOpen className="h-8 w-8 text-fg-3 mx-auto mb-2" />
                <p className="text-sm text-fg-2">Sem regras ainda. Propõe a primeira acima.</p>
              </div>
            ) : (
              <div className="flex flex-col gap-2 max-h-[60vh] overflow-y-auto">
                {rules.map((r) => (
                  <RuleRow
                    key={r.id}
                    rule={r}
                    onSelect={() => {
                      setSelectedRuleId(r.rule_id);
                      setViolations(null);
                    }}
                    selected={selectedRuleId === r.rule_id}
                  />
                ))}
              </div>
            )}
          </DarkCard>
        </div>

        {/* Right: detail panel */}
        <div>
          {selectedRule ? (
            <RuleDetailPanel
              rule={selectedRule}
              onApprove={(reason) => {
                setViolations(null);
                approveMutation.mutate({ ruleId: selectedRule.rule_id, reason });
              }}
              onReject={(reason) =>
                rejectMutation.mutate({ ruleId: selectedRule.rule_id, reason })
              }
              onSuspend={() => suspendMutation.mutate(selectedRule.rule_id)}
              onRollback={(reason) =>
                rollbackMutation.mutate({ ruleId: selectedRule.rule_id, reason })
              }
              pending={transitionPending}
              violations={violations}
            />
          ) : (
            <DarkCard className="text-center py-16">
              <BookOpen className="h-12 w-12 text-fg-3 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-fg-1 mb-1">
                Selecciona uma regra à esquerda
              </h3>
              <p className="text-sm text-fg-2">
                Ou propõe uma nova — vais ver aqui o YAML que o LLM produz e podes
                aprovar/rejeitar.
              </p>
            </DarkCard>
          )}
        </div>
      </div>
    </DarkPageLayout>
  );
}
