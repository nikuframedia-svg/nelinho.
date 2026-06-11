/**
 * Q.173.AC — Página /materiais (reconstruída).
 *
 * A página foi apagada no lean A1 (commit 2def464) por ser órfã.
 * A Fase 5 criou os dados que lhe faltavam — shortage-forecast + BOM materials + POs.
 *
 * 3 tabs via ?tab=:
 *   ruturas   — previsão de ruturas por data_rutura_prevista (default)
 *   stock     — catálogo BOM pesquisável + override min-stock
 *   encomendas — POs abertas com ETA
 */

import { useState, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  useQuery,
  useMutation,
  useQueryClient,
} from '@tanstack/react-query';
import {
  Package,
  AlertTriangle,
  ShoppingCart,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Search,
  Edit2,
  Check,
  X,
} from 'lucide-react';
import { PageHeader, Tabs, EmptyState, DarkBadge } from '../../components/dark';
import { DarkCard } from '../../components/dark/DarkCard';
import { supplyKeys } from '../../lib/api/keys';
import { materiaisApi } from '../../lib/api/supplyApi';
import {
  sugestaoVariant,
  sugestaoLabel,
  minStockSourceLabel,
  minStockSourceVariant,
  formatDataRutura,
  diasAteRutura,
  urgenciaMaterial,
} from './materiaisHelpers';
import type { MaterialEmRisco, BomMaterialItem } from '../../lib/api/supplyApi';

type TabId = 'ruturas' | 'stock' | 'encomendas';

// ─── Tab Ruturas ────────────────────────────────────────────────────────────

