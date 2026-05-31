/**
 * AutoProposeOverlay — cards "fantasma" das Decisões PROPOSED sobrepostos ao plano.
 *
 * Cada card mostra: título, consequence truncado, delta_eur (Q.115.F defensivo),
 * commit_sha short. Botões Aprovar/Rejeitar inline. Animação fade-out ao resolver.
 *
 * Q.115.M.
 */

import { useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { Check, X, ChevronDown, ChevronUp, Zap } from 'lucide-react';
import { usePendingDecisions } from '../../hooks/usePendingDecisions';
import type { DecisionRun } from '../../lib/api';
import { apiFetch } from '../../lib/api';
import { profitKeys } from '../../lib/api/keys';
import { DarkBadge } from '../dark';

// ─── Defensive profit preview fetch ──────────────────────────────────────────

interface MarginPreview {
  delta_eur: number | null;
  confidence: string;
}

function useProfitPreview(commitSha: string | undefined) {
  return useQuery<MarginPreview | null>({
    queryKey: profitKeys.preview(commitSha ?? ''),
    queryFn: async () => {
      if (!commitSha) return null;
      try {
        const data = await apiFetch<MarginPreview>(`/v1/profit/preview?schedule_commit_id=${commitSha}`);
        return data;
      } catch {
        // 404 ou erro → esconde gracefully
        return null;
      }
    },
    enabled: Boolean(commitSha),
    staleTime: 60_000,
    retry: false,
  });
}

// ─── Card fantasma individual ─────────────────────────────────────────────────

interface GhostCardProps {
  decision: DecisionRun;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  isPending: boolean;
}

function GhostCard({ decision, onApprove, onReject, isPending }: GhostCardProps): ReactNode {
  const sb = decision.sandbox_result ?? {};
  const commitSha: string | undefined =
    (sb.commit_sha as string | undefined) ??
    (decision.action_data?.commit_sha as string | undefined);

  const { data: preview } = useProfitPreview(commitSha);

  const ifAccept = sb.if_accept as string[] | undefined;
  const why = sb.why as string | undefined;

  const shortSha = commitSha ? commitSha.slice(0, 8) : null;

  return (
    <div
      className="rounded-lg border border-dashed border-amber-500/50 bg-slate-900/60 backdrop-blur-sm"
      style={{ opacity: 0.92 }}
    >
      {/* Cabeçalho fantasma */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-dashed border-amber-500/30">
        <Zap size={11} className="text-amber-400 flex-shrink-0" />
        <span className="text-[10px] font-semibold text-amber-400 uppercase tracking-wider">
          Proposto auto
        </span>
        {shortSha && (
          <code className="text-[10px] text-slate-500 ml-auto">{shortSha}</code>
        )}
      </div>

      {/* Conteúdo */}
      <div className="px-3 py-2 space-y-1.5">
        <p className="text-xs font-medium text-slate-200 line-clamp-2">
          {decision.title ?? '(Sem título)'}
        </p>

        {why && (
          <p className="text-[11px] text-slate-400 line-clamp-2">{why}</p>
        )}

        {ifAccept && ifAccept.length > 0 && (
          <p className="text-[11px] text-emerald-400 line-clamp-1">
            + {ifAccept[0]}
            {ifAccept.length > 1 && ` +${ifAccept.length - 1}`}
          </p>
        )}

        {/* delta_eur defensivo (Q.115.F) */}
        {preview?.delta_eur != null && (
          <DarkBadge
            variant={preview.delta_eur >= 0 ? 'success' : 'danger'}
          >
            {preview.delta_eur >= 0 ? '+' : ''}
            {preview.delta_eur.toFixed(0)} €
          </DarkBadge>
        )}
      </div>

      {/* Botões Aprovar / Rejeitar */}
      <div className="flex border-t border-dashed border-amber-500/30">
        <button
          type="button"
          disabled={isPending}
          onClick={() => onReject(decision.id)}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-medium text-red-400 hover:bg-red-500/10 transition-colors rounded-bl-lg disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Rejeitar decisão"
        >
          <X size={12} />
          Rejeitar
        </button>
        <div className="w-px bg-amber-500/20" />
        <button
          type="button"
          disabled={isPending}
          onClick={() => onApprove(decision.id)}
          className="flex-1 flex items-center justify-center gap-1.5 py-2 text-[11px] font-medium text-emerald-400 hover:bg-emerald-500/10 transition-colors rounded-br-lg disabled:opacity-40 disabled:cursor-not-allowed"
          aria-label="Aprovar decisão"
        >
          <Check size={12} />
          Aprovar
        </button>
      </div>
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export function AutoProposeOverlay(): ReactNode {
  const [expanded, setExpanded] = useState(false);
  // IDs em transição (fade-out a decorrer)
  const [fadingOut, setFadingOut] = useState<Set<string>>(new Set());

  const { decisions, approveMutation, rejectMutation } = usePendingDecisions({
    filter: (d) => d.proposed_by === 'auto_propose' || (d.sandbox_result as Record<string, unknown>)?.source === 'auto_propose',
  });

  // Filtra os que ainda não estão em fade-out
  const visible = decisions.filter((d) => !fadingOut.has(d.id));
  const count = visible.length;

  const handleApprove = (id: string) => {
    setFadingOut((prev) => new Set(prev).add(id));
    approveMutation.mutate(id);
  };

  const handleReject = (id: string) => {
    setFadingOut((prev) => new Set(prev).add(id));
    rejectMutation.mutate(id);
  };

  const isPending = approveMutation.isPending || rejectMutation.isPending;

  // 0 decisões → oculto silencioso
  if (count === 0) return null;

  return (
    <div
      className="absolute top-3 right-3 z-20 flex flex-col items-end gap-1.5"
      style={{ maxWidth: 280, pointerEvents: 'auto' }}
    >
      {/* Botão toggle com badge */}
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full border border-amber-500/50 bg-slate-900/80 backdrop-blur-sm text-xs font-medium text-amber-300 hover:bg-amber-500/10 transition-colors shadow-lg"
        aria-expanded={expanded}
        aria-label={`${count} decisões propostas automaticamente`}
      >
        <Zap size={12} className="text-amber-400" />
        <span>{count} {count === 1 ? 'decisão proposta' : 'decisões propostas'}</span>
        {expanded ? (
          <ChevronUp size={12} className="text-slate-400" />
        ) : (
          <ChevronDown size={12} className="text-slate-400" />
        )}
      </button>

      {/* Lista de cards fantasma */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            key="ghost-list"
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.15 }}
            className="flex flex-col gap-2 w-full"
          >
            <AnimatePresence>
              {visible.map((decision) => (
                <motion.div
                  key={decision.id}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20, scale: 0.95 }}
                  transition={{ duration: 0.18 }}
                >
                  <GhostCard
                    decision={decision}
                    onApprove={handleApprove}
                    onReject={handleReject}
                    isPending={isPending}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
