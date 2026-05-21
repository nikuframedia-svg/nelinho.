// CausalPanels · AblationPanel (Q.60.X). ZERO MOCKS — endpoints reais.
import { Panel, EmptyState } from '../../dark';

export function AblationPanel() {
  return (
    <Panel
      title="Ablation kit — feature importance"
      subtitle="src.copilot.causal.ablkit (sem REST exposto)">
      <EmptyState
        title="Endpoint REST por expor"
        hint="Detector ABL kit já existe como módulo Python para o Copilot. /v1/explain/ablation está planeado mas ainda não exposto. Por agora, importância de features só visível via Copilot drawer."
        size="sm"
      />
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 9. WhyKpiPanel — GET /kpis/snapshot-explained (drawer KPI)
// ═══════════════════════════════════════════════════════════════════════════
