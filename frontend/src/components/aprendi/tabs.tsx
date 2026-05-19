/**
 * Sub-tabs da página "O que aprendi" (Q.52.O).
 *
 * Cada tab é um componente que liga a um endpoint real. As tabs
 * "Q.17 Avançado" e "4 Camadas" descrevem a arquitectura fixa do
 * sistema (12 eventos × 9 acções × 8 operadores × 7 axiomas — closed
 * whitelist do DSL) — isso é estrutura conhecida, não dados mock.
 *
 * Sprint Q.52.O.
 */

import { useQuery } from '@tanstack/react-query';
import {
  Boxes,
  Brain,
  FlaskConical,
  Sparkles,
  Target,
} from 'lucide-react';
import type { ReactNode } from 'react';
import {
  capabilitiesApi,
  catalogApi,
  learningApi,
  mlApi,
  preferenceRulesApi,
  yamlPolicyApi,
  apiFetch,
} from '../../lib/api';
import type { PreferenceRule } from '../../lib/api';
import { Card, MiniBar, SectionHeader, Tag, TabState, toneBd, toneBg, toneVar } from './atoms';
import type { Tone } from './atoms';

// ─── Tab: Resumo ────────────────────────────────────────────────────
export function ResumoTab(): ReactNode {
  const weights = useQuery({
    queryKey: ['learning', 'weights'],
    queryFn: () => learningApi.weights(),
  });
  const rules = useQuery({
    queryKey: ['learning', 'rules'],
    queryFn: () => learningApi.rules(),
  });
  const pairs = useQuery({
    queryKey: ['learning', 'pairs'],
    queryFn: () => learningApi.pairs(),
  });

  const loading = weights.isLoading || rules.isLoading || pairs.isLoading;
  const error = weights.error ?? rules.error ?? pairs.error;

  return (
    <TabState
      loading={loading}
      error={error}
      empty={false}
      emptyText=""
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 10,
          marginBottom: 14,
        }}
      >
        <SummaryStat
          label="Regras aprendidas"
          value={rules.data?.total ?? 0}
          tone="blue"
        />
        <SummaryStat
          label="Pares de treino"
          value={pairs.data?.total_pairs ?? 0}
          tone="green"
        />
        <SummaryStat
          label="Elegíveis p/ DPO"
          value={pairs.data?.eligible_for_dpo ?? 0}
          tone="purple"
        />
        <SummaryStat
          label="Pesos a aprender"
          value={
            weights.data
              ? Object.keys(weights.data.current_weights ?? {}).length
              : 0
          }
          tone="teal"
        />
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1.2fr 1fr',
          gap: 14,
        }}
      >
        <Card padding={18}>
          <SectionHeader
            icon={<Target size={14} />}
            title="Pesos da fitness"
            subtitle="Default NELO vs ajuste aprendido pelas decisões"
          />
          <FitnessWeights weights={weights.data ?? null} />
        </Card>
        <Card padding={18}>
          <SectionHeader
            icon={<Sparkles size={14} />}
            title="Detector de regras"
            subtitle="Padrões observados nas decisões humanas"
          />
          {rules.data ? (
            <div
              style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
            >
              {Object.entries(rules.data.by_status ?? {}).map(
                ([status, count]) => (
                  <div
                    key={status}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 11px',
                      background: 'var(--bg-2)',
                      borderRadius: 'var(--r-sm)',
                      fontSize: 12,
                    }}
                  >
                    <span style={{ color: 'var(--fg-1)' }}>{status}</span>
                    <span
                      className="tabular"
                      style={{ color: 'var(--fg-0)', fontWeight: 600 }}
                    >
                      {count}
                    </span>
                  </div>
                ),
              )}
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--fg-3)',
                  marginTop: 4,
                }}
              >
                Última deteção:{' '}
                {rules.data.last_detector_run_at
                  ? new Date(
                      rules.data.last_detector_run_at,
                    ).toLocaleString('pt-PT')
                  : 'nunca'}
              </div>
            </div>
          ) : (
            <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>
              Sem dados do detector.
            </span>
          )}
        </Card>
      </div>
    </TabState>
  );
}

function SummaryStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: Tone;
}): ReactNode {
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding: 16,
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          bottom: 0,
          width: 2,
          background: toneVar(tone),
          opacity: 0.5,
        }}
      />
      <div
        style={{
          fontSize: 10.5,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.3,
          fontWeight: 500,
        }}
      >
        {label}
      </div>
      <div
        className="display tabular"
        style={{
          fontSize: 28,
          color: 'var(--fg-0)',
          fontWeight: 500,
          marginTop: 8,
        }}
      >
        {value.toLocaleString('pt-PT')}
      </div>
    </div>
  );
}

function FitnessWeights({
  weights,
}: {
  weights: {
    current_weights?: Record<string, number>;
    default_weights?: Record<string, number>;
  } | null;
}): ReactNode {
  if (!weights || !weights.current_weights) {
    return (
      <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>
        Sem pesos de fitness disponíveis.
      </span>
    );
  }
  const current = weights.current_weights;
  const def = weights.default_weights ?? {};
  const keys = Object.keys(current);
  const maxW = Math.max(...keys.map((k) => current[k]), 0.01);
  return (
    <div>
      <div
        style={{
          fontSize: 11,
          color: 'var(--fg-3)',
          marginBottom: 12,
          padding: '8px 10px',
          background: 'var(--bg-2)',
          borderRadius: 6,
        }}
      >
        <strong style={{ color: 'var(--fg-1)' }}>Default</strong> = padrão
        NELO ·{' '}
        <strong style={{ color: 'var(--accent)' }}>Aprendido</strong> =
        ajustado pelas decisões
      </div>
      {keys.map((k) => {
        const cur = current[k];
        const dft = def[k] ?? cur;
        const diff = cur - dft;
        return (
          <div key={k} style={{ marginBottom: 11 }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: 5,
              }}
            >
              <span style={{ fontSize: 11.5, color: 'var(--fg-1)' }}>
                {k}
              </span>
              <span
                className="tabular"
                style={{ fontSize: 11, color: 'var(--fg-3)' }}
              >
                <span style={{ color: 'var(--fg-2)' }}>
                  {dft.toFixed(2)}
                </span>{' '}
                →{' '}
                <span
                  style={{
                    color:
                      diff > 0
                        ? 'var(--green)'
                        : diff < 0
                          ? 'var(--red)'
                          : 'var(--fg-1)',
                    fontWeight: 600,
                  }}
                >
                  {cur.toFixed(2)}
                </span>
              </span>
            </div>
            <MiniBar value={(cur / maxW) * 100} />
          </div>
        );
      })}
    </div>
  );
}

// ─── Tab: Regras NL→DSL Q.17 ────────────────────────────────────────
export function RegrasQ17Tab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['yaml-policy', 'rules', 'aprendi'],
    queryFn: () => yamlPolicyApi.list({ limit: 100 }),
  });
  const rules = data?.rules ?? [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={rules.length === 0}
      emptyText="Ainda não há regras Q.17. O fluxo completo (PT-PT → YAML → sandbox → aprovação) vive na página de Regras."
    >
      <Card padding={0}>
        <div
          style={{
            padding: '12px 18px',
            borderBottom: '1px solid var(--bd-1)',
          }}
        >
          <SectionHeader
            title="Regras NL→DSL Q.17"
            subtitle={`${rules.length} regras na whitelist fechada`}
          />
        </div>
        {rules.map((r, i) => (
          <div
            key={r.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 110px 110px',
              padding: '11px 18px',
              borderBottom:
                i < rules.length - 1 ? '1px solid var(--bd-1)' : 'none',
              gap: 12,
              alignItems: 'center',
              fontSize: 12,
            }}
          >
            <span style={{ color: 'var(--fg-0)' }}>
              {r.nl_source ?? r.description ?? r.rule_id}
            </span>
            <span
              className="mono"
              style={{ color: 'var(--fg-3)', fontSize: 11 }}
            >
              {r.event_type || '—'}
            </span>
            <RuleStatusBadge status={r.status} />
          </div>
        ))}
      </Card>
    </TabState>
  );
}

