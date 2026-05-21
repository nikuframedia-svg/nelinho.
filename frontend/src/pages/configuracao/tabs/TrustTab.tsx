// ConfiguracaoPage · TrustTab (Q.60.U). ZERO MOCKS — endpoints reais.
import { useQuery } from '@tanstack/react-query';
import { ShieldCheck, Loader2 } from 'lucide-react';
import { KPIBig, EmptyState } from '../../../components/dark';
import { dqaApi } from '../../../lib/api';
import { ConfigCard, SectionHeader, type ConfigKeyRow, ConfigKeysPanel } from '../configuracaoShared';

export function TrustTab() {
  const trustQ = useQuery({
    queryKey: ['dqa', 'trust-index', 'global'],
    queryFn: () => dqaApi.trustIndex(),
    staleTime: 60_000,
    retry: false,
  });

  const ti = trustQ.data as
    | {
        trust_index?: number;
        score?: number;
        grade?: string;
        components?: Record<string, number>;
        component_scores?: Record<string, number>;
      }
    | undefined;
  const score = ti?.trust_index ?? ti?.score ?? null;
  const components = ti?.components ?? ti?.component_scores ?? {};

  return (
    <div className="space-y-3.5">
      <div className="grid grid-cols-3 gap-3">
        <KPIBig
          label="Trust Index global"
          value={score != null ? Math.round(score * 100) : '—'}
          unit={score != null ? '%' : undefined}
          context="confiança nos dados que alimentam o solver"
          status={
            score == null
              ? 'gray'
              : score >= 0.75
                ? 'green'
                : score >= 0.6
                  ? 'yellow'
                  : 'red'
          }
        />
        <KPIBig
          label="Grade"
          value={ti?.grade ?? '—'}
          status="accent"
        />
        <KPIBig
          label="Componentes"
          value={Object.keys(components).length}
          context="7 componentes ponderados (C/V/F/K/P/A/E)"
          status="gray"
        />
      </div>

      <ConfigCard>
        <div
          style={{ padding: '14px 18px', borderBottom: '1px solid var(--bd-1)' }}
        >
          <SectionHeader
            icon={<ShieldCheck size={14} />}
            title="Componentes do Trust Index"
            subtitle="GET /v1/dqa/trust-index — score por componente"
          />
        </div>
        <div className="p-[18px]">
          {trustQ.isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={20} className="text-accent-500 animate-spin" />
            </div>
          ) : Object.keys(components).length === 0 ? (
            <EmptyState
              title="Sem componentes de trust"
              hint="O Trust Index v2 calcula 7 componentes. Se a lista está vazia, o snapshot ainda não correu."
            />
          ) : (
            <div className="flex flex-col gap-2.5">
              {Object.entries(components).map(([name, val]) => (
                <div key={name}>
                  <div className="flex justify-between text-[12px] mb-1">
                    <span className="text-text-dark-secondary capitalize">
                      {name}
                    </span>
                    <span className="tabular-nums text-text-dark-primary font-semibold">
                      {Math.round(val * 100)}%
                    </span>
                  </div>
                  <div
                    style={{
                      height: 5,
                      background: 'var(--bd-1)',
                      borderRadius: 3,
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.min(100, val * 100)}%`,
                        height: '100%',
                        background:
                          val >= 0.75
                            ? 'var(--green)'
                            : val >= 0.6
                              ? 'var(--yellow)'
                              : 'var(--red)',
                        borderRadius: 3,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </ConfigCard>

      <ConfigKeysPanel
        title="Pesos e gates do Trust Index"
        subtitle="Blueprint v2.0 §4.5 · 7 componentes + 5 gates"
        icon={<ShieldCheck size={14} />}
        category="trust"
        rows={TRUST_KEYS}
        hint="Componentes (peso): C/V/F/K/P/A/E somam 1.0. Gates: 0.50 (solver-only), 0.60 (P90), 0.70 (auto-reorder), 0.75 (auto-commit), 0.80 (quality disposition)."
      />
    </div>
  );
}

// ─── Conjuntos de chaves de configuração (ConfigStore) ───────────────────────

export const TRUST_KEYS: ConfigKeyRow[] = [
  { key: 'weights.completeness', label: 'Peso C — Completeness', hint: 'Default 0.15', dataType: 'float' },
  { key: 'weights.validity', label: 'Peso V — Validity', hint: 'Default 0.20', dataType: 'float' },
  { key: 'weights.freshness', label: 'Peso F — Freshness', hint: 'Default 0.15', dataType: 'float' },
  { key: 'weights.consistency', label: 'Peso K — Consistency', hint: 'Default 0.20', dataType: 'float' },
  { key: 'weights.provenance', label: 'Peso P — Provenance', hint: 'Default 0.15', dataType: 'float' },
  { key: 'weights.anomaly', label: 'Peso A — Anomaly', hint: 'Default 0.10', dataType: 'float' },
  { key: 'weights.evidence', label: 'Peso E — Evidence', hint: 'Default 0.05', dataType: 'float' },
  { key: 'gates.auto_commit', label: 'Gate 4 — auto-commit', hint: 'TI<0.75 → human approval', dataType: 'float' },
  { key: 'gates.quality_disposition', label: 'Gate 5 — quality disposition', hint: 'TI<0.80 → quality moves bloqueados', dataType: 'float' },
];
