import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Sparkles, Play, AlertTriangle, Loader2, Check, X, Lightbulb, TrendingUp } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkTable, DarkTableHead, DarkTableBody, DarkTableRow, DarkTableHeader, DarkTableCell, DarkButton, DarkPillButton, DarkBadge, DarkIconButton } from '../../components/dark';
import { improveApi } from '../../lib/api';
import { useToastContext } from '../../components/ToastProvider';

export function SuggestionsPage() {
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [filterDomain, setFilterDomain] = useState<string>('ALL');
  const [isGenerating, setIsGenerating] = useState(false);
  const toast = useToastContext();
  const queryClient = useQueryClient();

  const { data: suggestions = [], isLoading, error } = useQuery({
    queryKey: ['suggestions', 'list'],
    queryFn: () => improveApi.listSuggestions(),
  });

  const filteredSuggestions = useMemo(() => {
    return suggestions.filter((s: any) => {
      const matchesStatus = filterStatus === 'ALL' || s.status === filterStatus;
      const matchesDomain = filterDomain === 'ALL' || s.domain === filterDomain;
      return matchesStatus && matchesDomain;
    });
  }, [suggestions, filterStatus, filterDomain]);

  const stats = useMemo(() => ({
    total: suggestions.length,
    pending: suggestions.filter((s: any) => s.status === 'PENDING').length,
    approved: suggestions.filter((s: any) => s.status === 'APPROVED').length,
    rejected: suggestions.filter((s: any) => s.status === 'REJECTED').length,
    totalImpact: suggestions.filter((s: any) => s.status === 'APPROVED').reduce((sum: number, s: any) => sum + (s.impact || 0), 0),
  }), [suggestions]);

  const domains = useMemo((): string[] => {
    const d = new Set<string>(suggestions.map((s: any) => s.domain as string).filter(Boolean));
    return ['ALL', ...Array.from(d)];
  }, [suggestions]);

  const generateMutation = useMutation({
    mutationFn: () => improveApi.generateSuggestions({ limit: 10 }),
    onMutate: () => setIsGenerating(true),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['suggestions'] }); toast.success('Suggestions generated'); },
    onError: (err: any) => toast.error(err.message || 'Generation failed'),
    onSettled: () => setIsGenerating(false),
  });

  const approveMutation = useMutation({
    mutationFn: (id: string) => improveApi.approveSuggestion(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['suggestions'] }); toast.success('Suggestion approved'); },
    onError: (err: any) => toast.error(err.message || 'Error'),
  });

  const rejectMutation = useMutation({
    mutationFn: (id: string) => improveApi.rejectSuggestion(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['suggestions'] }); toast.success('Suggestion rejected'); },
    onError: (err: any) => toast.error(err.message || 'Error'),
  });

  if (error) {
    return (
      <DarkPageLayout title="AI Suggestions" icon={<Sparkles size={20} />}>
        <DarkCard className="border-danger/30 bg-danger/10">
          <div className="flex items-center gap-3 text-danger-light">
            <AlertTriangle size={20} />
            <div><p className="font-medium">Error loading suggestions</p><p className="text-sm">{(error as Error).message}</p></div>
          </div>
        </DarkCard>
      </DarkPageLayout>
    );
  }

  return (
    <DarkPageLayout
      title="AI Suggestions"
      subtitle="AI-powered improvement recommendations"
      icon={<Sparkles size={20} />}
      actions={
        <DarkButton icon={isGenerating ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />} onClick={() => generateMutation.mutate()} disabled={isGenerating}>
          {isGenerating ? 'Generating...' : 'Generate Suggestions'}
        </DarkButton>
      }
    >
      {/* Info Banner */}
      <DarkCard className="mb-6 bg-accent/10 border-accent/20">
        <div className="flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center shrink-0">
            <Sparkles size={18} className="text-accent" />
          </div>
          <div>
            <p className="text-sm font-semibold text-accent">AI-Powered Improvement Engine</p>
            <p className="text-sm text-text-secondary mt-1">
              Our AI analyzes your production data and identifies opportunities for improvement.
              Review and approve suggestions to implement them in a sandbox environment.
            </p>
          </div>
        </div>
      </DarkCard>

      <div className="flex items-center gap-4 mb-6">
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {['ALL', 'PENDING', 'APPROVED', 'REJECTED'].map((status) => (
            <DarkPillButton key={status} active={filterStatus === status} onClick={() => setFilterStatus(status)}>{status}</DarkPillButton>
          ))}
        </div>
        <div className="flex items-center gap-1 bg-bg-secondary rounded-full p-1">
          {domains.map((domain) => (
            <DarkPillButton key={domain} active={filterDomain === domain} onClick={() => setFilterDomain(domain)}>{domain}</DarkPillButton>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-5 gap-4 mb-6">
        <DarkStatCard icon={<Sparkles size={18} />} label="Total" value={stats.total} size="sm" />
        <DarkStatCard icon={<Lightbulb size={18} />} iconBg="bg-amber/20" label="Pending" value={stats.pending} size="sm" />
        <DarkStatCard icon={<Check size={18} />} iconBg="bg-success/20" label="Approved" value={stats.approved} size="sm" />
        <DarkStatCard icon={<X size={18} />} iconBg="bg-danger/20" label="Rejected" value={stats.rejected} size="sm" />
        <DarkStatCard icon={<TrendingUp size={18} />} iconBg="bg-accent/20" label="Total Impact" value={`+${stats.totalImpact.toFixed(1)}%`} size="sm" />
      </div>

      {isLoading ? (
        <DarkCard className="text-center py-12"><Loader2 className="animate-spin mx-auto text-accent" size={32} /></DarkCard>
      ) : (
        <DarkCard padding="none">
          <DarkTable>
            <DarkTableHead>
              <DarkTableRow>
                <DarkTableHeader>Suggestion</DarkTableHeader>
                <DarkTableHeader>Domain</DarkTableHeader>
                <DarkTableHeader>Impact</DarkTableHeader>
                <DarkTableHeader>Confidence</DarkTableHeader>
                <DarkTableHeader>Status</DarkTableHeader>
                <DarkTableHeader align="right">Actions</DarkTableHeader>
              </DarkTableRow>
            </DarkTableHead>
            <DarkTableBody>
              {filteredSuggestions.map((suggestion: any) => (
                <DarkTableRow key={suggestion.id}>
                  <DarkTableCell>
                    <div><p className="font-semibold text-text-white">{suggestion.title}</p>{suggestion.description && <p className="text-xs text-text-tertiary truncate max-w-md">{suggestion.description}</p>}</div>
                  </DarkTableCell>
                  <DarkTableCell><DarkBadge variant="info">{suggestion.domain || 'General'}</DarkBadge></DarkTableCell>
                  <DarkTableCell mono className={suggestion.impact > 0 ? 'text-success' : 'text-text-tertiary'}>
                    {suggestion.impact ? `+${suggestion.impact.toFixed(1)}%` : '-'}
                  </DarkTableCell>
                  <DarkTableCell>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-bg-elevated rounded-full overflow-hidden max-w-16">
                        <div className="h-full bg-accent rounded-full" style={{ width: `${(suggestion.confidence || 0) * 100}%` }} />
                      </div>
                      <span className="text-xs text-text-tertiary">{((suggestion.confidence || 0) * 100).toFixed(0)}%</span>
                    </div>
                  </DarkTableCell>
                  <DarkTableCell>
                    <DarkBadge variant={suggestion.status === 'APPROVED' ? 'success' : suggestion.status === 'REJECTED' ? 'danger' : 'warning'} dot>
                      {suggestion.status || 'PENDING'}
                    </DarkBadge>
                  </DarkTableCell>
                  <DarkTableCell align="right">
                    {suggestion.status === 'PENDING' && (
                      <div className="flex items-center justify-end gap-1">
                        <DarkButton variant="ghost" size="sm" icon={<Check size={14} />} onClick={() => approveMutation.mutate(suggestion.id)}>Approve</DarkButton>
                        <DarkIconButton icon={<X size={16} />} size="sm" variant="ghost" onClick={() => rejectMutation.mutate(suggestion.id)} />
                      </div>
                    )}
                  </DarkTableCell>
                </DarkTableRow>
              ))}
              {filteredSuggestions.length === 0 && (
                <DarkTableRow><DarkTableCell colSpan={6} className="text-center py-12"><Sparkles size={40} className="mx-auto mb-3 text-text-tertiary opacity-50" /><p className="text-text-secondary">No suggestions found</p></DarkTableCell></DarkTableRow>
              )}
            </DarkTableBody>
          </DarkTable>
        </DarkCard>
      )}
    </DarkPageLayout>
  );
}