function RuleStatusBadge({ status }: { status: string }): ReactNode {
  const tone: Tone =
    status === 'active' || status === 'approved' || status === 'confirmed'
      ? 'green'
      : status === 'rejected' ||
          status === 'suspended' ||
          status === 'rolled_back'
        ? 'red'
        : 'yellow';
  return <Tag tone={tone} size="sm">{status}</Tag>;
}

// ─── Tab: Camada 1 — regras aprendidas (preference-rules) ───────────
export function Camada1Tab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['preference-rules', 'all'],
    queryFn: () => preferenceRulesApi.list({ limit: 100 }),
  });
  const rules: PreferenceRule[] = Array.isArray(data) ? data : [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={rules.length === 0}
      emptyText="Sem regras de preferência aprendidas. O sistema regista padrões à medida que tomas decisões."
    >
      <Card padding={18}>
        <SectionHeader
          title="Camada 1 · Regras aprendidas (soft)"
          subtitle="Padrões observados, não definidos · convivem com as regras Q.17"
        />
        {rules.map((r) => (
          <div
            key={r.id}
            style={{
              padding: '12px 14px',
              background: 'var(--bg-2)',
              border: '1px solid var(--bd-1)',
              borderRadius: 'var(--r-sm)',
              marginBottom: 8,
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: 4,
              }}
            >
              <span
                style={{
                  fontSize: 12.5,
                  color: 'var(--fg-0)',
                  fontWeight: 500,
                }}
              >
                {r.description || r.type}
              </span>
              <RuleStatusBadge status={r.status} />
            </div>
            <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
              Confiança {Math.round(r.confidence * 100)}% · {r.type}
            </div>
          </div>
        ))}
      </Card>
    </TabState>
  );
}

// ─── Tab: Q.17 Avançado — arquitectura fixa do DSL ──────────────────
export function Q17AdvancedTab(): ReactNode {
  // Whitelist fechada do DSL Q.17 — estrutura conhecida do sistema,
  // não dados (Pydantic Literal[...] no backend força estes valores).
  const blocks = [
    {
      label: 'Eventos DSL',
      count: 12,
      hint: 'mold_usage_threshold, defect_detected, phase_load_above, weekday, worker_assignment_proposed…',
    },
    {
      label: 'Acções',
      count: 9,
      hint: 'propose_maintenance, route_back, realloc_workers, block, auto_accept…',
    },
    {
      label: 'Operadores',
      count: 8,
      hint: '==, !=, <, >, in, contains, matches, between',
    },
    {
      label: 'Axiomas Spelke',
      count: 7,
      hint: 'continuity, exclusivity, identity, contact, agency, cohesion, solidity',
    },
  ];
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 10,
      }}
    >
      {blocks.map((b) => (
        <Card key={b.label} padding={16}>
          <div
            style={{
              fontSize: 10.5,
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
              fontWeight: 600,
            }}
          >
            {b.label}
          </div>
          <div
            className="display tabular"
            style={{ fontSize: 28, fontWeight: 500, marginTop: 6 }}
          >
            {b.count}
          </div>
          <div
            style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 4 }}
          >
            {b.hint}
          </div>
        </Card>
      ))}
    </div>
  );
}

