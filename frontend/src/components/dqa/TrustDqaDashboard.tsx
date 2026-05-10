/**
 * TrustDqaDashboard — consolidação 6 componentes Palantir num único dashboard.
 *
 * Onda 5 — E. Trust + DQA. Reúne:
 *   1. TrustHeatmap        — composite trust por dimensão
 *   2. BlockedMetricsWall  — métricas bloqueadas + razões
 *   3. CoverageAnalysis    — % cobertura ingestão
 *   4. IngestionTimeline   — eventos ingestão recentes
 *   5. SchemaDriftAlert    — alertas drift global
 *   6. QuarantineCenter    — registos em quarentena
 *
 * Componentes JÁ existem em /admin/data-quality (DataQualityPage). Este
 * dashboard reaproveita-os para tornar Trust+DQA visível em /qualidade
 * (sub-tab "Trust") sem duplicar lógica.
 */

import { useState } from 'react';
import {
  Shield,
  Ban,
  Activity,
  FileWarning,
  AlertTriangle,
  Database,
  ChevronRight,
} from 'lucide-react';
import {
  TrustHeatmap,
  BlockedMetricsWall,
  CoverageAnalysis,
  IngestionTimeline,
  SchemaDriftAlert,
  QuarantineCenter,
} from '../palantir';
import { useTrustHeatmap } from '@/hooks';

const SUB_TABS = [
  { id: 'overview', label: 'Resumo', icon: Shield },
  { id: 'trust', label: 'Trust Heatmap', icon: Shield },
  { id: 'blocked', label: 'Bloqueadas', icon: Ban },
  { id: 'coverage', label: 'Cobertura', icon: Activity },
  { id: 'ingestion', label: 'Ingestão', icon: Database },
  { id: 'drift', label: 'Schema drift', icon: FileWarning },
  { id: 'quarantine', label: 'Quarentena', icon: AlertTriangle },
] as const;
type SubId = (typeof SUB_TABS)[number]['id'];

export function TrustDqaDashboard() {
  const [sub, setSub] = useState<SubId>('overview');
  const { data: heatmapData } = useTrustHeatmap();

  return (
    <div className="space-y-4">
      {/* sub-tabs strip */}
      <div
        className="flex flex-wrap items-center gap-1 px-1 pb-2 border-b"
        style={{ borderColor: 'var(--bd-1)' }}
      >
        {SUB_TABS.map((t) => {
          const Icon = t.icon;
          const active = sub === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setSub(t.id)}
              className="rounded-md px-2.5 py-1.5 text-xs flex items-center gap-1.5 transition-colors"
              style={{
                background: active ? 'var(--bg-3)' : 'transparent',
                color: active ? 'var(--fg-1)' : 'var(--fg-3)',
              }}
            >
              <Icon size={12} />
              {t.label}
              {active && <ChevronRight size={11} />}
            </button>
          );
        })}
        <span className="ml-auto text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda5 — E. Trust + DQA
        </span>
      </div>

      {/* sub-tab content */}
      {sub === 'overview' && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <TrustHeatmap data={heatmapData} />
          <BlockedMetricsWall compact maxItems={6} />
          <CoverageAnalysis />
          <QuarantineCenter />
        </div>
      )}
      {sub === 'trust' && <TrustHeatmap data={heatmapData} />}
      {sub === 'blocked' && <BlockedMetricsWall />}
      {sub === 'coverage' && <CoverageAnalysis />}
      {sub === 'ingestion' && <IngestionTimeline />}
      {sub === 'drift' && (
        <div className="rounded-md border p-4" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
          <div className="text-xs mb-3" style={{ color: 'var(--fg-3)' }}>
            Alertas de schema drift detectados nas últimas 24h. O componente
            <code className="font-mono mx-1">SchemaDriftAlert</code>
            também aparece como floating banner no Layout global quando há drift activo.
          </div>
          <SchemaDriftAlert position="inline" />
        </div>
      )}
      {sub === 'quarantine' && <QuarantineCenter />}
    </div>
  );
}
