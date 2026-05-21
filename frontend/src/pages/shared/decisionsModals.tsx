// Modal de audit trail da DecisionsPage (Q.60.AE).
import { useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { decisionsApi } from '../../lib/api';
import { format } from 'date-fns';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '../../components/ui/Dialog';

export function DecisionAuditTrailModal({ decisionId, isOpen, onClose }: { decisionId: string; isOpen: boolean; onClose: () => void }) {
  const { data: auditTrail, isLoading } = useQuery({
    queryKey: ['decisions', decisionId, 'audit'],
    queryFn: () => decisionsApi.getAuditTrail(decisionId),
    enabled: isOpen,
  });

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px] bg-bg-card border-border-subtle">
        <DialogHeader>
          <DialogTitle className="text-text-white">Audit Trail</DialogTitle>
          <DialogDescription className="text-text-tertiary">
            Complete history of this decision
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={24} className="text-accent animate-spin" />
            </div>
          ) : !auditTrail || auditTrail.length === 0 ? (
            <p className="text-sm text-text-tertiary text-center py-8">No audit trail entries found</p>
          ) : (
            <div className="space-y-3">
              {auditTrail.map((entry, idx) => (
                <div key={idx} className="flex gap-3 p-3 bg-bg-elevated rounded-lg">
                  <div className="flex-shrink-0 w-2 h-2 rounded-full bg-accent mt-2" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-sm font-medium text-text-white">{entry.event}</p>
                      <p className="text-xs text-text-tertiary">{format(new Date(entry.timestamp), 'PPpp')}</p>
                    </div>
                    <p className="text-xs text-text-secondary">By: {entry.by}</p>
                    {entry.details && Object.keys(entry.details).length > 0 && (
                      <pre className="mt-2 text-xs bg-bg-base p-2 rounded border border-border-subtle overflow-x-auto text-text-secondary">
                        {JSON.stringify(entry.details, null, 2)}
                      </pre>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