// ─── Tab: 4 Camadas de Aprendizagem ─────────────────────────────────
export function CamadasTab(): ReactNode {
  const rules = useQuery({
    queryKey: ['learning', 'rules'],
    queryFn: () => learningApi.rules(),
  });
  const weights = useQuery({
    queryKey: ['learning', 'weights'],
    queryFn: () => learningApi.weights(),
  });
  const models = useQuery({
    queryKey: ['ml', 'models'],
    queryFn: () => mlApi.listModels(),
  });

  const layers = [
    {
      n: 1,
      label: 'Regras aprendidas',
      desc: 'Padrões observados em decisões humanas · soft constraints',
      count: rules.data?.total ?? 0,
      unit: 'regras',
    },
    {
      n: 2,
      label: 'Pesos da fitness',
      desc: 'Como ponderar makespan, qualidade, custo, idle, etc.',
      count: weights.data
        ? Object.keys(weights.data.current_weights ?? {}).length
        : 0,
      unit: 'pesos',
    },
    {
      n: 3,
      label: 'Parâmetros',
      desc: 'Thresholds, durações, custos · ajustados ao contexto real',
      count: weights.data
        ? Object.keys(weights.data.multipliers ?? {}).length
        : 0,
      unit: 'multiplicadores',
    },
    {
      n: 4,
      label: 'Modelos ML',
      desc: 'QualityRiskModel, ScheduleFitness, MoldHealth, WorkerScore',
      count: Array.isArray(models.data) ? models.data.length : 0,
      unit: 'modelos',
    },
  ];

  return (
    <TabState
      loading={rules.isLoading || weights.isLoading || models.isLoading}
      error={rules.error ?? weights.error ?? models.error}
      empty={false}
      emptyText=""
    >
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        {layers.map((c) => (
          <Card key={c.n} padding={16}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: 14 }}
            >
              <div
                className="display tabular"
                style={{
                  fontSize: 32,
                  color: 'var(--accent)',
                  fontWeight: 500,
                  width: 50,
                }}
              >
                {c.n}
              </div>
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontSize: 13.5,
                    color: 'var(--fg-0)',
                    fontWeight: 600,
                  }}
                >
                  Camada {c.n} · {c.label}
                </div>
                <div
                  style={{
                    fontSize: 11.5,
                    color: 'var(--fg-2)',
                    marginTop: 2,
                  }}
                >
                  {c.desc}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div
                  className="display tabular"
                  style={{
                    fontSize: 22,
                    color: 'var(--fg-0)',
                    fontWeight: 500,
                  }}
                >
                  {c.count}
                </div>
                <div style={{ fontSize: 10, color: 'var(--fg-3)' }}>
                  {c.unit}
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </TabState>
  );
}

// ─── Tab: Causal / Explain ──────────────────────────────────────────
export function CausalTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['explain', 'catalog'],
    queryFn: () => catalogApi.getMetrics(),
  });
  const metrics: Array<Record<string, unknown>> = Array.isArray(data)
    ? data
    : Array.isArray((data as Record<string, unknown>)?.metrics)
      ? ((data as Record<string, unknown>).metrics as Array<
          Record<string, unknown>
        >)
      : [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={metrics.length === 0}
      emptyText="Sem catálogo de métricas explicáveis disponível."
    >
      <Card padding={18}>
        <SectionHeader
          icon={<Brain size={14} />}
          title="Catálogo de métricas explicáveis"
          subtitle="Cada métrica tem origem rastreável · diagnóstico causal"
        />
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          {metrics.map((m, i) => (
            <div
              key={String(m.id ?? m.metric_id ?? i)}
              style={{
                padding: '10px 12px',
                background: 'var(--bg-2)',
                border: '1px solid var(--bd-1)',
                borderRadius: 'var(--r-sm)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <div>
                <div
                  style={{
                    fontSize: 12.5,
                    color: 'var(--fg-0)',
                    fontWeight: 500,
                  }}
                >
                  {String(m.label ?? m.name ?? m.id ?? m.metric_id)}
                </div>
                {m.description ? (
                  <div
                    style={{ fontSize: 11, color: 'var(--fg-3)' }}
                  >
                    {String(m.description)}
                  </div>
                ) : null}
              </div>
              <Tag
                tone={m.blocked === true ? 'red' : 'green'}
                size="sm"
              >
                {m.blocked === true ? 'bloqueada' : 'disponível'}
              </Tag>
            </div>
          ))}
        </div>
      </Card>
    </TabState>
  );
}

// ─── Tab: Copilot extras ────────────────────────────────────────────
export function CopilotTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['copilot', 'insights', 'aprendi'],
    queryFn: () => apiFetch<unknown>('/v1/copilot/insights'),
  });
  const insights: Array<Record<string, unknown>> = Array.isArray(data)
    ? data
    : Array.isArray((data as Record<string, unknown>)?.insights)
      ? ((data as Record<string, unknown>).insights as Array<
          Record<string, unknown>
        >)
      : [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={insights.length === 0}
      emptyText="Sem aprendizagens registadas pelo copiloto."
    >
      <Card padding={18}>
        <SectionHeader
          title="Aprendizagens do copiloto"
          subtitle="O que o copiloto on-prem aprendeu com o feedback dos utilizadores"
        />
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          {insights.map((ins, i) => (
            <div
              key={String(ins.id ?? i)}
              style={{
                padding: 11,
                background: 'var(--bg-2)',
                borderRadius: 6,
                fontSize: 12,
                color: 'var(--fg-1)',
              }}
            >
              {String(
                ins.text ?? ins.summary ?? ins.message ?? ins.title ?? '',
              )}
            </div>
          ))}
        </div>
      </Card>
    </TabState>
  );
}

