/**
 * Q17Panels — 5 panels para tornar visível tudo o que Q.17 YAML faz no backend.
 *
 * 1. Q17AuditFirings    — lista de rule firings com payload + outcome
 * 2. Q17ImpactDashboard — adoption metrics per rule
 * 3. Q17SchemaExplorer  — vocabulário fechado (12 events × 9 actions × 8 ops × 7 axioms)
 * 4. Q17ConflictResolver — alertas de conflitos entre rules
 * 5. Q17AxiomChecklist  — visual dos 7 Spelke axioms preservados/violados
 *
 * Sprint Q.18.ZIP.A.Onda1.
 */

import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  Activity,
  Shield,
  CheckCircle2,
  XCircle,
  ChevronRight,
} from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
const BASE = 'http://127.0.0.1:8001';

// ═══════════════════════════════════════════════════════════════════════════
// Q17 vocabulary closed whitelists (matching backend rule_schema.py)
// ═══════════════════════════════════════════════════════════════════════════

const EVENTS_12 = [
  'mold_use_count_threshold',
  'rework_rate_threshold',
  'overtime_threshold',
  'workforce_skill_gap_detected',
  'schedule_commit_proposed',
  'schedule_commit_rejected',
  'order_due_date_at_risk',
  'phase_capacity_exceeded',
  'quality_dispatch_rate_anomaly',
  'cura_secagem_window_violated',
  'inventory_below_rop',
  'cycle_time_drift_detected',
];

const ACTIONS_9 = [
  { id: 'alert', wired: true, desc: 'Emite alert ao gestor' },
  { id: 'block', wired: true, desc: 'Bloqueia operação (raises 409)' },
  { id: 'modify_fitness', wired: true, desc: 'Ajusta peso CPO scheduler' },
  { id: 'set_config', wired: true, desc: 'Set TenantConfig key' },
  { id: 'reassign_worker', wired: false, desc: 'Stubbed (Q.17.F.8)' },
  { id: 'propose_maintenance', wired: false, desc: 'Stubbed (Q.17.F.7)' },
  { id: 'notify', wired: false, desc: 'Stubbed (sem email/sms)' },
  { id: 'create_decision', wired: false, desc: 'Stubbed (Q.17.F.7)' },
  { id: 'pause_writes', wired: false, desc: 'Stubbed (Q.18.D)' },
];

const CONDITION_OPS_8 = [
  '==', '!=', '>', '>=', '<', '<=', 'in', 'not_in',
];

const SPELKE_AXIOMS_7 = [
  { id: 'capacity_non_negative', label: 'Capacidade ≥ 0', desc: 'Capacidade da fase nunca pode ser negativa' },
  { id: 'precedence_monotonic', label: 'Precedência monotónica', desc: 'Operações seguem ordem BOM (1→2→3)' },
  { id: 'mold_exclusive', label: 'Molde exclusivo', desc: '1 poço = 1 barco em cada momento' },
  { id: 'dual_resource_laminagem', label: 'Dual-resource Laminagem (88.5%)', desc: 'Operadores + molde simultâneos' },
  { id: 'skill_match', label: 'Skill match', desc: 'Operador apto à fase atribuída' },
  { id: 'cura_secagem_gaps', label: 'Cura/secagem 16 transições', desc: 'min_gap_hours entre fases químicas' },
  { id: 'safety_net_baseline', label: 'Safety net ≥ baseline', desc: 'Plano novo nunca pior que baseline' },
];

// ═══════════════════════════════════════════════════════════════════════════
// 1. Q17AuditFirings — lista de rule firings
// ═══════════════════════════════════════════════════════════════════════════

interface RuleFiring {
  id?: string;
  rule_id?: string;
  event_type?: string;
  outcome?: string;
  fire_count?: number;
  payload?: any;
  created_at?: string;
}

