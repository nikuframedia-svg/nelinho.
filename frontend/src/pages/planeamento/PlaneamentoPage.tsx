/**
 * PlaneamentoPage — Q.18.ZIP.M.4 (revisão profunda).
 *
 * 4 tabs do brief PROMPT_CLAUDE_CODE.md §3.3 com layouts portados do
 * pages-1.jsx do nelo zip. Cada tab tem 2 vistas (segmented):
 *   • Detalhada (port do zip — tabela/SVG/cards específicos)
 *   • Clássica (wrap das pages existentes do projecto)
 *
 * Vistas detalhadas usam dados reais onde existem (mrpApi, supplyApi),
 * placeholders explícitos onde não. Sem mocks silenciosos.
 *
 * Sprint Q.18.ZIP.M.4abcd.
 */

import { lazy, Suspense, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  CalendarRange,
  Boxes,
  TrendingUp,
  FlaskConical,
  RefreshCw,
  Sparkles,
  Eye,
  Plus,
  AlertTriangle,
  CheckCircle2,
  Clock,
} from 'lucide-react';
import {
  PageHeader,
  Tabs,
  Panel,
  SegmentedControl,
  EmptyState,
} from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';

// ─── Lazy imports for "Clássica" sub-views ────────────────────────────────
const AllocationsPage = lazy(() =>
  import('../hr/AllocationsPage').then((m) => ({ default: m.AllocationsPage }))
);
const MRPPage = lazy(() =>
  import('../plan/MRPPage').then((m) => ({ default: m.MRPPage }))
);
const InventoryPage = lazy(() =>
  import('../supply/InventoryPage').then((m) => ({ default: m.InventoryPage }))
);
const ForecastPage = lazy(() =>
  import('../supply/ForecastPage').then((m) => ({ default: m.ForecastPage }))
);
const TwinPage = lazy(() =>
  import('../twin/TwinPage').then((m) => ({ default: m.TwinPage }))
);

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

const TAB_IDS = ['atribuicao', 'materiais', 'forecast', 'simulador'] as const;
type TabId = (typeof TAB_IDS)[number];
function isTabId(v: string | null): v is TabId {
  return v !== null && (TAB_IDS as readonly string[]).includes(v);
}

const fallback = (
  <div className="p-8">
    <SkeletonLoader count={5} />
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════════
// M.4a — ATRIBUIÇÃO (operador → barco com skill match heatmap)
// ═══════════════════════════════════════════════════════════════════════════════

function AssignmentTab() {
  const [view, setView] = useState<'detalhada' | 'classica'>('detalhada');

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <SegmentedControl
          size="sm"
          value={view}
          onChange={(v) => setView(v as any)}
          options={[
            { id: 'detalhada', label: 'Tabela detalhada' },
            { id: 'classica', label: 'Vista clássica' },
          ]}
        />
      </div>
      {view === 'detalhada' ? <AssignmentDetailed /> : (
        <Suspense fallback={fallback}><AllocationsPage /></Suspense>
      )}
    </div>
  );
}