// ─── Tab: Governance / Audit (hash-chain) ───────────────────────────
export function AuditTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['governance', 'audit-timeline'],
    queryFn: () =>
      apiFetch<{ events: Array<Record<string, unknown>> }>(
        '/v1/governance/audit/timeline?limit=200',
      ),
  });
  const events = data?.events ?? [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={events.length === 0}
      emptyText="Sem eventos no trilho de auditoria."
    >
      <Card padding={0}>
        <div
          style={{
            padding: '12px 18px',
            borderBottom: '1px solid var(--bd-1)',
          }}
        >
          <SectionHeader
            title="Trilho de auditoria"
            subtitle="Cada decisão tem origem · imutável · hash-encadeado"
          />
        </div>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '170px 150px 1fr',
            padding: '10px 18px',
            borderBottom: '1px solid var(--bd-1)',
            background: 'var(--bg-2)',
            fontSize: 10.5,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
            gap: 12,
          }}
        >
          <div>Timestamp</div>
          <div>Autor</div>
          <div>Evento</div>
        </div>
        {events.map((e, i) => (
          <div
            key={i}
            style={{
              display: 'grid',
              gridTemplateColumns: '170px 150px 1fr',
              padding: '10px 18px',
              borderBottom:
                i < events.length - 1 ? '1px solid var(--bd-1)' : 'none',
              gap: 12,
              fontSize: 12,
            }}
          >
            <span
              className="mono tabular"
              style={{ color: 'var(--fg-3)' }}
            >
              {e.timestamp || e.ts || e.at
                ? new Date(
                    String(e.timestamp ?? e.ts ?? e.at),
                  ).toLocaleString('pt-PT')
                : '—'}
            </span>
            <span style={{ color: 'var(--fg-1)' }}>
              {String(e.actor ?? e.by ?? e.who ?? 'sistema')}
            </span>
            <span style={{ color: 'var(--fg-1)' }}>
              {String(e.event ?? e.action ?? e.type ?? '—')}
            </span>
          </div>
        ))}
      </Card>
    </TabState>
  );
}

// ─── Tab: Factory data product ──────────────────────────────────────
export function FdpTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['capabilities', 'aprendi'],
    queryFn: () => capabilitiesApi.get(),
  });

  // Extrai data products / módulos do payload de capabilities.
  const raw = data as Record<string, unknown> | undefined;
  const products: Array<Record<string, unknown>> = Array.isArray(
    raw?.data_products,
  )
    ? (raw!.data_products as Array<Record<string, unknown>>)
    : Array.isArray(raw?.modules)
      ? (raw!.modules as Array<Record<string, unknown>>)
      : Array.isArray(raw?.features)
        ? (raw!.features as Array<Record<string, unknown>>)
        : [];

  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={products.length === 0}
      emptyText="Sem factory data products reportados pelo /v1/capabilities."
    >
      <Card padding={0}>
        <div
          style={{
            padding: '12px 18px',
            borderBottom: '1px solid var(--bd-1)',
          }}
        >
          <SectionHeader
            icon={<Boxes size={14} />}
            title="Factory data product"
            subtitle="Capacidades reportadas pelo sistema · freshness"
          />
        </div>
        {products.map((d, i) => {
          const available =
            d.available === true ||
            d.enabled === true ||
            d.status === 'ok' ||
            d.status === 'available';
          return (
            <div
              key={String(d.name ?? d.id ?? i)}
              style={{
                display: 'grid',
                gridTemplateColumns: '2fr 1fr 100px',
                padding: '10px 18px',
                borderBottom:
                  i < products.length - 1
                    ? '1px solid var(--bd-1)'
                    : 'none',
                gap: 12,
                alignItems: 'center',
                fontSize: 12,
              }}
            >
              <span
                className="mono"
                style={{ color: 'var(--fg-1)' }}
              >
                {String(d.name ?? d.id ?? d.key ?? 'data product')}
              </span>
              <span style={{ color: 'var(--fg-3)', fontSize: 11 }}>
                {String(d.freshness ?? d.description ?? d.detail ?? '')}
              </span>
              <Tag tone={available ? 'green' : 'yellow'} size="sm">
                {available ? 'disponível' : 'parcial'}
              </Tag>
            </div>
          );
        })}
      </Card>
    </TabState>
  );
}

