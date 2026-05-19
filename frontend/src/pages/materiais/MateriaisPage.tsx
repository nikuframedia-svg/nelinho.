/**
 * MateriaisPage — Q.52.K · reconstrução do design NELO.
 *
 * 4 tabs: Catálogo · Prospeção · Entregas · Fornecedores.
 *
 * ZERO MOCKS:
 *   - Catálogo  → /v1/supply/materials/from-bom (REAL). O `supply.material_master`
 *                 está vazio nesta instalação; os materiais reais da NELO são
 *                 os componentes-folha das BOMs (`core.bom_items` × `core.products`),
 *                 com nome, unidade, custo padrão e nº de BOMs que os consomem.
 *                 O stock por armazém vem de `supply.warehouse_stock` (espelho
 *                 da view ERP `produto_stocks_por_armazem`, ETL `stock`); cada
 *                 linha expande para a repartição por armazém.
 *   - Prospeção → /v1/factory-map/shortage-risks (REAL) +
 *                 /v1/supply/reconciliation (REAL).
 *   - Entregas  → SEM endpoint de tracking de PO → empty state explícito.
 *   - Fornecedores → /v1/core/suppliers (REAL).
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
  Search,
  ChevronRight,
  Warehouse,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts/DarkPageLayout';
import { Segmented } from '../../components/dark/Segmented';
import { KPIBig } from '../../components/dark/KPIBig';
import { EmptyState } from '../../components/dark/EmptyState';
import { SkeletonLoader } from '../../components/ui/Skeleton';
import {
  materiaisApi,
  type BomMaterial,
  type ShortageRisk,
  type Supplier,
} from '../../components/materiais/materiaisApi';

type TabId = 'stock' | 'prospecao' | 'entregas' | 'fornecedores';

const TABS: Array<{ value: TabId; label: string; icon: ReactNode }> = [
  { value: 'stock', label: 'Catálogo', icon: <Boxes size={13} /> },
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
// TAB · CATÁLOGO  (materiais derivados da BOM)
// ═══════════════════════════════════════════════════════════════════════════

const CATALOG_GRID = '2.1fr 0.7fr 1.2fr 1fr 1fr';

function StockTab(): ReactNode {
  const [search, setSearch] = useState('');

  const materialsQuery = useQuery({
    queryKey: ['materiais', 'from-bom'],
    queryFn: () => materiaisApi.listMaterialsFromBom({ limit: 2000 }),
  });

  const envelope = materialsQuery.data;
  const all = useMemo(
    () => envelope?.items ?? [],
    [envelope],
  );
  const stockAvailable = envelope?.stock_available ?? false;

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return all;
    return all.filter(
      (m) =>
        m.product_name.toLowerCase().includes(q) ||
        m.product_code.toLowerCase().includes(q),
    );
  }, [all, search]);

  const stats = useMemo(() => {
    let withCost = 0;
    let costSum = 0;
    let withStock = 0;
    for (const m of all) {
      if (m.standard_cost !== null && m.standard_cost > 0) {
        withCost += 1;
        costSum += m.standard_cost;
      }
      if (m.on_hand !== null && m.on_hand > 0) withStock += 1;
    }
    return {
      total: all.length,
      withCost,
      avgCost: withCost > 0 ? costSum / withCost : 0,
      withStock,
    };
  }, [all]);

  if (materialsQuery.isLoading) {
    return <SkeletonLoader count={6} />;
  }
  if (materialsQuery.isError) {
    return (
      <EmptyState
        title="Não foi possível carregar o catálogo de materiais"
        hint="O endpoint /v1/supply/materials/from-bom falhou. Verifica se o backend está a correr."
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
  if (all.length === 0) {
    return (
      <EmptyState
        title="Sem materiais no catálogo"
        hint="Não há componentes-folha nas BOMs deste tenant. Confirma a sincronização do ERP (core.bom_items)."
        icon={<Boxes size={28} />}
      />
    );
  }

  return (
    <div>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <KPIBig
          label="Materiais no catálogo"
          value={stats.total}
          context="Componentes-folha das BOMs"
          status="gray"
        />
        <KPIBig
          label="Com stock"
          value={stockAvailable ? stats.withStock : '—'}
          context={
            stockAvailable
              ? `${stats.withStock} de ${stats.total} com on-hand > 0`
              : 'Stock por armazém não sincronizado'
          }
          status={stockAvailable ? 'green' : 'gray'}
          accent={stockAvailable ? 'green' : undefined}
        />
        <KPIBig
          label="Custo padrão médio"
          value={`€${stats.avgCost.toFixed(2)}`}
          context={`${stats.withCost} de ${stats.total} com custo > 0`}
          status="gray"
        />
      </div>

      {/* ── Banner honesto: estado do stock por armazém ─────────────────── */}
      {!stockAvailable ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 8,
            background: 'var(--yellow-bg)',
            border: '1px solid var(--yellow-bd)',
            borderRadius: 'var(--r-md)',
            padding: '10px 12px',
            marginBottom: 12,
            fontSize: 11.5,
            color: 'var(--fg-2)',
          }}
        >
          <AlertTriangle size={14} color="var(--yellow)" style={{ flexShrink: 0, marginTop: 1 }} />
          <span>
            {envelope?.unavailable_reason ??
              'O stock por armazém ainda não foi sincronizado do ERP NELO.'}
          </span>
        </div>
      ) : (
        envelope?.stock_synced_at && (
          <div
            style={{
              fontSize: 10.5,
              color: 'var(--fg-3)',
              marginBottom: 12,
            }}
          >
            Stock por armazém sincronizado do ERP NELO ·{' '}
            {new Date(envelope.stock_synced_at).toLocaleString('pt-PT')}
          </div>
        )
      )}

      {/* ── Pesquisa ───────────────────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-md)',
          padding: '8px 12px',
          marginBottom: 12,
        }}
      >
        <Search size={14} color="var(--fg-3)" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Procurar por nome ou código…"
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--fg-0)',
            fontSize: 12.5,
          }}
        />
        <span style={{ fontSize: 11, color: 'var(--fg-3)' }}>
          {filtered.length} de {all.length}
        </span>
      </div>

      <div
        style={{
          background: 'var(--bg-1)',
          border: '1px solid var(--bd-1)',
          borderRadius: 'var(--r-lg)',
          overflow: 'hidden',
        }}
      >
        {/* header */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: CATALOG_GRID,
            alignItems: 'center',
            gap: 14,
            padding: '12px 16px',
            borderBottom: '1px solid var(--bd-1)',
            background: 'var(--bg-2)',
            fontSize: 10.5,
            color: 'var(--fg-3)',
            textTransform: 'uppercase',
            letterSpacing: 0.4,
            fontWeight: 600,
          }}
        >
          <div>Material</div>
          <div>Unidade</div>
          <div style={{ textAlign: 'right' }}>Stock total</div>
          <div style={{ textAlign: 'right' }}>Custo padrão</div>
          <div style={{ textAlign: 'right' }}>Usado em</div>
        </div>
        {filtered.length === 0 ? (
          <div
            style={{
              padding: '24px 16px',
              fontSize: 12,
              color: 'var(--fg-3)',
              textAlign: 'center',
            }}
          >
            Nenhum material corresponde a “{search}”.
          </div>
        ) : (
          filtered.map((m) => <CatalogRow key={m.id} material={m} />)
        )}
      </div>
    </div>
  );
}