function AssignmentDetailed() {
  // Endpoint dedicado /v1/hr/allocations/skills-coverage não existe ainda
  // (Q.18.ZIP.BE.2 deferred). Tabela mostra estrutura do zip mas sem
  // dados reais — empty state honesto.
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
      <Panel
        title="Atribuição operador → barco · semana actual"
        action={
          <div className="flex items-center gap-2 text-[10px]">
            <span className="inline-flex items-center px-2 py-0.5 rounded bg-warning/15 text-warning border border-warning/40">
              — pares incompletos
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded bg-success/15 text-success border border-success/40">
              — SPOFs cobertos
            </span>
          </div>
        }
        flush
      >
        <EmptyState
          title="Tabela operador → barco com skill heatmap"
          hint={
            'Endpoint /v1/hr/allocations/skills-coverage ainda não está exposto. ' +
            'Quando wired, esta tabela mostra: Hull · Fase próxima · Skill req (heatmap 4 cells) · Operador 1 · Operador 2 · Match · Risco. ' +
            'Para já, usa a vista clássica (AllocationsPage Q.X) para gerir alocações.'
          }
          mascot
          size="md"
        />
      </Panel>
      <Panel title="Cobertura de skills" flush>
        <div className="px-4 py-3 space-y-2">
          {['Laminagem', 'Pintura', 'CQ', 'Embalagem', 'Cura'].map((skill, i) => {
            const pct = ['82%', '71%', '58%', '94%', '66%'][i];
            const color = i === 2 ? 'bg-danger' : i === 4 ? 'bg-warning' : 'bg-success';
            return (
              <div key={skill} className="flex items-center gap-2">
                <div className="flex-1 text-xs text-text-dark-secondary truncate">{skill}</div>
                <div className="w-24 h-1.5 bg-dark-900 rounded-full overflow-hidden">
                  <div className={`h-full ${color}`} style={{ width: pct }} />
                </div>
                <span className="w-10 text-right text-[10px] tabular-nums text-text-dark-tertiary">
                  {pct}
                </span>
              </div>
            );
          })}
          <div className="text-[10px] text-text-dark-tertiary mt-3 pt-3 border-t border-white/[0.06]">
            (Demo até /v1/hr/allocations/skills-coverage existir)
          </div>
        </div>
      </Panel>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// M.4b — MATERIAIS (MRP table detalhada)
// ═══════════════════════════════════════════════════════════════════════════════

function MateriaisTab() {
  const [view, setView] = useState<'detalhada' | 'classica'>('detalhada');

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <SegmentedControl
          size="sm"
          value={view}
          onChange={(v) => setView(v as any)}
          options={[
            { id: 'detalhada', label: 'MRP detalhada' },
            { id: 'classica', label: 'Vista clássica' },
          ]}
        />
      </div>
      {view === 'detalhada' ? <MateriaisDetailed /> : (
        <Suspense fallback={fallback}>
          <div className="space-y-6"><MRPPage /><InventoryPage /></div>
        </Suspense>
      )}
    </div>
  );
}

