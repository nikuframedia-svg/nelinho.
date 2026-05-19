// MateriaisPage · StockTab (Q.60.V). ZERO MOCKS — endpoints reais.
import { useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Boxes, AlertTriangle, Search, ChevronRight, Warehouse } from 'lucide-react';
import { KPIBig } from '../../../components/dark/KPIBig';
import { EmptyState } from '../../../components/dark/EmptyState';
import { SkeletonLoader } from '../../../components/ui/Skeleton';
import { materiaisApi, type BomMaterial } from '../../../components/materiais/materiaisApi';
import { primaryBtn } from '../materiaisShared';

export const CATALOG_GRID = '2fr 0.6fr 1fr 1.3fr 0.9fr 0.8fr';

/** Q.53.J — cor da etiqueta de confiança da previsão de rutura. */
export const STOCKOUT_CONFIDENCE_LABEL: Record<string, string> = {
  high: 'fiável',
  medium: 'estimada',
  low: 'incerta',
  none: '—',
};

export function StockTab(): ReactNode {
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
          <div style={{ textAlign: 'right' }}>Rutura prevista</div>
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

export function CatalogRow({ material: m }: { material: BomMaterial }): ReactNode {
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
        <StockoutCell material={m} />
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

/**
 * StockoutCell — Q.53.J · data prevista de rutura de um material.
 *
 * O endpoint /v1/supply/materials/from-bom traz `predicted_stockout_date`,
 * `stockout_confidence` e `avg_daily_consumption` calculados a partir do
 * consumo histórico real do ledger. Sem histórico suficiente o backend
 * devolve a data `null` com confiança "none" — mostramos "—" honesto.
 */
export function StockoutCell({ material: m }: { material: BomMaterial }): ReactNode {
  const date = m.predicted_stockout_date;
  const confidence = m.stockout_confidence ?? 'none';

  if (!date || confidence === 'none') {
    return (
      <div
        style={{
          fontSize: 11.5,
          color: 'var(--fg-3)',
          textAlign: 'right',
        }}
        title="Sem histórico de consumo suficiente para prever a rutura"
      >
        —
      </div>
    );
  }

  // Dias até à rutura → cor: ≤7d vermelho, ≤21d amarelo, senão neutro.
  const days = Math.round(
    (new Date(date).getTime() - Date.now()) / 86_400_000,
  );
  const colour =
    days <= 7 ? 'var(--red)' : days <= 21 ? 'var(--yellow)' : 'var(--fg-1)';

  return (
    <div style={{ textAlign: 'right', lineHeight: 1.35 }}>
      <div
        className="tabular"
        style={{ fontSize: 12, fontWeight: 600, color: colour }}
      >
        {new Date(date).toLocaleDateString('pt-PT', {
          day: '2-digit',
          month: '2-digit',
          year: '2-digit',
        })}
      </div>
      <div style={{ fontSize: 10, color: 'var(--fg-3)' }}>
        {days >= 0 ? `~${days}d` : 'vencida'}
        {' · '}
        {STOCKOUT_CONFIDENCE_LABEL[confidence] ?? confidence}
        {m.avg_daily_consumption && m.avg_daily_consumption > 0
          ? ` · ${m.avg_daily_consumption.toLocaleString('pt-PT', {
              maximumFractionDigits: 1,
            })}/dia`
          : ''}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// TAB · PROSPEÇÃO  (shortage-risks + reconciliações)
// ═══════════════════════════════════════════════════════════════════════════
