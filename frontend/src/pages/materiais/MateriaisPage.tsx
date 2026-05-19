/**
 * MateriaisPage — Q.52.K · reconstrução do design NELO.
 *
 * 4 tabs: Stock · Prospeção · Entregas · Fornecedores.
 *
 * ZERO MOCKS:
 *   - Stock     → /v1/supply/materials (master) + .../position (on-hand,
 *                 PARTIAL: posições degradadas mostram "—").
 *   - Prospeção → /v1/factory-map/shortage-risks (REAL) +
 *                 /v1/supply/reconciliation (REAL).
 *   - Entregas  → SEM endpoint de tracking de PO → empty state explícito.
 *   - Fornecedores → /v1/core/suppliers (REAL).
 *
 * Mutações de stock vivem no MaterialDetailSheet e invalidam a query
 * ['materiais'].
 */

import { useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Boxes,
  Building2,
  Target,
  Truck,
  AlertTriangle,
  Star,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts/DarkPageLayout';
import { Segmented } from '../../components/dark/Segmented';
import { KPIBig } from '../../components/dark/KPIBig';
import { EmptyState } from '../../components/dark/EmptyState';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import {
  materiaisApi,
  type MaterialPosition,
  type ShortageRisk,
  type Supplier,
} from '../../components/materiais/materiaisApi';
import {
  StockRow,
  StockRowHeader,
  stateFor,
  type StockRowData,
} from '../../components/materiais/StockRow';
import { MaterialDetailSheet } from '../../components/materiais/MaterialDetailSheet';

type TabId = 'stock' | 'prospecao' | 'entregas' | 'fornecedores';

const TABS: Array<{ value: TabId; label: string; icon: ReactNode }> = [
  { value: 'stock', label: 'Stock', icon: <Boxes size={13} /> },
  { value: 'prospecao', label: 'Prospeção', icon: <Target size={13} /> },
  { value: 'entregas', label: 'Entregas', icon: <Truck size={13} /> },
  { value: 'fornecedores', label: 'Fornecedores', icon: <Building2 size={13} /> },
];

// ═══════════════════════════════════════════════════════════════════════════
// PAGE
// ═══════════════════════════════════════════════════════════════════════════

export default function MateriaisPage(): ReactNode {
  const [tab, setTab] = useState<TabId>('stock');

  return (
    <DarkPageLayout
      title="Materiais"
      subtitle="Stock, prospeção MRP, entregas, fornecedores"
      icon={<Boxes size={18} />}
    >
      <div style={{ marginBottom: 16 }}>
        <Segmented options={TABS} value={tab} onChange={setTab} />
      </div>

      {tab === 'stock' && <StockTab />}
      {tab === 'prospecao' && <ProspecaoTab />}
      {tab === 'entregas' && <EntregasTab />}
      {tab === 'fornecedores' && <FornecedoresTab />}
    </DarkPageLayout>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · STOCK
// ═══════════════════════════════════════════════════════════════════════════

function StockTab(): ReactNode {
  const [selectedSku, setSelectedSku] = useState<string | null>(null);

  const materialsQuery = useQuery({
    queryKey: ['materiais', 'list'],
    queryFn: () => materiaisApi.listMaterials({ active_only: true }),
  });

  const materials = useMemo(
    () => materialsQuery.data ?? [],
    [materialsQuery.data],
  );

  // Posições de todos os SKUs — PARTIAL: o backend pode degradar.
  const positionsQuery = useQuery({
    queryKey: ['materiais', 'positions', materials.map((m) => m.sku_id)],
    queryFn: async () => {
      const entries = await Promise.all(
        materials.map(async (m) => {
          try {
            const p = await materiaisApi.getPosition(m.sku_id);
            return [m.sku_id, p] as const;
          } catch {
            return [m.sku_id, null] as const;
          }
        }),
      );
      return Object.fromEntries(entries) as Record<string, MaterialPosition | null>;
    },
    enabled: materials.length > 0,
    retry: 0,
  });

  const rows: StockRowData[] = useMemo(
    () =>
      materials.map((m) => ({
        material: m,
        position: positionsQuery.data?.[m.sku_id] ?? null,
      })),
    [materials, positionsQuery.data],
  );

  const counts = useMemo(() => {
    let ok = 0;
    let low = 0;
    let crit = 0;
    let unknown = 0;
    for (const r of rows) {
      const s = stateFor(r);
      if (s === 'ok') ok += 1;
      else if (s === 'low') low += 1;
      else if (s === 'critical' || s === 'out') crit += 1;
      else unknown += 1;
    }
    return { ok, low, crit, unknown };
  }, [rows]);

  const selectedMaterial =
    materials.find((m) => m.sku_id === selectedSku) ?? null;

  if (materialsQuery.isLoading) {
    return <SkeletonLoader count={6} />;
  }
  if (materialsQuery.isError) {
    return (
      <EmptyState
        title="Não foi possível carregar os materiais"
        hint="O endpoint /v1/supply/materials falhou. Verifica se o backend está a correr."
        icon={<Boxes size={28} />}
        action={
          <button
            type="button"
            onClick={() => materialsQuery.refetch()}
            style={primaryBtn}
          >
            Tentar novamente
          </button>
        }
      />
    );
  }
  if (materials.length === 0) {
    return (
      <EmptyState
        title="Sem materiais registados"
        hint="Ainda não há materiais no master de stock para este tenant. Cria materiais ou confirma a sincronização do ERP."
        icon={<Boxes size={28} />}
      />
    );
  }

  return (
    <div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <KPIBig
          label="Materiais OK"
          value={counts.ok}
          unit={`/ ${materials.length}`}
          status="green"
          accent="green"
        />
        <KPIBig label="Baixos" value={counts.low} status="yellow" accent="yellow" />
        <KPIBig
          label="Críticos / esgotados"
          value={counts.crit}
          status="red"
          accent="red"
        />
        <KPIBig
          label="Sem leitura de posição"
          value={counts.unknown}
          context={
            counts.unknown > 0
              ? 'Posição PARTIAL — on-hand indisponível'
              : 'Todas as posições disponíveis'
          }
          status="gray"
        />
      </div>

      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          overflow: 'hidden',
        }}
      >
        <StockRowHeader />
        {rows.map((r) => (
          <StockRow
            key={r.material.sku_id}
            data={r}
            onSelect={setSelectedSku}
            onOrder={setSelectedSku}
          />
        ))}
      </div>

      {positionsQuery.isLoading && (
        <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 10 }}>
          A ler posições de stock…
        </div>
      )}

      <MaterialDetailSheet
        material={selectedMaterial}
        onClose={() => setSelectedSku(null)}
      />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · PROSPEÇÃO  (shortage-risks + reconciliações)
// ═══════════════════════════════════════════════════════════════════════════

function normalizeRisks(
  raw: ShortageRisk[] | { items?: ShortageRisk[]; data?: ShortageRisk[] } | undefined,
): ShortageRisk[] {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw;
  return raw.items ?? raw.data ?? [];
}

function ProspecaoTab(): ReactNode {
  const risksQuery = useQuery({
    queryKey: ['materiais', 'shortage-risks'],
    queryFn: () => materiaisApi.shortageRisks(14),
    retry: 0,
  });

  const reconQuery = useQuery({
    queryKey: ['materiais', 'reconciliation'],
    queryFn: () => materiaisApi.listReconciliations({ limit: 50 }),
    retry: 0,
  });

  const risks = useMemo(
    () => normalizeRisks(risksQuery.data),
    [risksQuery.data],
  );
  const recons = reconQuery.data ?? [];
  const unresolved = recons.filter((r) => !r.resolved);

  if (risksQuery.isLoading) {
    return <SkeletonLoader count={4} />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
      {/* ── Risco de ruptura ─────────────────────────────────────────── */}
      <section
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionTitle
          icon={<Target size={14} />}
          title="Risco de ruptura · próximos 14 dias"
          subtitle="Detetor ROP — materiais que ficam abaixo do ponto de encomenda"
        />
        {risksQuery.isError ? (
          <EmptyState
            title="Não foi possível avaliar o risco"
            hint="O endpoint /v1/factory-map/shortage-risks falhou."
            icon={<AlertTriangle size={24} />}
            size="sm"
            action={
              <button type="button" onClick={() => risksQuery.refetch()} style={primaryBtn}>
                Tentar novamente
              </button>
            }
          />
        ) : risks.length === 0 ? (
          <EmptyState
            title="Sem risco de ruptura"
            hint="Nenhum material está projetado para ficar abaixo do ROP nos próximos 14 dias."
            icon={<Target size={24} />}
            size="sm"
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {risks.map((r, i) => (
              <div
                key={r.sku_id ?? i}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 110px 110px 120px',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 12px',
                  background: 'var(--bg-2)',
                  borderRadius: 'var(--r-sm)',
                }}
              >
                <div>
                  <div style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
                    {r.name ?? r.sku_id}
                  </div>
                  <div style={{ fontSize: 10.5, color: 'var(--fg-3)' }}>{r.sku_id}</div>
                </div>
                <div className="tabular" style={{ fontSize: 12, color: 'var(--fg-2)' }}>
                  {r.on_hand !== undefined ? `on-hand ${r.on_hand}` : '—'}
                </div>
                <div className="tabular" style={{ fontSize: 12, color: 'var(--fg-2)' }}>
                  {r.rop !== undefined && r.rop !== null ? `ROP ${r.rop}` : '—'}
                </div>
                <div
                  className="tabular"
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color:
                      r.days_to_stockout !== undefined && r.days_to_stockout !== null
                        ? r.days_to_stockout <= 3
                          ? 'var(--red)'
                          : 'var(--yellow)'
                        : 'var(--fg-3)',
                  }}
                >
                  {r.days_to_stockout !== undefined && r.days_to_stockout !== null
                    ? `acaba ~${Math.round(r.days_to_stockout)}d`
                    : 'sem estimativa'}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Reconciliações ───────────────────────────────────────────── */}
      <section
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          padding: 18,
        }}
      >
        <SectionTitle
          title="Reconciliações de inventário"
          subtitle="Contagem física vs teórica — variâncias por resolver"
        />
        {reconQuery.isLoading ? (
          <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>A carregar…</div>
        ) : reconQuery.isError ? (
          <EmptyState
            title="Reconciliações indisponíveis"
            hint="O endpoint /v1/supply/reconciliation falhou."
            size="sm"
          />
        ) : recons.length === 0 ? (
          <EmptyState
            title="Sem reconciliações"
            hint="Ainda não foi submetida nenhuma contagem física de stock."
            size="sm"
          />
        ) : (
          <div>
            <div style={{ fontSize: 11.5, color: 'var(--fg-2)', marginBottom: 10 }}>
              {unresolved.length} por resolver de {recons.length} no total
            </div>
            {recons.map((r) => (
              <div
                key={r.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 100px 100px 110px 90px',
                  alignItems: 'center',
                  gap: 12,
                  padding: '8px 0',
                  borderBottom: '1px solid var(--bd-1)',
                  fontSize: 11.5,
                }}
              >
                <span style={{ color: 'var(--fg-1)', fontWeight: 500 }}>{r.sku_id}</span>
                <span className="tabular" style={{ color: 'var(--fg-2)' }}>
                  teór. {r.theoretical_qty}
                </span>
                <span className="tabular" style={{ color: 'var(--fg-2)' }}>
                  fís. {r.physical_qty}
                </span>
                <span
                  className="tabular"
                  style={{
                    color: r.variance_qty === 0 ? 'var(--fg-3)' : 'var(--orange)',
                  }}
                >
                  Δ {r.variance_qty > 0 ? '+' : ''}
                  {r.variance_qty}
                </span>
                <span
                  style={{
                    color: r.resolved ? 'var(--green)' : 'var(--yellow)',
                    fontWeight: 500,
                  }}
                >
                  {r.resolved ? 'Resolvida' : 'Aberta'}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · ENTREGAS  (sem endpoint — empty state explícito)
// ═══════════════════════════════════════════════════════════════════════════

function EntregasTab(): ReactNode {
  return (
    <EmptyState
      title="Tracking de entregas ainda não disponível"
      hint={
        'Não existe endpoint de tracking de encomendas de fornecedor (receção de PO, ETA confirmada). ' +
        'Está identificado como gap de backend Q.53 — quando o endpoint existir, esta tab mostra as ' +
        'próximas entregas com data, fornecedor, material e estado de confirmação.'
      }
      icon={<Truck size={28} />}
    />
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · FORNECEDORES
// ═══════════════════════════════════════════════════════════════════════════

function FornecedoresTab(): ReactNode {
  const suppliersQuery = useQuery({
    queryKey: ['materiais', 'suppliers'],
    queryFn: () => materiaisApi.listSuppliers(),
  });

  const suppliers = suppliersQuery.data ?? [];

  if (suppliersQuery.isLoading) {
    return <SkeletonLoader count={3} />;
  }
  if (suppliersQuery.isError) {
    return (
      <EmptyState
        title="Não foi possível carregar os fornecedores"
        hint="O endpoint /v1/core/suppliers falhou."
        icon={<Building2 size={28} />}
        action={
          <button type="button" onClick={() => suppliersQuery.refetch()} style={primaryBtn}>
            Tentar novamente
          </button>
        }
      />
    );
  }
  if (suppliers.length === 0) {
    return (
      <EmptyState
        title="Sem fornecedores registados"
        hint="Ainda não há fornecedores no master para este tenant."
        icon={<Building2 size={28} />}
      />
    );
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: 12,
      }}
    >
      {suppliers.map((s) => (
        <SupplierCard key={s.id} supplier={s} />
      ))}
    </div>
  );
}

function SupplierCard({ supplier }: { supplier: Supplier }): ReactNode {
  const rating = supplier.quality_rating;
  return (
    <div
      style={{
        background: 'var(--bg-1)',
        border: '1px solid var(--bd-1)',
        borderRadius: 'var(--r-lg)',
        padding: 16,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}
      >
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
            {supplier.supplier_name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--fg-3)', marginTop: 2 }}>
            {supplier.supplier_code} · {supplier.material_category}
          </div>
        </div>
        {supplier.is_preferred && (
          <span
            style={{
              fontSize: 10,
              color: 'var(--accent)',
              background: 'var(--accent-bg)',
              border: '1px solid var(--accent-bd)',
              borderRadius: 5,
              padding: '2px 6px',
              fontWeight: 600,
            }}
          >
            Preferencial
          </span>
        )}
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 10,
          marginTop: 12,
        }}
      >
        <div>
          <div
            style={{
              fontSize: 10,
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
            }}
          >
            Qualidade
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              marginTop: 3,
            }}
          >
            {rating !== null ? (
              <>
                <Star
                  size={14}
                  color={rating >= 4 ? 'var(--green)' : rating >= 3 ? 'var(--yellow)' : 'var(--red)'}
                  fill="currentColor"
                />
                <span
                  className="tabular"
                  style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-0)' }}
                >
                  {rating}/5
                </span>
              </>
            ) : (
              <span style={{ fontSize: 13, color: 'var(--fg-3)' }}>sem rating</span>
            )}
          </div>
        </div>
        <div>
          <div
            style={{
              fontSize: 10,
              color: 'var(--fg-3)',
              textTransform: 'uppercase',
              letterSpacing: 0.4,
            }}
          >
            Lead time
          </div>
          <div
            className="tabular"
            style={{ fontSize: 16, fontWeight: 600, color: 'var(--fg-0)', marginTop: 3 }}
          >
            {supplier.lead_time_days}d
          </div>
        </div>
      </div>

      {(supplier.contact_name || supplier.city) && (
        <div
          style={{
            fontSize: 10.5,
            color: 'var(--fg-3)',
            marginTop: 12,
            paddingTop: 10,
            borderTop: '1px solid var(--bd-1)',
          }}
        >
          {supplier.contact_name ?? ''}
          {supplier.contact_name && supplier.city ? ' · ' : ''}
          {[supplier.city, supplier.country].filter(Boolean).join(', ')}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════

function SectionTitle({
  icon,
  title,
  subtitle,
}: {
  icon?: ReactNode;
  title: string;
  subtitle?: string;
}): ReactNode {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        {icon && <span style={{ color: 'var(--fg-2)' }}>{icon}</span>}
        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--fg-0)' }}>
          {title}
        </span>
      </div>
      {subtitle && (
        <div style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 3 }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}

const primaryBtn: React.CSSProperties = {
  padding: '6px 14px',
  fontSize: 12,
  fontWeight: 500,
  borderRadius: 'var(--r-sm)',
  background: 'var(--accent)',
  color: '#fff',
  border: 'none',
  cursor: 'pointer',
};
