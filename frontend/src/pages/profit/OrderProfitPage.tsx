/**
 * OrderProfitPage — Q.31.A drill-down de lucro ("€30K de onde?").
 *
 * Tabela de margem por barco a partir de GET /v1/profit/orders/margins:
 * casco, produto, receita, COGS, margem €/%, estado. Clicar numa linha
 * abre a decomposição 6-vias (material/labor/machine/setup/overhead/
 * scrap) lida de GET /v1/profit/cogs/orders/{id}.
 *
 * Ordens sem CostCalculation aparecem com "—" e o badge "Sem cálculo" —
 * honesto, ZERO MOCKS, nada de margens inventadas.
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Receipt } from 'lucide-react';
import { cogsApi, profitApi, type OrderMarginRow } from '../../lib/api';
import { Panel, EmptyState, Modal, DarkBadge } from '../../components/dark';
import { SkeletonLoader } from '../../components/ui/Skeleton';

const eur = (n: number | null | undefined): string =>
  n == null
    ? '—'
    : n.toLocaleString('pt-PT', {
        style: 'currency',
        currency: 'EUR',
        maximumFractionDigits: 0,
      });

const pct = (f: number | null): string =>
  f == null ? '—' : `${(f * 100).toFixed(1)}%`;

function marginVariant(margin: number | null): 'success' | 'danger' | 'neutral' {
  if (margin == null) return 'neutral';
  return margin >= 0 ? 'success' : 'danger';
}

export function OrderProfitPage() {
  const [selected, setSelected] = useState<OrderMarginRow | null>(null);

  const marginsQuery = useQuery({
    queryKey: ['profit', 'order-margins'],
    queryFn: () => profitApi.orderMargins({ limit: 200 }),
    staleTime: 60_000,
    retry: 0,
  });

  const rows = marginsQuery.data?.items ?? [];
  const calculatedCount = rows.filter((r) => r.calculated).length;

  return (
    <div className="px-4">
      <Panel
        title="Margem por barco"
        badge={rows.length}
        subtitle={
          rows.length > 0
            ? `${calculatedCount} de ${rows.length} ordens com COGS calculado`
            : undefined
        }
      >
        {marginsQuery.isLoading ? (
          <SkeletonLoader count={6} />
        ) : marginsQuery.isError ? (
          <EmptyState
            title="Não foi possível carregar as margens"
            hint="O endpoint /v1/profit/orders/margins não respondeu. Tenta atualizar."
            mascot={false}
            icon={<Receipt size={28} />}
          />
        ) : rows.length === 0 ? (
          <EmptyState
            title="Sem ordens de produção"
            hint="Quando houver ordens, a margem por barco aparece aqui."
            icon={<Receipt size={28} />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-text-dark-tertiary border-b border-white/[0.08]">
                  <th className="py-2 px-2">Casco</th>
                  <th className="py-2 px-2">Produto</th>
                  <th className="py-2 px-2 text-right">Receita</th>
                  <th className="py-2 px-2 text-right">COGS</th>
                  <th className="py-2 px-2 text-right">Margem €</th>
                  <th className="py-2 px-2 text-right">Margem %</th>
                  <th className="py-2 px-2">Estado</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr
                    key={r.order_id}
                    onClick={() => r.calculated && setSelected(r)}
                    className={`border-b border-white/[0.04] ${
                      r.calculated
                        ? 'cursor-pointer hover:bg-white/[0.03]'
                        : 'opacity-60'
                    }`}
                  >
                    <td className="py-2 px-2 font-medium text-text-dark-primary tabular-nums">
                      #{r.hull}
                    </td>
                    <td className="py-2 px-2 text-text-dark-secondary truncate max-w-[220px]">
                      {r.product_name}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums text-text-dark-secondary">
                      {eur(r.revenue_eur)}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums text-text-dark-secondary">
                      {eur(r.total_cogs)}
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums">
                      <DarkBadge variant={marginVariant(r.margin_eur)} size="sm">
                        {eur(r.margin_eur)}
                      </DarkBadge>
                    </td>
                    <td className="py-2 px-2 text-right tabular-nums text-text-dark-secondary">
                      {pct(r.margin_pct)}
                    </td>
                    <td className="py-2 px-2">
                      {r.calculated ? (
                        <span className="text-[11px] text-text-dark-tertiary">
                          {r.status}
                        </span>
                      ) : (
                        <DarkBadge variant="neutral" size="sm">
                          Sem cálculo
                        </DarkBadge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {selected && (
        <CostBreakdownModal row={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}

// ─── Modal — decomposição 6-vias do COGS ─────────────────────────────────

const COST_LABELS: Record<string, string> = {
  material: 'Material',
  labor: 'Mão-de-obra',
  machine: 'Máquina',
  setup: 'Setup',
  overhead: 'Overhead',
  scrap: 'Sucata',
};

function CostBreakdownModal({
  row,
  onClose,
}: {
  row: OrderMarginRow;
  onClose: () => void;
}) {
  const cogsQuery = useQuery({
    queryKey: ['profit', 'cogs', row.order_id],
    queryFn: () => cogsApi.getOrderCOGS(row.order_id),
    retry: 0,
  });

  const breakdown: Record<string, number> =
    cogsQuery.data?.breakdown ?? {};

  return (
    <Modal
      open
      onClose={onClose}
      title={`Decomposição do custo — barco #${row.hull}`}
      size="md"
    >
      <div className="space-y-3">
        <div className="text-xs text-text-dark-tertiary">{row.product_name}</div>

        {cogsQuery.isLoading ? (
          <SkeletonLoader count={6} />
        ) : cogsQuery.isError ? (
          <div className="text-sm text-danger">
            Sem decomposição de COGS para esta ordem.
          </div>
        ) : (
          <table className="w-full text-sm">
            <tbody>
              {Object.keys(COST_LABELS).map((key) => (
                <tr key={key} className="border-b border-white/[0.04]">
                  <td className="py-1.5 text-text-dark-secondary">
                    {COST_LABELS[key]}
                  </td>
                  <td className="py-1.5 text-right tabular-nums text-text-dark-primary">
                    {eur(breakdown[key] ?? 0)}
                  </td>
                </tr>
              ))}
              <tr className="font-semibold">
                <td className="py-2 text-text-dark-primary">Total COGS</td>
                <td className="py-2 text-right tabular-nums text-text-dark-primary">
                  {eur(row.total_cogs)}
                </td>
              </tr>
            </tbody>
          </table>
        )}

        <div className="grid grid-cols-3 gap-2 pt-1">
          <Metric label="Receita" value={eur(row.revenue_eur)} />
          <Metric label="COGS" value={eur(row.total_cogs)} />
          <Metric
            label="Margem"
            value={eur(row.margin_eur)}
            variant={marginVariant(row.margin_eur)}
          />
        </div>
      </div>
    </Modal>
  );
}

function Metric({
  label,
  value,
  variant = 'neutral',
}: {
  label: string;
  value: string;
  variant?: 'success' | 'danger' | 'neutral';
}) {
  const color =
    variant === 'success'
      ? 'var(--green)'
      : variant === 'danger'
        ? 'var(--red)'
        : 'var(--fg-1)';
  return (
    <div className="rounded-md bg-dark-900/40 border border-white/[0.06] px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-text-dark-tertiary">
        {label}
      </div>
      <div className="text-sm font-semibold tabular-nums mt-0.5" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

export default OrderProfitPage;
