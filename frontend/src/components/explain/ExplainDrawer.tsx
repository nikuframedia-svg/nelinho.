import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { X, Loader2, Info, Lightbulb, Ban, Shield, GitBranch, Calculator, FileText, AlertOctagon } from 'lucide-react';
import { fetchExplainedMetric, TabButton, DefinitionTab, FormulaTab, LineageTab, TrustTab, LimitationsTab, ImproveTab, type ExplainDrawerProps, type TabId } from './explainBits';

export function ExplainDrawer({ open, onClose, metricId, onSimulateClick }: ExplainDrawerProps) {
  const [activeTab, setActiveTab] = useState<TabId>('definition');
  
  const { data, isLoading, error } = useQuery({
    queryKey: ['explain', metricId],
    queryFn: () => fetchExplainedMetric(metricId),
    enabled: open && !!metricId,
    staleTime: 2 * 60 * 1000,
    retry: false,
  });

  if (!open) return null;

  const isBlocked = data?.value === null && data?.trust_index === 0;
  const isWarning = data?.trust_index !== undefined && data.trust_index > 0 && data.trust_index < 0.7;

  const tabs: Array<{ id: TabId; label: string; icon: React.ElementType }> = [
    { id: 'definition', label: 'Definição', icon: FileText },
    { id: 'formula', label: 'Fórmula', icon: Calculator },
    { id: 'lineage', label: 'Lineage', icon: GitBranch },
    { id: 'trust', label: 'Trust', icon: Shield },
    { id: 'limitations', label: 'Limites', icon: AlertOctagon },
    { id: 'improve', label: 'Melhorar', icon: Lightbulb },
  ];

  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40 transition-opacity"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-[560px] bg-white shadow-2xl z-50 overflow-hidden flex flex-col animate-slideInRight">
        {/* Header */}
        <div className={`px-6 py-4 border-b ${
          isBlocked ? 'bg-gradient-to-r from-red-50 to-orange-50 border-red-200' : 
          isWarning ? 'bg-gradient-to-r from-amber-50 to-yellow-50 border-amber-200' : 
          'bg-gradient-to-r from-blue-50 to-indigo-50 border-slate-200'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                isBlocked ? 'bg-red-500' : isWarning ? 'bg-amber-500' : 'bg-blue-500'
              }`}>
                {isBlocked ? <Ban size={20} className="text-white" /> : <Info size={20} className="text-white" />}
              </div>
              <div>
                <h2 className="font-bold text-slate-900">
                  {isBlocked ? 'Métrica Bloqueada' : 'Explicar Métrica'}
                </h2>
                <p className="text-sm text-slate-500">{metricId}</p>
              </div>
            </div>
            <button 
              onClick={onClose}
              className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center transition-colors"
            >
              <X size={20} className="text-slate-500" />
            </button>
          </div>
          
          {/* Value Display */}
          {data && (
            <div className="mt-4 flex items-baseline gap-2">
              {isBlocked ? (
                <span className="text-xl font-bold text-red-600 flex items-center gap-2">
                  <Ban size={20} />
                  INDISPONÍVEL
                </span>
              ) : (
                <>
                  <span className="text-3xl font-bold text-slate-900">
                    {data.value !== null ? data.value.toLocaleString('pt-PT', { maximumFractionDigits: 1 }) : '—'}
                  </span>
                  <span className="text-lg text-slate-500">{data.unit}</span>
                  {data.trust_index !== undefined && (
                    <span className={`ml-2 text-xs font-medium px-2 py-1 rounded ${
                      data.trust_index >= 0.7 ? 'bg-emerald-100 text-emerald-700' :
                      data.trust_index >= 0.5 ? 'bg-amber-100 text-amber-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {Math.round(data.trust_index * 100)}% trust
                    </span>
                  )}
                </>
              )}
            </div>
          )}
        </div>
        
        {/* Tabs */}
        <div className="px-4 py-3 border-b border-slate-200 bg-slate-50">
          <div className="flex items-center gap-1 overflow-x-auto">
            {tabs.map((tab) => (
              <TabButton
                key={tab.id}
                active={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
                icon={tab.icon}
                label={tab.label}
              />
            ))}
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 size={32} className="text-blue-500 animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-4">
                <Ban size={32} className="text-red-500" />
              </div>
              <p className="text-red-600 font-medium">Erro ao carregar explicação</p>
              <p className="text-sm text-slate-500 mt-2">{(error as Error).message}</p>
            </div>
          ) : data ? (
            <>
              {activeTab === 'definition' && <DefinitionTab data={data} />}
              {activeTab === 'formula' && <FormulaTab data={data} />}
              {activeTab === 'lineage' && <LineageTab data={data} />}
              {activeTab === 'trust' && <TrustTab data={data} />}
              {activeTab === 'limitations' && <LimitationsTab data={data} />}
              {activeTab === 'improve' && <ImproveTab data={data} onSimulate={onSimulateClick} />}
            </>
          ) : null}
        </div>
        
        {/* Footer */}
        {data && (
          <div className="px-6 py-3 border-t border-slate-200 bg-slate-50">
            <p className="text-xs text-slate-400">
              Calculado em: {new Date(data.computed_at).toLocaleString('pt-PT')}
            </p>
          </div>
        )}
      </div>
    </>
  );
}