function RuturasTab() {
  const [horizonte, setHorizonte] = useState(60);
  const [filtroTexto, setFiltroTexto] = useState('');
  const [filtroSugestao, setFiltroSugestao] = useState<string>('');
  const [expandido, setExpandido] = useState<string | null>(null);

  const q = useQuery({
    queryKey: supplyKeys.shortageForecast(horizonte),
    queryFn: () => materiaisApi.shortageForecast(horizonte),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const materiais = useMemo(() => {
    if (!q.data) return [];
    let lista = [...q.data.materiais_em_risco];
    // ordenar por urgência (mais urgente primeiro)
    lista.sort((a, b) => urgenciaMaterial(a) - urgenciaMaterial(b));
    if (filtroTexto.trim()) {
      const txt = filtroTexto.toLowerCase();
      lista = lista.filter(
        (m) =>
          m.product_name.toLowerCase().includes(txt) ||
          m.product_code.toLowerCase().includes(txt),
      );
    }
    if (filtroSugestao) {
      lista = lista.filter((m) => m.sugestao === filtroSugestao);
    }
    return lista;
  }, [q.data, filtroTexto, filtroSugestao]);

  if (q.isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-text-dark-tertiary">
        <RefreshCw size={18} className="animate-spin mr-2" />
        A calcular previsão de ruturas…
      </div>
    );
  }

  if (q.isError) {
    return (
      <EmptyState
        mascot={false}
        icon={<AlertTriangle size={32} />}
        title="Erro ao carregar previsão de ruturas"
        hint="Verifica se o backend está acessível e tenta novamente."
        action={
          <button
            type="button"
            className="btn-dark-sm"
            onClick={() => q.refetch()}
          >
            Tentar novamente
          </button>
        }
      />
    );
  }

  const meta = q.data;
  const commitShaShort = meta?.commit_sha?.slice(0, 8) ?? '—';
  const geradoEm = meta?.gerado_em
    ? new Date(meta.gerado_em).toLocaleTimeString('pt-PT', {
        hour: '2-digit',
        minute: '2-digit',
      })
    : '—';

  if (materiais.length === 0 && !filtroTexto && !filtroSugestao) {
    return (
      <EmptyState
        mascot={false}
        icon={<Package size={32} />}
        title="Sem ruturas previstas"
        hint={`Nenhum material em risco nos próximos ${horizonte} dias.`}
      />
    );
  }

  return (
    <div className="p-6 space-y-4">
      {/* Meta banner */}
      {meta && (
        <div
          className="text-xs text-text-dark-tertiary px-1 pb-2"
          style={{ borderBottom: '1px solid var(--bd-1)' }}
        >
          baseado no plano{' '}
          <span className="font-mono text-text-dark-secondary">{commitShaShort}</span>
          {' · '}gerado às {geradoEm}
          {meta.excluidos_sem_stock_rastreado > 0 && (
            <> · <span className="text-text-dark-tertiary">{meta.excluidos_sem_stock_rastreado} pseudo-componentes excluídos</span></>
          )}
          {meta.fontes.length > 0 && (
            <> · fontes: {meta.fontes.join(', ')}</>
          )}
        </div>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-48">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-text-dark-tertiary pointer-events-none"
          />
          <input
            type="text"
            placeholder="Pesquisar material…"
            className="w-full pl-8 pr-3 py-2 rounded-md text-sm bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300"
            value={filtroTexto}
            onChange={(e) => setFiltroTexto(e.target.value)}
          />
        </div>
        <select
          className="px-3 py-2 rounded-md text-sm bg-white text-slate-900 border border-slate-300"
          value={filtroSugestao}
          onChange={(e) => setFiltroSugestao(e.target.value)}
          aria-label="Filtrar por tipo de sugestão"
        >
          <option value="">Todas as sugestões</option>
          <option value="compra">Compra</option>
          <option value="transferencia">Transferência</option>
          <option value="replaneamento">Replaneamento</option>
        </select>
        <div className="flex items-center gap-2 ml-auto">
          <label className="text-xs text-text-dark-tertiary" htmlFor="horizonte-select">
            Horizonte:
          </label>
          <select
            id="horizonte-select"
            className="px-2 py-1.5 rounded-md text-xs bg-white text-slate-900 border border-slate-300"
            value={horizonte}
            onChange={(e) => setHorizonte(Number(e.target.value))}
          >
            <option value={14}>14 dias</option>
            <option value={30}>30 dias</option>
            <option value={60}>60 dias</option>
            <option value={90}>90 dias</option>
          </select>
        </div>
      </div>

      {/* Resultados */}
      {materiais.length === 0 ? (
        <EmptyState
          size="sm"
          mascot={false}
          icon={<Search size={24} />}
          title="Sem resultados para este filtro"
        />
      ) : (
        <div className="space-y-2">
          {materiais.map((m) => (
            <MaterialRiscoCard
              key={m.product_code}
              m={m}
              expandido={expandido === m.product_code}
              onToggle={() =>
                setExpandido(
                  expandido === m.product_code ? null : m.product_code,
                )
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function MaterialRiscoCard({
  m,
  expandido,
  onToggle,
}: {
  m: MaterialEmRisco;
  expandido: boolean;
  onToggle: () => void;
}) {
  const dias = diasAteRutura(m.data_rutura_prevista);
  const dataFormatada = formatDataRutura(m.data_rutura_prevista);
  const dataLimiteFormatada = formatDataRutura(m.data_limite_encomenda);

  return (
    <DarkCard padding="sm" className="hover:ring-1 hover:ring-bd-2 transition-shadow">
      {/* Linha principal */}
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0 space-y-1.5">
          {/* Nome + código */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-medium text-sm text-text-dark-primary truncate max-w-xs">
              {m.product_name}
            </span>
            <span className="font-mono text-xs text-text-dark-tertiary">
              {m.product_code}
            </span>
          </div>

          {/* Linha de dados */}
          <div className="flex flex-wrap items-center gap-2 text-xs text-text-dark-secondary">
            {/* Stock atual */}
            <span title={m.stock_negativo_erp ? 'Stock negativo no ERP (acerto pendente)' : undefined}>
              Stock:{' '}
              {m.stock_negativo_erp ? (
                <DarkBadge variant="danger" size="sm">
                  {m.stock_atual.toLocaleString('pt-PT')} ⚠ negativo ERP
                </DarkBadge>
              ) : (
                <strong className="tabular-nums">{m.stock_atual.toLocaleString('pt-PT')}</strong>
              )}
            </span>

            {/* Mínimo com source */}
            <span>
              Mín:{' '}
              <strong className="tabular-nums">{m.min_stock.toLocaleString('pt-PT')}</strong>{' '}
              <DarkBadge variant={minStockSourceVariant(m.min_stock_source)} size="sm">
                {minStockSourceLabel(m.min_stock_source)}
              </DarkBadge>
            </span>

            {/* Data de rutura */}
            {dataFormatada && (
              <span>
                Rutura:{' '}
                <strong>
                  {dataFormatada}
                  {dias !== null && (
                    <span className={`ml-1 ${dias <= 7 ? 'text-red-400' : dias <= 30 ? 'text-yellow-400' : 'text-text-dark-secondary'}`}>
                      ({dias < 0 ? 'passou' : `em ${dias}d`})
                    </span>
                  )}
                </strong>
              </span>
            )}

            {/* Défice */}
            {m.defice > 0 && (
              <span className="text-red-400 tabular-nums">
                Défice: {m.defice.toLocaleString('pt-PT')}
              </span>
            )}
          </div>

          {/* Sugestão */}
          <div className="flex items-center gap-2 flex-wrap">
            <DarkBadge variant={sugestaoVariant(m.sugestao)} size="sm">
              {sugestaoLabel(m.sugestao)}
            </DarkBadge>
            <span className="text-xs text-text-dark-secondary">{m.sugestao_detalhe}</span>
            {dataLimiteFormatada && m.sugestao === 'compra' && (
              <span className="text-xs text-red-400">
                Prazo limite: {dataLimiteFormatada}
              </span>
            )}
          </div>
        </div>

        {/* Botão expandir */}
        <button
          type="button"
          className="text-text-dark-tertiary hover:text-text-dark-primary p-1 flex-shrink-0"
          onClick={onToggle}
          aria-label={expandido ? 'Recolher detalhes' : 'Ver barcos afetados'}
          title={expandido ? 'Recolher' : `${m.ordens_afetadas.length} barcos afetados`}
        >
          {expandido ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {/* Expansão: barcos afetados */}
      {expandido && m.ordens_afetadas.length > 0 && (
        <div
          className="mt-3 pt-3 space-y-1"
          style={{ borderTop: '1px solid var(--bd-1)' }}
        >
          <div className="text-xs font-medium text-text-dark-secondary mb-1.5">
            Barcos afetados ({m.ordens_afetadas.length}):
          </div>
          {m.ordens_afetadas.map((o) => (
            <div
              key={o.order_id}
              className="flex items-center gap-3 text-xs text-text-dark-secondary"
            >
              <span className="font-mono text-text-dark-tertiary">{o.order_id}</span>
              <span className="truncate">{o.modelo}</span>
              <span className="ml-auto text-text-dark-tertiary">
                {formatDataRutura(o.start_time)}
              </span>
            </div>
          ))}
          {m.consumo_mediano_por_barco != null && (
            <div className="text-xs text-text-dark-tertiary mt-2">
              Consumo mediano/barco: {m.consumo_mediano_por_barco.toLocaleString('pt-PT')}
            </div>
          )}
          {m.outros_armazens.length > 0 && (
            <div className="text-xs text-text-dark-tertiary mt-1">
              Outros armazéns:{' '}
              {m.outros_armazens
                .map((aw) => `${aw.warehouse_name} (${aw.stock.toLocaleString('pt-PT')})`)
                .join(', ')}
            </div>
          )}
        </div>
      )}
    </DarkCard>
  );
}

// ─── Tab Stock ──────────────────────────────────────────────────────────────

function StockTab() {
  const [pesquisa, setPesquisa] = useState('');
  const [editarSku, setEditarSku] = useState<string | null>(null);
  const [novoMin, setNovoMin] = useState('');
  const queryClient = useQueryClient();

  const q = useQuery({
    queryKey: supplyKeys.bomMaterials({ search: pesquisa || undefined }),
    queryFn: () =>
      materiaisApi.bomMaterials({
        search: pesquisa || undefined,
        limit: 500,
      }),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  const patchMutation = useMutation({
    mutationFn: ({ sku, val }: { sku: string; val: number }) =>
      materiaisApi.patchMinStock(sku, val),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: supplyKeys.all });
      setEditarSku(null);
      setNovoMin('');
    },
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-text-dark-tertiary">
        <RefreshCw size={18} className="animate-spin mr-2" />
        A carregar catálogo…
      </div>
    );
  }

  if (q.isError) {
    return (
      <EmptyState
        mascot={false}
        icon={<AlertTriangle size={32} />}
        title="Erro ao carregar catálogo de materiais"
        hint="Verifica se o backend está acessível."
        action={
          <button type="button" className="btn-dark-sm" onClick={() => q.refetch()}>
            Tentar novamente
          </button>
        }
      />
    );
  }

  const envelope = q.data;
  const items: BomMaterialItem[] = envelope?.items ?? [];

  return (
    <div className="p-6 space-y-4">
      {/* Aviso de stock não sincronizado */}
      {envelope && !envelope.stock_available && (
        <div
          className="text-xs text-yellow-400 px-3 py-2 rounded-md"
          style={{ background: 'rgba(250,204,21,0.08)', border: '1px solid rgba(250,204,21,0.2)' }}
        >
          <strong>Stock não sincronizado.</strong>{' '}
          {envelope.unavailable_reason ??
            'Corre o ETL de stock para ver os níveis reais do ERP.'}
        </div>
      )}

      {/* Pesquisa */}
      <div className="relative max-w-md">
        <Search
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-text-dark-tertiary pointer-events-none"
        />
        <input
          type="text"
          placeholder="Pesquisar material por nome ou código…"
          className="w-full pl-8 pr-3 py-2 rounded-md text-sm bg-white text-slate-900 placeholder:text-slate-400 border border-slate-300"
          value={pesquisa}
          onChange={(e) => setPesquisa(e.target.value)}
        />
      </div>

      {items.length === 0 ? (
        <EmptyState
          size="sm"
          mascot={false}
          icon={<Package size={24} />}
          title="Sem materiais encontrados"
          hint={pesquisa ? 'Tenta outro termo de pesquisa.' : 'A BOM não tem componentes-folha registados.'}
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
            <thead>
              <tr
                className="text-xs text-text-dark-tertiary uppercase"
                style={{ borderBottom: '1px solid var(--bd-1)' }}
              >
                <th className="text-left pb-2 pr-4 font-medium">Material</th>
                <th className="text-right pb-2 pr-4 font-medium tabular-nums">Stock actual</th>
                <th className="text-right pb-2 pr-4 font-medium tabular-nums">Mínimo</th>
                <th className="text-left pb-2 pr-4 font-medium">Lead time</th>
                <th className="text-right pb-2 font-medium">Editar mín.</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.id}
                  className="border-b border-bd-1/40 hover:bg-bg-1/30 transition-colors"
                  style={{ borderBottomColor: 'var(--bd-1)' }}
                >
                  <td className="py-2.5 pr-4">
                    <div className="font-medium text-text-dark-primary truncate max-w-xs">
                      {item.product_name}
                    </div>
                    <div className="font-mono text-xs text-text-dark-tertiary">
                      {item.product_code}
                    </div>
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">
                    {item.on_hand != null ? (
                      <span
                        className={
                          item.on_hand < 0
                            ? 'text-red-400'
                            : item.predicted_stockout_date
                            ? 'text-yellow-400'
                            : 'text-text-dark-primary'
                        }
                      >
                        {item.on_hand.toLocaleString('pt-PT')}
                        {item.on_hand < 0 && (
                          <span className="ml-1 text-red-400 text-xs" title="Stock negativo no ERP (acerto pendente)">⚠</span>
                        )}
                      </span>
                    ) : (
                      <span className="text-text-dark-tertiary">—</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums text-text-dark-secondary">
                    —
                  </td>
                  <td className="py-2.5 pr-4 text-text-dark-secondary text-xs">
                    {item.avg_daily_consumption != null
                      ? `${item.avg_daily_consumption.toLocaleString('pt-PT', { maximumFractionDigits: 2 })} /dia`
                      : '—'}
                  </td>
                  <td className="py-2.5 text-right">
                    {editarSku === item.product_code ? (
                      <div className="flex items-center gap-1 justify-end">
                        <input
                          type="number"
                          min={0}
                          step={1}
                          className="w-20 px-2 py-1 rounded text-xs bg-white text-slate-900 border border-slate-300"
                          value={novoMin}
                          onChange={(e) => setNovoMin(e.target.value)}
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && novoMin !== '') {
                              patchMutation.mutate({
                                sku: item.product_code,
                                val: Number(novoMin),
                              });
                            } else if (e.key === 'Escape') {
                              setEditarSku(null);
                              setNovoMin('');
                            }
                          }}
                        />
                        <button
                          type="button"
                          className="text-green-400 hover:text-green-300 p-1"
                          disabled={novoMin === '' || patchMutation.isPending}
                          onClick={() =>
                            patchMutation.mutate({
                              sku: item.product_code,
                              val: Number(novoMin),
                            })
                          }
                          title="Confirmar"
                        >
                          <Check size={14} />
                        </button>
                        <button
                          type="button"
                          className="text-text-dark-tertiary hover:text-text-dark-primary p-1"
                          onClick={() => {
                            setEditarSku(null);
                            setNovoMin('');
                          }}
                          title="Cancelar"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        className="text-text-dark-tertiary hover:text-text-dark-primary p-1"
                        onClick={() => {
                          setEditarSku(item.product_code);
                          setNovoMin('');
                        }}
                        title="Editar mínimo"
                      >
                        <Edit2 size={14} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-xs text-text-dark-tertiary pt-2">
            {items.length} material{items.length !== 1 ? 'is' : ''} · componentes-folha das BOMs
            {envelope?.stock_synced_at && (
              <> · stock sincronizado às{' '}
              {new Date(envelope.stock_synced_at).toLocaleTimeString('pt-PT', {
                hour: '2-digit',
                minute: '2-digit',
              })}</>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Tab Encomendas ─────────────────────────────────────────────────────────

function EncomendasTab() {
  const q = useQuery({
    queryKey: supplyKeys.purchaseOrders({ openOnly: true }),
    queryFn: () => materiaisApi.purchaseOrders({ open_only: true, limit: 200 }),
    staleTime: 5 * 60_000,
    retry: 1,
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center justify-center py-20 text-text-dark-tertiary">
        <RefreshCw size={18} className="animate-spin mr-2" />
        A carregar encomendas…
      </div>
    );
  }

  if (q.isError) {
    return (
      <EmptyState
        mascot={false}
        icon={<AlertTriangle size={32} />}
        title="Erro ao carregar encomendas"
        hint="Verifica se o backend está acessível."
        action={
          <button type="button" className="btn-dark-sm" onClick={() => q.refetch()}>
            Tentar novamente
          </button>
        }
      />
    );
  }

  const envelope = q.data;

  if (!envelope?.data_available) {
    return (
      <EmptyState
        mascot={false}
        icon={<ShoppingCart size={32} />}
        title="Encomendas não sincronizadas"
        hint={
          envelope?.unavailable_reason ??
          'O mirror supply.purchase_orders ainda não foi sincronizado. Corre o ETL de purchase_orders.'
        }
      />
    );
  }

  const items = envelope.items;

  if (items.length === 0) {
    return (
      <EmptyState
        mascot={false}
        icon={<ShoppingCart size={32} />}
        title="Sem encomendas abertas"
        hint="Nenhuma PO com estado OPEN ou PARTIAL."
      />
    );
  }

  const { summary } = envelope;

  return (
    <div className="p-6 space-y-4">
      {/* Resumo */}
      <div className="flex flex-wrap gap-3">
        <DarkBadge variant="neutral">
          {summary.open} abertas
        </DarkBadge>
        {summary.overdue > 0 && (
          <DarkBadge variant="danger">
            {summary.overdue} em atraso
          </DarkBadge>
        )}
        <DarkBadge variant="info">
          {summary.total_outstanding_qty.toLocaleString('pt-PT')} unid. pendentes
        </DarkBadge>
        {envelope.last_synced_at && (
          <span className="text-xs text-text-dark-tertiary self-center">
            sincronizado às{' '}
            {new Date(envelope.last_synced_at).toLocaleTimeString('pt-PT', {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        )}
      </div>

      {/* Tabela */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
          <thead>
            <tr
              className="text-xs text-text-dark-tertiary uppercase"
              style={{ borderBottom: '1px solid var(--bd-1)' }}
            >
              <th className="text-left pb-2 pr-4 font-medium">Fornecedor</th>
              <th className="text-left pb-2 pr-4 font-medium">Material</th>
              <th className="text-right pb-2 pr-4 font-medium tabular-nums">Qtd.</th>
              <th className="text-left pb-2 pr-4 font-medium">Data encomenda</th>
              <th className="text-left pb-2 pr-4 font-medium">ETA</th>
              <th className="text-left pb-2 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {items.map((po) => (
              <tr
                key={po.id}
                className="border-b border-bd-1/40 hover:bg-bg-1/30 transition-colors"
                style={{ borderBottomColor: 'var(--bd-1)' }}
              >
                <td className="py-2.5 pr-4">
                  <span className="text-text-dark-primary">{po.supplier_name}</span>
                </td>
                <td className="py-2.5 pr-4">
                  <div className="text-text-dark-primary truncate max-w-xs">
                    {po.product_name ?? po.product_code}
                  </div>
                  <div className="font-mono text-xs text-text-dark-tertiary">
                    {po.product_code}
                  </div>
                </td>
                <td className="py-2.5 pr-4 text-right tabular-nums text-text-dark-secondary">
                  {po.qty_outstanding.toLocaleString('pt-PT')}{' '}
                  <span className="text-text-dark-tertiary">{po.unit_of_measure}</span>
                </td>
                <td className="py-2.5 pr-4 text-text-dark-secondary text-xs">
                  {po.ordered_at
                    ? new Date(po.ordered_at).toLocaleDateString('pt-PT', {
                        day: 'numeric',
                        month: 'short',
                      })
                    : '—'}
                </td>
                <td className="py-2.5 pr-4 text-xs">
                  {po.eta ? (
                    <span className={po.is_overdue ? 'text-red-400' : 'text-text-dark-secondary'}>
                      {po.notes?.includes('estimada') ? '~' : ''}
                      {new Date(po.eta).toLocaleDateString('pt-PT', {
                        day: 'numeric',
                        month: 'short',
                        year: 'numeric',
                      })}
                      {po.is_overdue && (
                        <span className="ml-1 text-red-400" title="Em atraso">⚠</span>
                      )}
                      {po.days_to_eta != null && !po.is_overdue && (
                        <span className="text-text-dark-tertiary ml-1">
                          ({po.days_to_eta}d)
                        </span>
                      )}
                    </span>
                  ) : (
                    <span className="text-text-dark-tertiary">sem ETA</span>
                  )}
                </td>
                <td className="py-2.5">
                  <DarkBadge
                    variant={
                      po.status === 'OPEN'
                        ? 'info'
                        : po.status === 'PARTIAL'
                        ? 'warning'
                        : 'neutral'
                    }
                    size="sm"
                  >
                    {po.status === 'OPEN'
                      ? 'Aberta'
                      : po.status === 'PARTIAL'
                      ? 'Parcial'
                      : po.status}
                  </DarkBadge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="text-xs text-text-dark-tertiary pt-2">
          {items.length} encomenda{items.length !== 1 ? 's' : ''} abertas
        </div>
      </div>
    </div>
  );
}

// ─── Página principal ────────────────────────────────────────────────────────

export default function MateriaisPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab = (searchParams.get('tab') as TabId | null) ?? 'ruturas';

  function setTab(id: TabId) {
    setSearchParams({ tab: id }, { replace: true });
  }

  const tabs = [
    {
      id: 'ruturas',
      label: 'Ruturas',
      icon: <AlertTriangle size={13} />,
    },
    {
      id: 'stock',
      label: 'Stock',
      icon: <Package size={13} />,
    },
    {
      id: 'encomendas',
      label: 'Encomendas',
      icon: <ShoppingCart size={13} />,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Materiais"
        subtitle="Ruturas previstas, stock por armazém e encomendas a fornecedor"
        icon={<Package size={20} />}
      />

      {/* Tab bar */}
      <div
        className="px-6 sticky z-10"
        style={{
          top: 52 + 73, // TopBar + PageHeader aprox.
          background: 'var(--bg-0)',
          borderBottom: '1px solid var(--bd-1)',
        }}
      >
        <Tabs
          tabs={tabs}
          value={tab}
          onChange={(id) => setTab(id as TabId)}
        />
      </div>

      {/* Conteúdo */}
      <div className="h-[calc(100vh-52px-73px-44px)] overflow-y-auto">
        {tab === 'ruturas' && <RuturasTab />}
        {tab === 'stock' && <StockTab />}
        {tab === 'encomendas' && <EncomendasTab />}
      </div>
    </div>
  );
}
