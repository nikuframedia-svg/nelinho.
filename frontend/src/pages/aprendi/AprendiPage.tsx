/**
 * AprendiPage — /aprendi · "O que aprendi" (Q.52.O).
 *
 * Reconstrução fiel do design NELO.html (page-aprendi.jsx): banner de
 * transparência + 12 sub-tabs em pílulas. Cada tab liga a um endpoint
 * real (learning/weights, ml/models, preference-rules, audit/timeline,
 * explain/catalog, capabilities…).
 *
 * ZERO MOCKS: as tabs com dados vêm da API; quando vazias mostram um
 * estado honesto. As tabs "Q.17 Avançado" descrevem a arquitectura
 * fixa do DSL (whitelist fechada) — estrutura conhecida, não dados.
 *
 * Sprint Q.52.O.
 */

import { useState } from 'react';
import { Brain, Eye } from 'lucide-react';
import type { ReactNode } from 'react';
import { DarkPageLayout } from '../../layouts';
import {
  AuditTab,
  Camada1Tab,
  CamadasTab,
  CausalTab,
  CopilotTab,
  FdpTab,
  MlRegistryTab,
  Q17AdvancedTab,
  RegrasQ17Tab,
  ResumoTab,
  ShowcaseTab,
  TwinSandboxTab,
} from '../../components/aprendi/tabs';

type AprendiTab =
  | 'resumo'
  | 'regras'
  | 'camada1'
  | 'q17adv'
  | 'camadas'
  | 'causal'
  | 'copilot'
  | 'audit'
  | 'fdp'
  | 'ml'
  | 'twin'
  | 'showcase';

const SUB_TABS: Array<{ id: AprendiTab; label: string }> = [
  { id: 'resumo', label: 'Resumo' },
  { id: 'regras', label: 'Regras (NL→DSL Q.17)' },
  { id: 'camada1', label: 'Regras aprendidas (Camada 1)' },
  { id: 'q17adv', label: 'Q.17 Avançado' },
  { id: 'camadas', label: '4 Camadas de Aprendizagem' },
  { id: 'causal', label: 'Causal / Explain' },
  { id: 'copilot', label: 'Copilot extras' },
  { id: 'audit', label: 'Governança / Audit' },
  { id: 'fdp', label: 'Factory data product' },
  { id: 'ml', label: 'ML registry' },
  { id: 'twin', label: 'Twin sandbox' },
  { id: 'showcase', label: 'Showcase' },
];

const TAB_COMPONENTS: Record<AprendiTab, () => ReactNode> = {
  resumo: ResumoTab,
  regras: RegrasQ17Tab,
  camada1: Camada1Tab,
  q17adv: Q17AdvancedTab,
  camadas: CamadasTab,
  causal: CausalTab,
  copilot: CopilotTab,
  audit: AuditTab,
  fdp: FdpTab,
  ml: MlRegistryTab,
  twin: TwinSandboxTab,
  showcase: ShowcaseTab,
};

export default function AprendiPage(): ReactNode {
  const [tab, setTab] = useState<AprendiTab>('resumo');
  const ActiveTab = TAB_COMPONENTS[tab];

  return (
    <DarkPageLayout
      title="O que aprendi"
      subtitle="Transparência total · tudo o que o sistema aprendeu está aqui — podes aprovar, rejeitar ou pausar qualquer regra"
      icon={<Brain size={20} />}
    >
      {/* Banner de transparência */}
      <div
        style={{
          padding: 14,
          background: 'var(--bg-2)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-md)',
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <Eye size={16} color="var(--accent)" />
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontSize: 13,
              color: 'var(--fg-0)',
              fontWeight: 500,
            }}
          >
            Transparência total
          </div>
          <div style={{ fontSize: 11.5, color: 'var(--fg-2)' }}>
            Nada é mágico, nada é caixa-preta. Cada padrão, peso, modelo ou
            decisão tem origem rastreável.
          </div>
        </div>
      </div>

      {/* Pílulas das sub-tabs */}
      <div
        style={{
          display: 'flex',
          gap: 4,
          flexWrap: 'wrap',
          marginBottom: 18,
          paddingBottom: 12,
          borderBottom: '1px solid var(--bd-1)',
        }}
      >
        {SUB_TABS.map((s) => {
          const active = tab === s.id;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => setTab(s.id)}
              style={{
                padding: '6px 12px',
                background: active ? 'var(--bg-3)' : 'transparent',
                border: `1px solid ${
                  active ? 'var(--bd-2)' : 'transparent'
                }`,
                borderRadius: 999,
                color: active ? 'var(--fg-0)' : 'var(--fg-2)',
                fontSize: 11.5,
                fontWeight: active ? 600 : 500,
                cursor: 'pointer',
              }}
            >
              {s.label}
            </button>
          );
        })}
      </div>

      <ActiveTab />
    </DarkPageLayout>
  );
}