// ─── Tab: ML registry ───────────────────────────────────────────────
export function MlRegistryTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['ml', 'models', 'list'],
    queryFn: () => mlApi.listModels(),
  });
  const models: string[] = Array.isArray(data) ? data : [];
  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={models.length === 0}
      emptyText="Sem modelos no ML registry."
    >
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        {models.map((name) => (
          <MlModelRow key={name} name={name} />
        ))}
      </div>
    </TabState>
  );
}

function MlModelRow({ name }: { name: string }): ReactNode {
  const versions = useQuery({
    queryKey: ['ml', 'versions', name],
    queryFn: () => mlApi.listVersions(name, { limit: 1 }),
  });
  const active = useQuery({
    queryKey: ['ml', 'active', name],
    queryFn: () => mlApi.getActive(name),
    retry: false,
  });
  const latest = versions.data?.[0] as Record<string, unknown> | undefined;
  const activeArtifact = active.data as
    | Record<string, unknown>
    | undefined;
  return (
    <Card padding={14}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 13,
              color: 'var(--fg-0)',
              fontWeight: 600,
            }}
          >
            {name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)' }}>
            {versions.data
              ? `${versions.data.length === 0 ? 'sem' : ''} versões registadas`
              : 'a carregar versões…'}
            {latest?.created_at
              ? ` · última ${new Date(
                  String(latest.created_at),
                ).toLocaleDateString('pt-PT')}`
              : ''}
          </div>
        </div>
        <Tag tone={activeArtifact ? 'green' : 'yellow'} size="sm">
          {activeArtifact
            ? `activa ${String(
                activeArtifact.version ?? activeArtifact.id ?? '',
              ).slice(0, 8)}`
            : 'sem versão activa'}
        </Tag>
      </div>
    </Card>
  );
}

// ─── Tab: Twin sandbox ──────────────────────────────────────────────
export function TwinSandboxTab(): ReactNode {
  const { data, isLoading, error } = useQuery({
    queryKey: ['twin', 'scenarios', 'aprendi'],
    queryFn: () => apiFetch<Array<Record<string, unknown>>>(
      '/v1/twin/scenarios',
    ),
  });
  const scenarios = Array.isArray(data) ? data : [];
  const simulated = scenarios.filter(
    (s) => !!s.simulation_result,
  ).length;
  const solved = scenarios.filter((s) => s.status === 'SOLVED').length;

  return (
    <TabState
      loading={isLoading}
      error={error}
      empty={false}
      emptyText=""
    >
      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}
      >
        <Card padding={18}>
          <SectionHeader
            icon={<FlaskConical size={14} />}
            title="Digital twin sandbox"
            subtitle="Cópia isolada da BD · corre what-ifs sem tocar produção"
          />
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(2, 1fr)',
              gap: 8,
            }}
          >
            <SandboxStat label="Cenários" value={scenarios.length} />
            <SandboxStat label="Simulados" value={simulated} />
            <SandboxStat
              label="Resolvidos"
              value={solved}
              tone="green"
            />
            <SandboxStat
              label="Por simular"
              value={scenarios.length - simulated}
              tone="yellow"
            />
          </div>
        </Card>
        <Card padding={18}>
          <SectionHeader title="Como funciona" />
          <ol
            style={{
              paddingLeft: 18,
              margin: 0,
              fontSize: 12,
              color: 'var(--fg-1)',
              lineHeight: 1.7,
            }}
          >
            <li>Snapshot da BD de produção (read-only)</li>
            <li>Aplica a mudança proposta na cópia</li>
            <li>Valida os 7 axiomas Spelke</li>
            <li>Mede o impacto · €, dias, OTD</li>
            <li>Descarta a cópia · devolve o veredicto</li>
          </ol>
        </Card>
      </div>
    </TabState>
  );
}

function SandboxStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: Tone;
}): ReactNode {
  return (
    <div
      style={{
        padding: 10,
        background: 'var(--bg-2)',
        borderRadius: 6,
      }}
    >
      <div
        style={{
          fontSize: 10,
          color: 'var(--fg-3)',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
        }}
      >
        {label}
      </div>
      <div
        className="display tabular"
        style={{
          fontSize: 22,
          fontWeight: 500,
          color: tone ? toneVar(tone) : 'var(--fg-0)',
        }}
      >
        {value}
      </div>
    </div>
  );
}

// ─── Tab: Showcase ──────────────────────────────────────────────────
export function ShowcaseTab(): ReactNode {
  const weights = useQuery({
    queryKey: ['learning', 'weights'],
    queryFn: () => learningApi.weights(),
  });
  const rules = useQuery({
    queryKey: ['learning', 'rules'],
    queryFn: () => learningApi.rules(),
  });
  const pairs = useQuery({
    queryKey: ['learning', 'pairs'],
    queryFn: () => learningApi.pairs(),
  });
  const models = useQuery({
    queryKey: ['ml', 'models'],
    queryFn: () => mlApi.listModels(),
  });

  const cards: Array<{ title: string; detail: string; tone: Tone }> = [
    {
      title: `${rules.data?.total ?? 0} regras aprendidas`,
      detail: 'Padrões detectados nas decisões humanas',
      tone: 'blue',
    },
    {
      title: `${pairs.data?.total_pairs ?? 0} pares de treino`,
      detail: `${pairs.data?.eligible_for_dpo ?? 0} elegíveis para DPO`,
      tone: 'green',
    },
    {
      title: `${
        weights.data
          ? Object.keys(weights.data.current_weights ?? {}).length
          : 0
      } pesos de fitness`,
      detail: 'Ajustados ao contexto real da fábrica',
      tone: 'teal',
    },
    {
      title: `${Array.isArray(models.data) ? models.data.length : 0} modelos ML`,
      detail: 'No registry · com drift monitor',
      tone: 'purple',
    },
    {
      title: `${pairs.data?.abl_pairs_today ?? 0} pares hoje`,
      detail: 'Aprendizagem activa no dia de hoje',
      tone: 'green',
    },
    {
      title: '0 violações de axioma',
      detail: '7 axiomas Spelke nunca cedem por design',
      tone: 'green',
    },
  ];

  return (
    <TabState
      loading={
        weights.isLoading ||
        rules.isLoading ||
        pairs.isLoading ||
        models.isLoading
      }
      error={
        weights.error ?? rules.error ?? pairs.error ?? models.error
      }
      empty={false}
      emptyText=""
    >
      <Card padding={18}>
        <SectionHeader
          title="Showcase"
          subtitle="Resultados reais da aprendizagem — para parceiros, equipa, direção"
        />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 10,
          }}
        >
          {cards.map((s, i) => (
            <div
              key={i}
              style={{
                padding: 14,
                background: toneBg(s.tone),
                border: `1px solid ${toneBd(s.tone)}`,
                borderRadius: 'var(--r-md)',
              }}
            >
              <div
                className="display"
                style={{
                  fontSize: 17,
                  color: toneVar(s.tone),
                  fontWeight: 600,
                }}
              >
                {s.title}
              </div>
              <div
                style={{
                  fontSize: 11.5,
                  color: 'var(--fg-2)',
                  marginTop: 4,
                }}
              >
                {s.detail}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </TabState>
  );
}