function CatalogRow({ material: m }: { material: BomMaterial }): ReactNode {
  const [open, setOpen] = useState(false);
  // Só armazéns com stock ≠ 0 interessam para a repartição.
  const warehouses = m.warehouses.filter((w) => w.stock !== 0);
  const expandable = warehouses.length > 0;

  return (
    <div style={{ borderBottom: '1px solid var(--bd-1)' }}>
      <div
        role={expandable ? 'button' : undefined}
        tabIndex={expandable ? 0 : undefined}
        onClick={expandable ? () => setOpen((o) => !o) : undefined}
        onKeyDown={
          expandable
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setOpen((o) => !o);
                }
              }
            : undefined
        }
        style={{
          display: 'grid',
          gridTemplateColumns: CATALOG_GRID,
          alignItems: 'center',
          gap: 14,
          padding: '11px 16px',
          cursor: expandable ? 'pointer' : 'default',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <ChevronRight
            size={13}
            color="var(--fg-3)"
            style={{
              flexShrink: 0,
              opacity: expandable ? 1 : 0,
              transform: open ? 'rotate(90deg)' : 'none',
              transition: 'transform 0.12s',
            }}
          />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12.5, color: 'var(--fg-0)', fontWeight: 500 }}>
              {m.product_name}
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--fg-3)', marginTop: 3 }}>
              {m.product_code}
              {m.category ? ` · ${m.category}` : ''}
              {expandable ? ` · ${warehouses.length} armazém(ns)` : ''}
            </div>
          </div>
        </div>
        <div style={{ fontSize: 12, color: 'var(--fg-2)' }}>
          {m.unit_of_measure}
        </div>
        <div
          className="tabular"
          style={{
            fontSize: 12.5,
            fontWeight: 600,
            textAlign: 'right',
            color:
              m.on_hand === null
                ? 'var(--fg-3)'
                : m.on_hand <= 0
                  ? 'var(--orange)'
                  : 'var(--fg-0)',
          }}
        >
          {m.on_hand === null ? (
            <span style={{ fontWeight: 400 }}>—</span>
          ) : (
            m.on_hand.toLocaleString('pt-PT', { maximumFractionDigits: 1 })
          )}
        </div>
        <div
          className="tabular"
          style={{
            fontSize: 12.5,
            color: m.standard_cost && m.standard_cost > 0 ? 'var(--fg-0)' : 'var(--fg-3)',
            fontWeight: 600,
            textAlign: 'right',
          }}
        >
          {m.standard_cost !== null && m.standard_cost > 0
            ? `€${m.standard_cost.toLocaleString('pt-PT', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}`
            : '—'}
        </div>
        <div
          className="tabular"
          style={{ fontSize: 12, color: 'var(--fg-2)', textAlign: 'right' }}
        >
          {m.used_in_n_boms.toLocaleString('pt-PT')}{' '}
          <span style={{ fontSize: 10, color: 'var(--fg-3)' }}>BOMs</span>
        </div>
      </div>

      {/* ── Repartição por armazém ──────────────────────────────────────── */}
      {open && expandable && (
        <div
          style={{
            background: 'var(--bg-2)',
            padding: '4px 16px 10px 36px',
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          {warehouses.map((w) => (
            <div
              key={w.warehouse_id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '5px 0',
                fontSize: 11.5,
              }}
            >
              <span
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  color: 'var(--fg-2)',
                }}
              >
                <Warehouse size={11} color="var(--fg-3)" />
                {w.warehouse_name}
              </span>
              <span
                className="tabular"
                style={{
                  fontWeight: 600,
                  color: w.stock < 0 ? 'var(--red)' : 'var(--fg-0)',
                }}
              >
                {w.stock.toLocaleString('pt-PT', { maximumFractionDigits: 1 })}{' '}
                <span style={{ fontSize: 9.5, color: 'var(--fg-3)', fontWeight: 400 }}>
                  {m.unit_of_measure}
                </span>
              </span>
            </div>
          ))}
        </div>
      )}
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
