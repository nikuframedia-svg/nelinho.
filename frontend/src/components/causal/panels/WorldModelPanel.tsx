// CausalPanels · WorldModelPanel (Q.60.X). ZERO MOCKS — endpoints reais.
import { Panel, EmptyState } from '../../dark';

export function WorldModelPanel() {
  return (
    <Panel
      title="World-model — forecast bands"
      subtitle="src.copilot.causal.world_model (sem REST exposto)">
      <EmptyState
        title="Endpoint REST por expor"
        hint="Módulo Python com Monte Carlo rollout existe (causal_query) mas /v1/explain/forecast ainda não está implementado. Para já, world-model corre apenas via tool-call interno do Copilot."
        size="sm"
      />
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// 7. AttributionPanel — GET /v1/explain/attribution (waterfall)
// ═══════════════════════════════════════════════════════════════════════════
