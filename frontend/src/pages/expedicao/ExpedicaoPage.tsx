/**
 * ExpedicaoPage — Expedição (shell · Q.60.S).
 *
 * As 3 tabs (Lista/CTP/Activas) foram decompostas para ./tabs/. Os
 * componentes da Lista vivem em ./tabs/listaComponents; os helpers puros
 * em ./expedicaoShared.
 */
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Truck, Target, Flag, RefreshCw, CalendarDays, PackageCheck } from 'lucide-react';
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

  const batchesQuery = useQuery({
    queryKey: ['expedicao', 'batches'],
    queryFn: () => transportApi.listBatches(),
    staleTime: 60_000,
    retry: 0,
  });
  const batches = useMemo(() => batchesQuery.data ?? [], [batchesQuery.data]);

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
          <button
            type="button"
            onClick={() => batchesQuery.refetch()}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
          >
            <RefreshCw size={13} />
            Atualizar
          </button>
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
          />
        )}
      </div>
    </div>
  );
}
