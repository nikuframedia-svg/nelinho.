/**
 * ExpedicaoPage — Expedição (shell · Q.60.S).
 *
 * As 3 tabs (Lista/CTP/Activas) foram decompostas para ./tabs/. Os
 * componentes da Lista vivem em ./tabs/listaComponents; os helpers puros
 * em ./expedicaoShared.
 */
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Truck, Target, Flag, RefreshCw, CalendarDays, PackageCheck, DownloadCloud, Loader2 } from 'lucide-react';
import { PageHeader, Tabs } from '../../components/dark';
import { transportApi } from '../../lib/api';
import { ListaTab } from './tabs/ListaTab';
import { CTPTab } from './tabs/CTPTab';
import { ActivasTab } from './tabs/ActivasTab';
import { PorDataTab } from './tabs/PorDataTab';
import { ProntosTab } from './tabs/ProntosTab';

type TabId = 'lista' | 'pordata' | 'prontos' | 'ctp' | 'activas';

export default function ExpedicaoPage() {
  // Q.135.F2.1 — /overall liga uma data via ?date=YYYY-MM-DD → abre a aba "Por data".
  const [searchParams] = useSearchParams();
  const dateParam = searchParams.get('date');
  const [tab, setTab] = useState<TabId>(dateParam ? 'pordata' : 'lista');
  const queryClient = useQueryClient();

  // Q.143.D — janela: só camiões de hoje−3d em diante (esconde o histórico).
  const fromDate = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() - 3);
    return d.toISOString().slice(0, 10);
  }, []);

  const batchesQuery = useQuery({
    queryKey: ['expedicao', 'batches', fromDate],
    queryFn: () => transportApi.listBatches({ from_date: fromDate }),
    staleTime: 60_000,
    retry: 0,
  });
  const batches = useMemo(() => batchesQuery.data ?? [], [batchesQuery.data]);

  // Q.143.B — derivar camiões reais das ordens (idempotente, preserva manual).
  const syncMutation = useMutation({
    mutationFn: () => transportApi.refreshFromOrders(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['expedicao'] }),
  });

  const tabs = [
    { id: 'lista', label: 'Expedições', icon: <Truck size={13} /> },
    { id: 'pordata', label: 'Por data', icon: <CalendarDays size={13} /> },
    { id: 'prontos', label: 'Prontos a sair', icon: <PackageCheck size={13} /> },
    { id: 'ctp', label: 'CTP · novo pedido', icon: <Target size={13} /> },
    {
      id: 'activas',
      label: 'Encomendas activas',
      icon: <Flag size={13} />,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Expedição"
        subtitle="Camiões de 50 lugares · arrasta barcos entre expedições · CTP encaixa em camiões existentes"
        helpId="expedicao"
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              title="Cria/preenche os camiões a partir das ordens reais (data de transporte). Idempotente — não desfaz movimentos manuais."
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-teal-500/15 text-teal-200 hover:bg-teal-500/25 border border-teal-400/25 text-xs font-medium transition-colors disabled:opacity-60"
            >
              {syncMutation.isPending ? <Loader2 size={13} className="animate-spin" /> : <DownloadCloud size={13} />}
              {syncMutation.isPending ? 'A sincronizar…' : 'Sincronizar do ERP'}
            </button>
            <button
              type="button"
              onClick={() => batchesQuery.refetch()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
            >
              <RefreshCw size={13} />
              Atualizar
            </button>
          </div>
        }
      />

      <div className="px-6 pt-2">
        <Tabs
          tabs={tabs}
          value={tab}
          onChange={(id) => setTab(id as TabId)}
        />
      </div>

      <div className="px-6 py-4 page-enter">
        {tab === 'lista' && (
          <ListaTab
            batches={batches}
            isLoading={batchesQuery.isLoading}
            isError={batchesQuery.isError}
            onSync={() => syncMutation.mutate()}
            isSyncing={syncMutation.isPending}
          />
        )}
        {tab === 'pordata' && (
          <PorDataTab initialDate={dateParam ?? undefined} />
        )}
        {tab === 'prontos' && <ProntosTab />}
        {tab === 'ctp' && (
          <CTPTab
            batches={batches}
            batchesLoading={batchesQuery.isLoading}
          />
        )}
        {tab === 'activas' && (
          <ActivasTab
            batches={batches}
            isLoading={batchesQuery.isLoading}
            isError={batchesQuery.isError}
            onSync={() => syncMutation.mutate()}
            isSyncing={syncMutation.isPending}
          />
        )}
      </div>
    </div>
  );
}