async function fetchRuleFirings(): Promise<RuleFiring[]> {
  try {
    const r = await fetch(`${BASE}/v1/governance/rule-firings?limit=50`, { headers: TENANT });
    if (!r.ok) return [];
    const data = await r.json();
    return Array.isArray(data) ? data : (data.items ?? data.firings ?? []);
  } catch {
    return [];
  }
}

export function Q17AuditFirings() {
  const q = useQuery({
    queryKey: ['q17', 'firings'],
    queryFn: fetchRuleFirings,
    staleTime: 30_000,
    retry: 0,
  });
  const items = q.data ?? [];

  return (
    <Panel title="Audit firings — quando regras dispararam" badge={items.length || '—'} flush>
      {q.isLoading ? (
        <div className="px-4 py-6 text-center text-xs" style={{ color: 'var(--fg-3)' }}>
          A carregar firings…
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="Nenhuma regra disparou ainda"
          hint="Quando regras Q.17 forem activadas e detectarem eventos, o histórico aparece aqui (regra, evento, payload, outcome, fire_count)."
          mascot
          size="sm"
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b" style={{ borderColor: 'var(--bd-1)' }}>
              <tr className="text-left uppercase tracking-wider" style={{ color: 'var(--fg-3)', fontSize: 10 }}>
                <th className="px-3 py-2">Quando</th>
                <th className="px-3 py-2">Regra</th>
                <th className="px-3 py-2">Evento</th>
                <th className="px-3 py-2">Outcome</th>
                <th className="px-3 py-2 text-right">Fires</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, 50).map((f, i) => (
                <tr key={f.id ?? i} className="border-b" style={{ borderColor: 'var(--bd-1)' }}>
                  <td className="px-3 py-2 tabular-nums" style={{ color: 'var(--fg-2)' }}>
                    {f.created_at ? new Date(f.created_at).toLocaleString('pt-PT') : '—'}
                  </td>
                  <td className="px-3 py-2 font-mono" style={{ color: 'var(--fg-1)' }}>
                    {(f.rule_id ?? '—').toString().slice(0, 8)}
                  </td>
                  <td className="px-3 py-2" style={{ color: 'var(--fg-2)' }}>
                    {f.event_type ?? '—'}
                  </td>
                  <td className="px-3 py-2">
                    <ZipToneBadge
                      tone={
                        f.outcome === 'accepted'
                          ? 'green'
                          : f.outcome === 'rejected'
                            ? 'red'
                            : f.outcome === 'expired'
                              ? 'gray'
                              : 'blue'
                      }
                      size="sm"
                    >
                      {f.outcome ?? 'proposed'}
                    </ZipToneBadge>
                  </td>
                  <td className="px-3 py-2 tabular-nums text-right" style={{ color: 'var(--fg-1)' }}>
                    {f.fire_count ?? 1}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 2. Q17ImpactDashboard — adoption metrics
// ═══════════════════════════════════════════════════════════════════════════

interface YamlRule {
  id: string;
  name?: string;
  status?: string;
  event_type?: string;
}

async function fetchYamlRules(): Promise<YamlRule[]> {
  try {
    const r = await fetch(`${BASE}/v1/governance/yaml-policy/rules?limit=50`, { headers: TENANT });
    if (!r.ok) return [];
    const data = await r.json();
    return data.rules ?? [];
  } catch {
    return [];
  }
}

async function fetchAdoption(rule_id: string) {
  try {
    const r = await fetch(`${BASE}/v1/governance/rule-firings/adoption?rule_id=${rule_id}`, { headers: TENANT });
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
}

export function Q17ImpactDashboard() {
  const rulesQuery = useQuery({
    queryKey: ['q17', 'rules'],
    queryFn: fetchYamlRules,
    staleTime: 60_000,
    retry: 0,
  });

  const adoptionQuery = useQuery({
    queryKey: ['q17', 'adoption-all', rulesQuery.data?.map((r) => r.id).join(',')],
    queryFn: async () => {
      if (!rulesQuery.data) return new Map();
      const results = await Promise.all(
        rulesQuery.data.slice(0, 20).map(async (r) => [r.id, await fetchAdoption(r.id)] as const),
      );
      return new Map(results);
    },
    enabled: !!rulesQuery.data && rulesQuery.data.length > 0,
    staleTime: 60_000,
    retry: 0,
  });

  const rules = rulesQuery.data ?? [];

  return (
    <Panel title="Impacto das regras — adoption metrics" badge={rules.length || '—'} flush>
      {rulesQuery.isLoading ? (
        <div className="px-4 py-6 text-center text-xs" style={{ color: 'var(--fg-3)' }}>
          A carregar regras…
        </div>
      ) : rules.length === 0 ? (
        <EmptyState
          title="Sem regras Q.17 propostas ainda"
          hint="Quando o gestor (ou LLM) propuser regras YAML e elas forem aprovadas, métricas de adoção aparecem aqui (X disparos, Y aceites, Z rejeições)."
          mascot
          size="sm"
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b" style={{ borderColor: 'var(--bd-1)' }}>
              <tr className="text-left uppercase tracking-wider" style={{ color: 'var(--fg-3)', fontSize: 10 }}>
                <th className="px-3 py-2">Regra</th>
                <th className="px-3 py-2">Estado</th>
                <th className="px-3 py-2">Evento</th>
                <th className="px-3 py-2 text-right">Disparos</th>
                <th className="px-3 py-2 text-right">Aceites</th>
                <th className="px-3 py-2 text-right">Adoção%</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => {
                const ad: any = adoptionQuery.data?.get(r.id);
                const fires = ad?.total_fires ?? 0;
                const accepted = ad?.accepted_count ?? 0;
                const adoption = fires > 0 ? Math.round((accepted / fires) * 100) : null;
                return (
                  <tr key={r.id} className="border-b" style={{ borderColor: 'var(--bd-1)' }}>
                    <td className="px-3 py-2" style={{ color: 'var(--fg-1)' }}>{r.name ?? r.id.slice(0, 8)}</td>
                    <td className="px-3 py-2">
                      <ZipToneBadge tone={r.status === 'active' ? 'green' : 'yellow'} size="sm">
                        {r.status ?? '—'}
                      </ZipToneBadge>
                    </td>
                    <td className="px-3 py-2" style={{ color: 'var(--fg-2)' }}>{r.event_type ?? '—'}</td>
                    <td className="px-3 py-2 tabular-nums text-right" style={{ color: 'var(--fg-1)' }}>{fires}</td>
                    <td className="px-3 py-2 tabular-nums text-right" style={{ color: 'var(--green)' }}>{accepted}</td>
                    <td className="px-3 py-2 tabular-nums text-right" style={{ color: 'var(--fg-1)' }}>
                      {adoption !== null ? `${adoption}%` : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 3. Q17SchemaExplorer — vocabulário fechado (12×9×8×7)
// ═══════════════════════════════════════════════════════════════════════════

export function Q17SchemaExplorer() {
  const [section, setSection] = useState<'events' | 'actions' | 'ops' | 'axioms'>('events');

  return (
    <Panel
      title="Schema explorer — vocabulário fechado Q.17"
      badge={`${EVENTS_12.length}×${ACTIONS_9.length}×${CONDITION_OPS_8.length}×${SPELKE_AXIOMS_7.length}`}
      flush
    >
      <div className="px-4 py-2 border-b" style={{ borderColor: 'var(--bd-1)' }}>
        <div className="flex gap-1.5">
          {(['events', 'actions', 'ops', 'axioms'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setSection(s)}
              className="px-2.5 py-1 rounded text-xs transition-colors"
              style={{
                background: section === s ? 'var(--bg-3)' : 'transparent',
                color: section === s ? 'var(--fg-0)' : 'var(--fg-2)',
                border: `1px solid ${section === s ? 'var(--bd-2)' : 'var(--bd-1)'}`,
              }}
            >
              {s === 'events'
                ? `Events (${EVENTS_12.length})`
                : s === 'actions'
                  ? `Actions (${ACTIONS_9.length})`
                  : s === 'ops'
                    ? `Ops (${CONDITION_OPS_8.length})`
                    : `Axioms (${SPELKE_AXIOMS_7.length})`}
            </button>
          ))}
        </div>
      </div>
      <div className="px-4 py-3">
        {section === 'events' && (
          <ul className="grid grid-cols-2 gap-2">
            {EVENTS_12.map((e) => (
              <li
                key={e}
                className="px-3 py-2 rounded font-mono text-xs"
                style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-1)', color: 'var(--fg-1)' }}
              >
                {e}
              </li>
            ))}
          </ul>
        )}
        {section === 'actions' && (
          <ul className="space-y-1.5">
            {ACTIONS_9.map((a) => (
              <li
                key={a.id}
                className="flex items-center gap-2 px-3 py-2 rounded"
                style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-1)' }}
              >
                <ZipToneBadge tone={a.wired ? 'green' : 'yellow'} size="sm">
                  {a.wired ? '✓ wired' : '⚠ stubbed'}
                </ZipToneBadge>
                <span className="font-mono text-xs" style={{ color: 'var(--fg-0)' }}>{a.id}</span>
                <span className="text-xs" style={{ color: 'var(--fg-2)' }}>· {a.desc}</span>
              </li>
            ))}
          </ul>
        )}
        {section === 'ops' && (
          <ul className="grid grid-cols-4 gap-2">
            {CONDITION_OPS_8.map((o) => (
              <li
                key={o}
                className="px-3 py-2 rounded font-mono text-xs text-center"
                style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-1)', color: 'var(--fg-0)' }}
              >
                {o}
              </li>
            ))}
          </ul>
        )}
        {section === 'axioms' && (
          <ul className="space-y-2">
            {SPELKE_AXIOMS_7.map((ax) => (
              <li
                key={ax.id}
                className="px-3 py-2 rounded"
                style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-1)' }}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Shield size={12} style={{ color: 'var(--blue)' }} />
                  <span className="text-xs font-medium" style={{ color: 'var(--fg-0)' }}>{ax.label}</span>
                </div>
                <div className="text-[11px]" style={{ color: 'var(--fg-2)' }}>{ax.desc}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 4. Q17ConflictResolver — alertas conflitos
// ═══════════════════════════════════════════════════════════════════════════

export function Q17ConflictResolver() {
  const rulesQuery = useQuery({
    queryKey: ['q17', 'rules-conflicts'],
    queryFn: fetchYamlRules,
    staleTime: 60_000,
    retry: 0,
  });
  const rules = rulesQuery.data ?? [];

  // Detectar conflitos: múltiplas regras active no mesmo event_type
  const conflicts = useMemo(() => {
    const byEvent: Record<string, YamlRule[]> = {};
    for (const r of rules) {
      if (r.status !== 'active' || !r.event_type) continue;
      if (!byEvent[r.event_type]) byEvent[r.event_type] = [];
      byEvent[r.event_type].push(r);
    }
    return Object.entries(byEvent)
      .filter(([, rs]) => rs.length > 1)
      .map(([event, rs]) => ({ event, rules: rs }));
  }, [rules]);

  return (
    <Panel title="Conflict resolver — regras potencialmente em conflito" badge={conflicts.length || '0'} flush>
      {rulesQuery.isLoading ? (
        <div className="px-4 py-6 text-center text-xs" style={{ color: 'var(--fg-3)' }}>
          A analisar conflitos…
        </div>
      ) : conflicts.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs flex items-center justify-center gap-2" style={{ color: 'var(--fg-2)' }}>
          <CheckCircle2 size={14} style={{ color: 'var(--green)' }} />
          Sem conflitos detectados — cada event_type tem no máximo 1 regra activa.
        </div>
      ) : (
        <div className="px-4 py-3 space-y-3">
          {conflicts.map(({ event, rules }) => (
            <div
              key={event}
              className="px-3 py-2 rounded"
              style={{ background: 'var(--yellow-bg)', border: '1px solid var(--yellow-bd)' }}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <AlertTriangle size={14} style={{ color: 'var(--yellow)' }} />
                <span className="text-xs font-medium" style={{ color: 'var(--fg-0)' }}>
                  Event <code className="font-mono">{event}</code> tem {rules.length} regras activas
                </span>
              </div>
              <ul className="space-y-1 ml-5">
                {rules.map((r) => (
                  <li key={r.id} className="text-xs flex items-center gap-2" style={{ color: 'var(--fg-1)' }}>
                    <ChevronRight size={10} style={{ color: 'var(--fg-3)' }} />
                    <span className="font-mono">{r.id.slice(0, 8)}</span>
                    <span style={{ color: 'var(--fg-2)' }}>· {r.name ?? '—'}</span>
                  </li>
                ))}
              </ul>
              <div className="text-[11px] mt-1.5 ml-5" style={{ color: 'var(--fg-3)' }}>
                Backend conflict resolver decide ordem de execução (priority + created_at). Para evitar comportamento ambíguo, suspenda regras duplicadas.
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 5. Q17AxiomChecklist — visual dos 7 axiomas (rendering inline em rule preview)
// ═══════════════════════════════════════════════════════════════════════════

interface AxiomChecklistProps {
  /** Lista de axiom_ids requeridos pela rule (constraints.axioms_required no YAML). */
  required?: string[];
  /** Lista de axiom_ids violados (verificação backend). */
  violated?: string[];
}

export function Q17AxiomChecklist({ required = [], violated = [] }: AxiomChecklistProps) {
  return (
    <div
      className="px-3 py-2.5 rounded"
      style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-1)' }}
    >
      <div className="flex items-center gap-2 mb-2">
        <Shield size={12} style={{ color: 'var(--blue)' }} />
        <span className="text-xs font-medium" style={{ color: 'var(--fg-0)' }}>
          7 Spelke axioms — invariants preservados pela regra
        </span>
      </div>
      <ul className="space-y-1">
        {SPELKE_AXIOMS_7.map((ax) => {
          const req = required.includes(ax.id);
          const viol = violated.includes(ax.id);
          return (
            <li key={ax.id} className="flex items-start gap-2 text-xs">
              {viol ? (
                <XCircle size={12} style={{ color: 'var(--red)', flexShrink: 0, marginTop: 2 }} />
              ) : req ? (
                <CheckCircle2 size={12} style={{ color: 'var(--green)', flexShrink: 0, marginTop: 2 }} />
              ) : (
                <span
                  style={{
                    width: 12,
                    height: 12,
                    borderRadius: '50%',
                    border: '1px solid var(--bd-2)',
                    flexShrink: 0,
                    marginTop: 2,
                  }}
                />
              )}
              <div>
                <span style={{ color: viol ? 'var(--red)' : req ? 'var(--fg-0)' : 'var(--fg-3)' }}>
                  {ax.label}
                </span>
                {viol && (
                  <span className="ml-2 text-[10px] font-semibold" style={{ color: 'var(--red)' }}>
                    VIOLADO
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Q17Dashboard — composição dos 4 panels principais (sem axiom checklist
// que é renderizado inline em rule preview)
// ═══════════════════════════════════════════════════════════════════════════

export function Q17Dashboard() {
  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 px-3 py-2 rounded" style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-1)' }}>
        <Activity size={14} style={{ color: 'var(--purple)' }} />
        <div className="flex-1">
          <div className="text-sm font-medium" style={{ color: 'var(--fg-0)' }}>
            Q.17 Logic-as-data — dashboard avançado
          </div>
          <div className="text-xs" style={{ color: 'var(--fg-2)' }}>
            Audit firings · Impact metrics · Schema explorer · Conflict resolver
          </div>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Q17AuditFirings />
        <Q17ImpactDashboard />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Q17SchemaExplorer />
        <Q17ConflictResolver />
      </div>
    </div>
  );
}
