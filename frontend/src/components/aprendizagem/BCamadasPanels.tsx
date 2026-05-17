/**
 * BCamadasPanels — visualizações para as 4 Camadas de Aprendizagem (B).
 *
 * 1. CamadasOverview — strip 4 cards (cada camada com status + métrica chave)
 * 2. Camada2Weights — chart linhas adaptive weights history
 * 3. Camada3DPOCounter — counter "X/500 pares acumulados" + breakdown
 * 4. Camada4ABLPanel — research panel com pair counts day-by-day
 *
 * Sprint Q.18.ZIP.B.Onda2.
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Layers, Brain, Database, FlaskConical } from 'lucide-react';
import { Panel, ZipToneBadge, EmptyState } from '../dark';
import { getApiBase } from '../../lib/api';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const BASE = getApiBase();
const DPO_TARGET = 500;

interface PreferenceRule {
  id: string;
  rule_type?: string;
  status?: string;
  confidence?: number;
}

interface WeightHistory {
  entries: Array<{
    version?: string;
    weights?: Record<string, number>;
    promoted_at?: string;
  }>;
}

interface LearningPairs {
  total_pairs: number;
  eligible_for_dpo: number;
  total_commits_with_rejection: number;
  by_category: Record<string, number>;
  by_weekday: Record<string, number>;
  last_30d: { commits: number; pairs: number; eligible: number };
  last_90d: { commits: number; pairs: number; eligible: number };
  abl_pairs_today: number;
  min_reason_len: number;
}

interface AdapterStatus {
  active_version: string | null;
  promoted_at: string | null;
  promoted_by: string | null;
  reason: string | null;
  intent_match_rate: number | null;
  safety_violations_count: number | null;
  has_previous: boolean;
}

async function fetchPreferenceRules(): Promise<PreferenceRule[]> {
  try {
    const r = await fetch(`${BASE}/v1/governance/preference-rules?limit=100`, { headers: TENANT });
    if (!r.ok) return [];
    const d = await r.json();
    return Array.isArray(d) ? d : (d.items ?? d.rules ?? []);
  } catch { return []; }
}

async function fetchWeightHistory(): Promise<WeightHistory> {
  try {
    const r = await fetch(`${BASE}/v1/governance/learning/weights/history?limit=20`, { headers: TENANT });
    if (!r.ok) return { entries: [] };
    return await r.json();
  } catch { return { entries: [] }; }
}

async function fetchLearningPairs(): Promise<LearningPairs | null> {
  try {
    const r = await fetch(`${BASE}/v1/governance/learning/pairs`, { headers: TENANT });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

async function fetchAdapterStatus(): Promise<AdapterStatus | null> {
  try {
    const r = await fetch(`${BASE}/v1/governance/learning/adapter`, { headers: TENANT });
    if (!r.ok) return null;
    return await r.json();
  } catch { return null; }
}

// ═══════════════════════════════════════════════════════════════════════════
// CamadasOverview — strip de 4 cards
// ═══════════════════════════════════════════════════════════════════════════

export function CamadasOverview() {
  const rulesQuery = useQuery({ queryKey: ['b', 'pref-rules'], queryFn: fetchPreferenceRules, staleTime: 60_000, retry: 0 });
  const weightsQuery = useQuery({ queryKey: ['b', 'weight-history'], queryFn: fetchWeightHistory, staleTime: 60_000, retry: 0 });
  const pairsQuery = useQuery({ queryKey: ['b', 'pairs'], queryFn: fetchLearningPairs, staleTime: 60_000, retry: 0 });
  const adapterQuery = useQuery({ queryKey: ['b', 'adapter'], queryFn: fetchAdapterStatus, staleTime: 60_000, retry: 0 });

  const c1Count = (rulesQuery.data ?? []).length;
  const c1Active = (rulesQuery.data ?? []).filter((r) => r.status === 'confirmed' || r.status === 'active').length;
  const c2Versions = (weightsQuery.data?.entries ?? []).length;
  const c3Pairs = pairsQuery.data?.total_pairs ?? 0;
  const c3Eligible = pairsQuery.data?.eligible_for_dpo ?? 0;
  const c4AblToday = pairsQuery.data?.abl_pairs_today ?? 0;
  const c3Pct = Math.min(100, Math.round((c3Eligible / DPO_TARGET) * 100));

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 14 }}>
      <CamadaCard
        n={1}
        icon={<Layers size={14} />}
        label="Camada 1 — Regras"
        value={c1Count.toString()}
        sub={`${c1Active} confirmadas / ${c1Count} detectadas`}
        tone="green"
      />
      <CamadaCard
        n={2}
        icon={<Brain size={14} />}
        label="Camada 2 — Pesos"
        value={c2Versions.toString()}
        sub={c2Versions > 0 ? `${c2Versions} versões fitness` : 'Sem pesos aprendidos'}
        tone={c2Versions > 0 ? 'blue' : 'gray'}
      />
      <CamadaCard
        n={3}
        icon={<Database size={14} />}
        label="Camada 3 — DPO"
        value={`${c3Eligible}/${DPO_TARGET}`}
        sub={`${c3Pairs} pares total · ${c3Pct}% para fine-tune`}
        tone={c3Pct >= 100 ? 'green' : c3Pct >= 50 ? 'yellow' : 'gray'}
      />
      <CamadaCard
        n={4}
        icon={<FlaskConical size={14} />}
        label="Camada 4 — ABL"
        value={c4AblToday.toString()}
        sub={adapterQuery.data?.active_version ? `Adapter ${adapterQuery.data.active_version}` : 'Sem adapter activo'}
        tone="purple"
      />
    </div>
  );
}

function CamadaCard({
  n,
  icon,
  label,
  value,
  sub,
  tone,
}: {
  n: number;
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  tone: 'green' | 'blue' | 'yellow' | 'gray' | 'purple';
}) {
  return (
    <div
      style={{
        padding: 16,
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <div
          style={{
            width: 22,
            height: 22,
            borderRadius: 'var(--r-sm)',
            background: `var(--${tone}-bg)`,
            color: `var(--${tone})`,
            border: `1px solid var(--${tone}-bd)`,
            display: 'grid',
            placeItems: 'center',
            fontSize: 10,
            fontWeight: 700,
          }}
        >
          {n}
        </div>
        <span style={{ fontSize: 11, color: 'var(--fg-2)' }}>{icon}</span>
        <span className="text-xs font-medium" style={{ color: 'var(--fg-1)' }}>{label}</span>
      </div>
      <div className="tabular-nums" style={{ fontSize: 24, fontWeight: 700, color: `var(--${tone})`, lineHeight: 1 }}>
        {value}
      </div>
      <div className="text-[11px] mt-1" style={{ color: 'var(--fg-3)' }}>{sub}</div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Camada2Weights — chart adaptive weights history
// ═══════════════════════════════════════════════════════════════════════════

export function Camada2Weights() {
  const q = useQuery({ queryKey: ['b', 'c2-weights'], queryFn: fetchWeightHistory, staleTime: 60_000, retry: 0 });
  const entries = q.data?.entries ?? [];

  // Extract all weight keys
  const allKeys = useMemo(() => {
    const set = new Set<string>();
    for (const e of entries) {
      Object.keys(e.weights ?? {}).forEach((k) => set.add(k));
    }
    return Array.from(set).sort();
  }, [entries]);

  return (
    <Panel title="Camada 2 — Adaptive fitness weights (evolução)" badge={entries.length || '—'} flush>
      {q.isLoading ? (
        <div className="px-4 py-6 text-center text-xs" style={{ color: 'var(--fg-3)' }}>A carregar histórico…</div>
      ) : entries.length === 0 ? (
        <EmptyState
          title="Sem pesos aprendidos ainda"
          hint="A Camada 2 ajusta os pesos da fitness function (makespan/tardiness/setup/quality/throughput/idle) com base nas tuas decisões. Quando tiveres ≥10 commits aprovados, novos pesos são propostos automaticamente."
          mascot
          size="sm"
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="border-b" style={{ borderColor: 'var(--bd-1)' }}>
              <tr className="text-left uppercase tracking-wider" style={{ color: 'var(--fg-3)', fontSize: 10 }}>
                <th className="px-3 py-2">Versão</th>
                <th className="px-3 py-2">Promovido</th>
                {allKeys.map((k) => (
                  <th key={k} className="px-2 py-2 text-right">{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <tr key={i} className="border-b" style={{ borderColor: 'var(--bd-1)' }}>
                  <td className="px-3 py-2 font-mono" style={{ color: 'var(--fg-1)' }}>{e.version ?? '—'}</td>
                  <td className="px-3 py-2" style={{ color: 'var(--fg-2)' }}>
                    {e.promoted_at ? new Date(e.promoted_at).toLocaleDateString('pt-PT') : '—'}
                  </td>
                  {allKeys.map((k) => (
                    <td key={k} className="px-2 py-2 tabular-nums text-right" style={{ color: 'var(--fg-1)' }}>
                      {e.weights?.[k] !== undefined ? Number(e.weights[k]).toFixed(2) : '—'}
                    </td>
                  ))}
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
// Camada3DPOCounter — "X/500 pares acumulados"
// ═══════════════════════════════════════════════════════════════════════════

export function Camada3DPOCounter() {
  const q = useQuery({ queryKey: ['b', 'c3-pairs'], queryFn: fetchLearningPairs, staleTime: 60_000, retry: 0 });
  const data = q.data;

  const eligible = data?.eligible_for_dpo ?? 0;
  const pct = Math.min(100, Math.round((eligible / DPO_TARGET) * 100));
  const tone = pct >= 100 ? 'green' : pct >= 50 ? 'yellow' : 'gray';

  return (
    <Panel title="Camada 3 — DPO RL pairs (preferência humana)" badge={data ? `${eligible}/${DPO_TARGET}` : '—'} flush>
      {q.isLoading ? (
        <div className="px-4 py-6 text-center text-xs" style={{ color: 'var(--fg-3)' }}>A carregar pares…</div>
      ) : !data ? (
        <EmptyState title="Endpoint /v1/governance/learning/pairs indisponível" hint="" mascot size="sm" />
      ) : (
        <div className="px-4 py-4 space-y-4">
          {/* Big counter */}
          <div>
            <div className="flex items-baseline gap-2 tabular-nums">
              <span style={{ fontSize: 36, fontWeight: 700, color: `var(--${tone})`, lineHeight: 1 }}>{eligible}</span>
              <span style={{ fontSize: 14, color: 'var(--fg-3)' }}>/ {DPO_TARGET} pares para fine-tune</span>
            </div>
            <div className="text-xs mt-1" style={{ color: 'var(--fg-2)' }}>
              {data.total_pairs} pares total · {data.total_commits_with_rejection} commits com rejeição · {pct}% completo
            </div>
            <div
              style={{
                height: 8,
                background: 'var(--bg-3)',
                borderRadius: 4,
                marginTop: 10,
                overflow: 'hidden',
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: '100%',
                  background: `var(--${tone})`,
                  transition: 'width 0.3s ease',
                }}
              />
            </div>
            <div className="text-[11px] mt-2" style={{ color: 'var(--fg-3)' }}>
              {pct < 100
                ? `Faltam ${DPO_TARGET - eligible} pares elegíveis (motivo ≥${data.min_reason_len} chars) para activar fine-tune QLoRA + DPO.`
                : 'Pronto para fine-tune. Próximo job DPO no próximo ciclo trimestral.'}
            </div>
          </div>

          {/* 30d / 90d split */}
          <div className="grid grid-cols-2 gap-3">
            <div
              style={{
                padding: '10px 12px',
                background: 'var(--bg-2)',
                border: '1px solid var(--bd-1)',
                borderRadius: 'var(--r-md)',
              }}
            >
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>Últimos 30 dias</div>
              <div className="text-sm font-medium tabular-nums mt-1" style={{ color: 'var(--fg-0)' }}>
                {data.last_30d.eligible} elegíveis
              </div>
              <div className="text-[11px]" style={{ color: 'var(--fg-2)' }}>
                {data.last_30d.commits} commits · {data.last_30d.pairs} pares
              </div>
            </div>
            <div
              style={{
                padding: '10px 12px',
                background: 'var(--bg-2)',
                border: '1px solid var(--bd-1)',
                borderRadius: 'var(--r-md)',
              }}
            >
              <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>Últimos 90 dias</div>
              <div className="text-sm font-medium tabular-nums mt-1" style={{ color: 'var(--fg-0)' }}>
                {data.last_90d.eligible} elegíveis
              </div>
              <div className="text-[11px]" style={{ color: 'var(--fg-2)' }}>
                {data.last_90d.commits} commits · {data.last_90d.pairs} pares
              </div>
            </div>
          </div>

          {/* By category */}
          {Object.keys(data.by_category).length > 0 && (
            <div>
              <div className="text-[10px] uppercase tracking-wider mb-1.5" style={{ color: 'var(--fg-3)' }}>Por categoria de rejeição</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(data.by_category).map(([cat, n]) => (
                  <ZipToneBadge key={cat} tone="blue" size="sm">
                    {cat}: {n}
                  </ZipToneBadge>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Camada4ABLPanel — research panel
// ═══════════════════════════════════════════════════════════════════════════

export function Camada4ABLPanel() {
  const pairsQuery = useQuery({ queryKey: ['b', 'c4-pairs'], queryFn: fetchLearningPairs, staleTime: 60_000, retry: 0 });
  const adapterQuery = useQuery({ queryKey: ['b', 'c4-adapter'], queryFn: fetchAdapterStatus, staleTime: 60_000, retry: 0 });

  const ablToday = pairsQuery.data?.abl_pairs_today ?? 0;
  const adapter = adapterQuery.data;

  return (
    <Panel title="Camada 4 — ABL kit (research)" flush>
      <div className="px-4 py-4 space-y-3">
        <div className="text-xs" style={{ color: 'var(--fg-2)', lineHeight: 1.5 }}>
          <strong style={{ color: 'var(--fg-0)' }}>ABL kit</strong> = Ablation Kit. Pipeline de
          treino que remove cada feature do DAG sequencialmente para medir
          impacto causal individual. Permite descobrir quais variáveis movem
          mesmo o KPI vs ruído.
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div
            style={{
              padding: '10px 12px',
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-md)',
            }}
          >
            <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>Pares ABL hoje</div>
            <div className="text-2xl font-bold tabular-nums mt-1" style={{ color: 'var(--purple)' }}>{ablToday}</div>
            <div className="text-[11px]" style={{ color: 'var(--fg-3)' }}>Acumulados últimas 24h</div>
          </div>
          <div
            style={{
              padding: '10px 12px',
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-md)',
            }}
          >
            <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>Adapter activo</div>
            <div className="text-sm font-medium font-mono mt-1" style={{ color: adapter?.active_version ? 'var(--green)' : 'var(--fg-3)' }}>
              {adapter?.active_version ?? '—'}
            </div>
            <div className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
              {adapter?.promoted_at ? `Promovido ${new Date(adapter.promoted_at).toLocaleDateString('pt-PT')}` : 'Sem adapter promovido'}
            </div>
          </div>
        </div>

        {adapter?.intent_match_rate !== null && adapter?.intent_match_rate !== undefined && (
          <div
            style={{
              padding: '10px 12px',
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-md)',
            }}
          >
            <div className="text-[10px] uppercase tracking-wider" style={{ color: 'var(--fg-3)' }}>Intent match rate</div>
            <div className="text-lg font-bold tabular-nums mt-1" style={{ color: 'var(--green)' }}>
              {Math.round(adapter.intent_match_rate * 100)}%
            </div>
            <div className="text-[11px]" style={{ color: 'var(--fg-3)' }}>
              {adapter.safety_violations_count ?? 0} violações safety detectadas
            </div>
          </div>
        )}

        <div
          style={{
            padding: '10px 12px',
            background: 'var(--purple-bg)',
            border: '1px solid var(--purple-bd)',
            borderRadius: 'var(--r-md)',
            fontSize: 11,
            color: 'var(--fg-1)',
          }}
        >
          <strong style={{ color: 'var(--purple)' }}>Research POC.</strong> Quando 500+ pares ABL
          forem acumulados, próximo ciclo trimestral re-treina o adapter
          com novos pesos causais. Operadores nunca vêem este loop directo.
        </div>
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// BCamadasDashboard — composição
// ═══════════════════════════════════════════════════════════════════════════

export function BCamadasDashboard() {
  return (
    <div className="space-y-5">
      <CamadasOverview />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Camada3DPOCounter />
        <Camada4ABLPanel />
      </div>
      <Camada2Weights />
    </div>
  );
}
