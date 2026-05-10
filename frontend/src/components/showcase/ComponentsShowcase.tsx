/**
 * ComponentsShowcase — Onda 20 (X). Demo dos componentes design system
 * sub-utilizados, wired a dados reais do backend.
 */

import { useQuery } from '@tanstack/react-query';
import {
  Panel,
  CausalChainCard,
  TimelineSuggestion,
  ConsequenceBlock,
  type ConsequenceLine,
} from '../dark';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
const BASE = 'http://127.0.0.1:8001';

export function ComponentsShowcase() {
  const decisionQ = useQuery({
    queryKey: ['showcase-decision'],
    queryFn: async () => {
      const r = await fetch(`${BASE}/v1/governance/decisions?limit=1`, { headers: TENANT });
      if (!r.ok) return null;
      const data = await r.json();
      const items = Array.isArray(data) ? data : (data.items ?? []);
      return items[0] ?? null;
    },
    staleTime: 60_000,
    retry: 0,
  });

  const firingQ = useQuery({
    queryKey: ['showcase-firing'],
    queryFn: async () => {
      const r = await fetch(`${BASE}/v1/governance/rule-firings?limit=1`, { headers: TENANT });
      if (!r.ok) return null;
      const data = await r.json();
      const items = Array.isArray(data) ? data : (data.items ?? data.firings ?? []);
      return items[0] ?? null;
    },
    staleTime: 60_000,
    retry: 0,
  });

  const decision = decisionQ.data as any;
  const firing = firingQ.data as any;

  const ifAccept: ConsequenceLine[] = [
    { label: 'OTD', value: '+0.5%', severity: 'positive' },
    { label: 'Throughput', value: '+€120/dia', severity: 'positive' },
    { label: 'Risco', value: 'baixo', severity: 'info' },
  ];
  const ifReject: ConsequenceLine[] = [
    { label: 'OTD', value: '−0.3%', severity: 'critical' },
    { label: 'Backlog', value: '+2 dias', severity: 'warning' },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs" style={{ color: 'var(--fg-2)' }}>
          Componentes design system wired a dados reais
        </span>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda20 — X. Componentes
        </span>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <Panel title="CausalChainCard" subtitle="GET /v1/governance/decisions?limit=1">
          {decisionQ.isLoading ? (
            <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
          ) : (
            <CausalChainCard
              question={decision?.decision_type ?? 'Sem decisão recente'}
              root_cause={decision ? `Decisão ${decision.status ?? '—'} (${decision.decision_id?.slice(0, 8) ?? ''})` : 'Sem dados'}
              confidence={decision?.confidence ?? 0.75}
              mechanism={[
                'Trigger: ' + (decision?.trigger_event ?? '—'),
                'Política: ' + (decision?.policy_name ?? '—'),
                'Status: ' + (decision?.status ?? '—'),
              ]}
              evidence={decision?.evidence_refs ?? ['Sem evidence_refs disponíveis']}
              recommendation={decision?.recommendation ?? 'Aceitar (auto-approved policy match)'}
            />
          )}
        </Panel>

        <Panel title="ConsequenceBlock" subtitle="3 linhas: positivo/warning/critical">
          <ConsequenceBlock title="Se aceitar" lines={ifAccept} />
          <div className="h-2" />
          <ConsequenceBlock title="Se rejeitar" lines={ifReject} />
        </Panel>
      </div>

      <Panel title="TimelineSuggestion" subtitle="GET /v1/governance/rule-firings?limit=1">
        {firingQ.isLoading ? (
          <div className="px-2 py-4 text-xs text-center" style={{ color: 'var(--fg-3)' }}>A carregar…</div>
        ) : (
          <TimelineSuggestion
            id={firing?.id ?? 'demo'}
            priority="medium"
            title={firing?.event_type ?? 'Sugestão demo'}
            what_changed={firing ? `Regra ${(firing.rule_id ?? '').slice(0, 8)} disparou` : 'Mover 3 K2 de terça para quarta'}
            why={firing?.outcome ?? 'Padrão histórico sugere ganho de OTD'}
            if_accept={ifAccept}
            if_reject={ifReject}
            age_label={firing?.created_at ? new Date(firing.created_at).toLocaleString('pt-PT') : 'demo'}
            onAccept={async () => alert('Demo only — usa /inbox para aceitar decisões reais.')}
            onReject={async () => alert('Demo only — usa /inbox para rejeitar.')}
          />
        )}
      </Panel>

      <div className="text-[10px] flex items-center gap-2 px-1" style={{ color: 'var(--fg-3)' }}>
        Outros componentes design system já wired noutras pages: ConfigParam (/definicoes
        {' > '} Cura/secagem) · GhostOverlay (DragDropPlanner) · IngestionTimeline (/qualidade
        Trust) · ScenarioDiffViewer (/admin/twin) · ToolRegistry (/definicoes Sistema).
      </div>
    </div>
  );
}