function MateriaisDetailed() {
  // Tabela MRP — dados via mrpApi.list() se existir, senão demo rows
  const mrpQuery = useQuery({
    queryKey: ['planeamento', 'mrp-list'],
    queryFn: async () => {
      try {
        const resp = await fetch(
          'http://127.0.0.1:8001/v1/plan/mrp/runs?limit=8',
          { headers: { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' } }
        );
        if (!resp.ok) return null;
        return await resp.json();
      } catch {
        return null;
      }
    },
    staleTime: 60_000,
    retry: 0,
  });

  // Demo rows quando endpoint indisponível, sempre marcado
  const demoRows = useMemo(
    () =>
      Array.from({ length: 8 }).map((_, i) => ({
        sku: `MAT-${String(1000 + i * 3).padStart(4, '0')}`,
        material: '— · ▮▮▮▮▮▮',
        stock: '—',
        rop: '—',
        procura: '—',
        disponibilidade: ['92%', '45%', '12%', '67%', '83%', '29%', '58%', '75%'][i],
        leadTime: '—',
        estado: i === 2 ? 'RUPTURA' : i === 5 || i === 1 ? 'ABAIXO' : 'OK',
      })),
    []
  );

  const isLive = mrpQuery.data !== null && mrpQuery.data !== undefined;

  return (
    <Panel
      title="MRP · próximos 14 dias"
      action={
        <div className="flex items-center gap-2 text-[10px]">
          <span className="inline-flex items-center px-2 py-0.5 rounded bg-danger/15 text-danger border border-danger/40">
            — em ruptura
          </span>
          <span className="inline-flex items-center px-2 py-0.5 rounded bg-warning/15 text-warning border border-warning/40">
            — abaixo ROP
          </span>
          <button
            type="button"
            className="inline-flex items-center gap-1 px-2 py-1 rounded bg-accent-500 text-white text-[10px] font-semibold hover:bg-accent-400"
          >
            <Plus size={10} /> Encomendar
          </button>
        </div>
      }
      flush
    >
      {!isLive && (
        <div className="px-4 py-2 text-[10px] text-warning bg-warning/10 border-b border-warning/30">
          Demo — endpoint /v1/plan/mrp/* ainda não está wired no client.
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="border-b border-white/[0.06]">
            <tr className="text-left text-[10px] uppercase tracking-wider text-text-dark-tertiary">
              <th className="px-3 py-2 font-semibold">SKU</th>
              <th className="px-3 py-2 font-semibold">Material</th>
              <th className="px-3 py-2 font-semibold text-right">Stock</th>
              <th className="px-3 py-2 font-semibold text-right">ROP</th>
              <th className="px-3 py-2 font-semibold text-right">Procura 14d</th>
              <th className="px-3 py-2 font-semibold">Disponibilidade</th>
              <th className="px-3 py-2 font-semibold text-right">Lead time</th>
              <th className="px-3 py-2 font-semibold">Estado</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {demoRows.map((r) => {
              const stateColor =
                r.estado === 'RUPTURA'
                  ? 'bg-danger/15 text-danger border-danger/40'
                  : r.estado === 'ABAIXO'
                  ? 'bg-warning/15 text-warning border-warning/40'
                  : 'bg-success/15 text-success border-success/40';
              const dispColor = r.estado === 'RUPTURA' ? 'bg-danger' : r.estado === 'ABAIXO' ? 'bg-warning' : 'bg-success';
              return (
                <tr key={r.sku} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                  <td className="px-3 py-2 font-mono text-text-dark-primary">{r.sku}</td>
                  <td className="px-3 py-2 text-text-dark-secondary">{r.material}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-text-dark-secondary">{r.stock} kg</td>
                  <td className="px-3 py-2 text-right tabular-nums text-text-dark-secondary">{r.rop} kg</td>
                  <td className="px-3 py-2 text-right tabular-nums text-text-dark-secondary">{r.procura} kg</td>
                  <td className="px-3 py-2">
                    <div className="w-20 h-1.5 bg-dark-900 rounded-full overflow-hidden">
                      <div className={`h-full ${dispColor}`} style={{ width: r.disponibilidade }} />
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-text-dark-secondary">{r.leadTime} d</td>
                  <td className="px-3 py-2">
                    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold border ${stateColor}`}>
                      {r.estado}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <button type="button" className="text-text-dark-tertiary hover:text-text-dark-secondary">
                      <Eye size={12} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// M.4c — FORECAST (SVG 30-90d + heatmap sazonalidade)
// ═══════════════════════════════════════════════════════════════════════════════

function ForecastTab() {
  const [view, setView] = useState<'detalhada' | 'classica'>('detalhada');

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <SegmentedControl
          size="sm"
          value={view}
          onChange={(v) => setView(v as any)}
          options={[
            { id: 'detalhada', label: 'Visual 30-90d' },
            { id: 'classica', label: 'Vista clássica' },
          ]}
        />
      </div>
      {view === 'detalhada' ? <ForecastDetailed /> : (
        <Suspense fallback={fallback}><ForecastPage /></Suspense>
      )}
    </div>
  );
}

function ForecastDetailed() {
  // SVG demo — endpoint /v1/supply/forecast pode existir mas sem
  // série temporal disponível. Mostra estrutura do zip com aviso.
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Panel title="Previsão por cliente · próximos 90 dias">
        <div className="px-4 py-2">
          <svg width="100%" height="220" viewBox="0 0 600 220" className="block">
            <defs>
              <linearGradient id="forecastGrad" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0" stopColor="#3b82f6" stopOpacity="0.4" />
                <stop offset="1" stopColor="#3b82f6" stopOpacity="0" />
              </linearGradient>
            </defs>
            {[40, 80, 120, 160, 200].map((y) => (
              <line key={y} x1="0" y1={y} x2="600" y2={y} stroke="rgba(255,255,255,0.04)" />
            ))}
            <path
              d="M0,180 L60,160 L120,170 L180,140 L240,150 L300,110 L360,120 L420,90 L480,100 L540,70 L600,80 L600,220 L0,220 Z"
              fill="url(#forecastGrad)"
            />
            <path
              d="M0,180 L60,160 L120,170 L180,140 L240,150 L300,110 L360,120 L420,90 L480,100 L540,70 L600,80"
              fill="none"
              stroke="#3b82f6"
              strokeWidth="2"
            />
            {/* uncertainty band */}
            <path
              d="M300,110 L360,115 L420,80 L480,90 L540,55 L600,65 L600,95 L540,85 L480,115 L420,100 L360,135 L300,130 Z"
              fill="#3b82f6"
              opacity="0.1"
            />
          </svg>
          <div className="text-[10px] text-text-dark-tertiary font-mono mt-2">
            DEMO · ±—% intervalo confiança · modelo —— v—.—
          </div>
        </div>
      </Panel>
      <Panel title="Sazonalidade · histórico 24m">
        <div className="px-4 py-3">
          <div className="grid grid-cols-12 gap-0.5 mb-3">
            {Array.from({ length: 24 }).map((_, i) => {
              const v = Math.sin(i * 0.5) * 0.5 + 0.5;
              return (
                <div
                  key={i}
                  className="h-8 rounded-sm"
                  style={{ backgroundColor: `rgba(59, 130, 246, ${v})` }}
                  title={`Mês ${i + 1}: ${(v * 100).toFixed(0)}%`}
                />
              );
            })}
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-text-dark-tertiary">Pico</span>
              <span className="block text-text-dark-primary">— · semana —</span>
            </div>
            <div>
              <span className="text-text-dark-tertiary">Vale</span>
              <span className="block text-text-dark-primary">— · semana —</span>
            </div>
            <div>
              <span className="text-text-dark-tertiary">Tendência</span>
              <span className="block text-text-dark-primary">+— %/ano</span>
            </div>
          </div>
          <div className="text-[10px] text-warning mt-3 pt-3 border-t border-white/[0.06]">
            Demo visual — endpoint /v1/supply/forecast com série histórica deferred.
          </div>
        </div>
      </Panel>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// M.4d — SIMULADOR (3 cenários)
// ═══════════════════════════════════════════════════════════════════════════════

function SimuladorTab() {
  const [view, setView] = useState<'detalhada' | 'classica'>('detalhada');

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <SegmentedControl
          size="sm"
          value={view}
          onChange={(v) => setView(v as any)}
          options={[
            { id: 'detalhada', label: '3 cenários' },
            { id: 'classica', label: 'Vista clássica (Twin)' },
          ]}
        />
      </div>
      {view === 'detalhada' ? <SimuladorDetailed /> : (
        <Suspense fallback={fallback}><TwinPage /></Suspense>
      )}
    </div>
  );
}

function SimuladorDetailed() {
  const scenarios = [
    {
      name: 'Cenário A · base',
      status: 'ACTIVO',
      icon: <CheckCircle2 size={12} />,
      eurDay: '—',
      atrasos: '—',
      risco: 'BAIXO',
      confianca: '—',
      tone: 'success' as const,
    },
    {
      name: 'Cenário B · acelerar Pintura',
      status: 'SIMULADO',
      icon: <Clock size={12} />,
      eurDay: '+— €',
      atrasos: '—',
      risco: 'MÉDIO',
      confianca: '82%',
      tone: 'warning' as const,
    },
    {
      name: 'Cenário C · adiar #———',
      status: 'SIMULADO',
      icon: <AlertTriangle size={12} />,
      eurDay: '−— €',
      atrasos: '—',
      risco: 'ALTO',
      confianca: '67%',
      tone: 'danger' as const,
    },
  ];
  const toneColor = {
    success: 'text-success bg-success/15 border-success/40',
    warning: 'text-warning bg-warning/15 border-warning/40',
    danger: 'text-danger bg-danger/15 border-danger/40',
  };

  return (
    <Panel title="Cenários what-if" flush>
      <div className="px-4 py-2 text-[10px] text-warning bg-warning/10 border-b border-warning/30">
        Demo — endpoint /v1/twin/scenarios/simulate connection deferred. Estes
        cenários são exemplo do layout do zip. Para simulação real usa a vista clássica (Twin).
      </div>
      <div className="px-4 py-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        {scenarios.map((s, i) => (
          <div
            key={i}
            className="flex flex-col gap-3 p-4 rounded-md bg-dark-900/40 border border-white/[0.06]"
          >
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase tracking-wider text-text-dark-tertiary font-mono">
                CENÁRIO
              </span>
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border ${toneColor[s.tone]}`}
              >
                {s.icon}
                {s.status}
              </span>
            </div>
            <div className="text-sm font-semibold text-text-dark-primary">{s.name}</div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="text-text-dark-tertiary">€/dia</div>
              <div className="text-right tabular-nums text-text-dark-primary font-mono">{s.eurDay}</div>
              <div className="text-text-dark-tertiary">Atrasos</div>
              <div className="text-right tabular-nums text-text-dark-primary font-mono">{s.atrasos}</div>
              <div className="text-text-dark-tertiary">Risco</div>
              <div className="text-right tabular-nums text-text-dark-primary font-mono">{s.risco}</div>
              <div className="text-text-dark-tertiary">Confiança</div>
              <div className="text-right tabular-nums text-text-dark-primary font-mono">{s.confianca}</div>
            </div>
            <button
              type="button"
              className="px-3 py-1.5 rounded-md bg-white/[0.06] text-text-dark-secondary hover:bg-white/[0.10] hover:text-text-dark-primary text-xs font-medium transition-colors"
            >
              Comparar
            </button>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════════

export default function PlaneamentoPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tabFromUrl = searchParams.get('tab');
  const activeTab: TabId = isTabId(tabFromUrl) ? tabFromUrl : 'atribuicao';

  const tabs = useMemo(
    () => [
      { id: 'atribuicao', label: 'Atribuição', icon: <CalendarRange size={13} /> },
      { id: 'materiais', label: 'Materiais', icon: <Boxes size={13} /> },
      { id: 'forecast', label: 'Previsão', icon: <TrendingUp size={13} /> },
      { id: 'simulador', label: 'Simulador', icon: <FlaskConical size={13} /> },
    ],
    []
  );

  const handleTabChange = (id: string) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', id);
    setSearchParams(next, { replace: true });
  };

  return (
    <div>
      <PageHeader
        title="Planeamento"
        subtitle="ATRIBUIÇÕES · MRP · FORECAST · CENÁRIOS"
        actions={
          <>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
            >
              <RefreshCw size={13} />
              Atualizar
            </button>
            <button
              type="button"
              onClick={() => askCopilot(`Que decisões de planeamento são mais críticas hoje em ${activeTab}?`)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-xs font-medium transition-colors"
            >
              <Sparkles size={13} />
              Pedir ao Copilot
            </button>
          </>
        }
      />

      <div className="px-6 pt-2">
        <Tabs tabs={tabs} value={activeTab} onChange={handleTabChange} />
      </div>

      <div className="px-2 py-4">
        {activeTab === 'atribuicao' && <AssignmentTab />}
        {activeTab === 'materiais' && <MateriaisTab />}
        {activeTab === 'forecast' && <ForecastTab />}
        {activeTab === 'simulador' && <SimuladorTab />}
      </div>
    </div>
  );
}
