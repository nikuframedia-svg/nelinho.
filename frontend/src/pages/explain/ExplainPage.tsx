import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Lightbulb, AlertTriangle, Loader2 } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkBadge, DarkSearchInput, DarkButton } from '../../components/dark';
import { explainApi } from '../../lib/api';
import { ExplainDrawer } from '../../components/explain';

// PALANTIR-LEVEL COMPONENTS
import { ModuleErrorBoundary } from '../../components/palantir';

export function ExplainPage() {
  const [search, setSearch] = useState('');
  const [selectedMetricId, setSelectedMetricId] = useState<string | null>(null);

  const { data: catalog = [], isLoading, error } = useQuery({
    queryKey: ['explain', 'catalog'],
    queryFn: () => explainApi.getCatalog(),
  });

  const filteredCatalog = useMemo(() => {
    if (!search) return catalog;
    return catalog.filter((m: any) =>
      m.name?.toLowerCase().includes(search.toLowerCase()) ||
      m.id?.toLowerCase().includes(search.toLowerCase()) ||
      m.domain?.toLowerCase().includes(search.toLowerCase())
    );
  }, [catalog, search]);

  const stats = useMemo(() => {
    const domains = new Set(catalog.map((m: any) => m.domain));
    return { total: catalog.length, domains: domains.size };
  }, [catalog]);

  if (error) {
    return (
      <DarkPageLayout title="Explainability Center" icon={<Lightbulb size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading catalog</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <ModuleErrorBoundary moduleName="Explainability Center">
    <DarkPageLayout
      title="Explainability Center"
      subtitle="Understand how metrics are calculated"
      icon={<Lightbulb size={20} />}
    >
      {/* Info Banner */}
      <DarkCard className="mb-6 bg-accent/10 border-accent/20">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center shrink-0">
            <Lightbulb size={18} className="text-accent" />
          </div>
          <div>
            <p className="text-sm font-semibold text-accent">Transparent AI Decision Making</p>
            <p className="text-sm text-text-secondary mt-1">
              Every metric in ProdPlan can be explained. Click on any metric to see how it was calculated, 
              what data sources were used, and what factors influenced the result.
            </p>
          </div>
        </div>
      </DarkCard>

      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput placeholder="Search metrics..." value={search} onChange={(e) => setSearch(e.target.value)} onClear={() => setSearch('')} containerClassName="w-72" />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        <DarkStatCard icon={<Lightbulb size={18} />} label="Total Metrics" value={stats.total} size="sm" />
        <DarkStatCard icon={<Lightbulb size={18} />} iconBg="bg-blue/20" label="Domains" value={stats.domains} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Metric</DarkTableHeader>
                <DarkTableHeader>ID</DarkTableHeader>
                <DarkTableHeader>Domain</DarkTableHeader>
                <DarkTableHeader>Unit</DarkTableHeader>
                <DarkTableHeader>Description</DarkTableHeader>
                <DarkTableHeader align="right">Action</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredCatalog.map((metric: any) => (
                <DarkTableRow key={metric.id}>
                  <DarkTableCell className="text-text-white font-medium">{metric.name}</DarkTableCell>
                  <DarkTableCell mono className="text-text-tertiary">{metric.id}</DarkTableCell>
                  <DarkTableCell><DarkBadge variant="info">{metric.domain}</DarkBadge></DarkTableCell>
                  <DarkTableCell>{metric.unit || '-'}</DarkTableCell>
                  <DarkTableCell className="text-text-secondary max-w-xs truncate">{metric.description || '-'}</DarkTableCell>
                  <DarkTableCell align="right">
                    <DarkButton variant="ghost" size="sm" icon={<Lightbulb size={14} />} onClick={() => setSelectedMetricId(metric.id)}>
                      Explain
                    </DarkButton>
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredCatalog.length === 0 && (
                <DarkTableRow><DarkTableCell colSpan={6} className="text-center py-12"><Lightbulb size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No metrics found</p></DarkTableCell></DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>
        </DarkCard>
      )}

      <ExplainDrawer open={!!selectedMetricId} onClose={() => setSelectedMetricId(null)} metricId={selectedMetricId || ''} />
    </DarkPageLayout>
    </ModuleErrorBoundary>
  );
}
