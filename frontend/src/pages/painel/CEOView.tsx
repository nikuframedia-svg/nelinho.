/**
 * CEOView — vista CEO leitura-em-10s, portada de page-ceo.jsx do nelo zip.
 *
 * Substitui o CEODashboardPage legacy (broken — chama /v1/profit/dashboard
 * que devolve 500 InFailedSQLTransactionError). Esta versão usa endpoints
 * INDIVIDUAIS que funcionam (otd, fpy, activeAlerts, expeditions) +
 * graceful degradation se algum falhar.
 *
 * Layout do zip (page-ceo.jsx:1-256):
 *   1. Hero card grande — "A fábrica está NO PLANO" derivado de OTD+FPY+alertas
 *   2. 4 KPIs leitura-em-10s: Barcos em produção, OEE/FPY, OTD, Alertas activos
 *   3. Acção primária "Ver inbox de decisões" (3 sugestões pendentes)
 *
 * Sprint Q.18.ZIP.M.0 + M.1.
 */

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  AlertTriangle,
  Euro,
  Bell,
  Building,
  ArrowRight,
  RefreshCw,
  Sparkles,
  Users,
} from 'lucide-react';
import {
  PageHeader,
  KPICard,
  Panel,
  EmptyState,
  scoreToGrade,
  type KPIStatus,
} from '../../components/dark';
import { ceoDashboardApi, dqaApi } from '../../lib/api';
import { factoryApi } from '../../lib/factoryApi';

function askCopilot(query: string) {
  window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query } }));
}

function statusForOtd(pct: number | null): KPIStatus {
  if (pct === null) return 'neutral';
  if (pct >= 0.95) return 'green';
  if (pct >= 0.85) return 'yellow';
  return 'red';
}

function statusForFpy(pct: number | null): KPIStatus {
  if (pct === null) return 'neutral';
  if (pct >= 0.85) return 'green';
  if (pct >= 0.70) return 'yellow';
  return 'red';
}

function statusForCount(count: number, warnAt = 1, dangerAt = 3): KPIStatus {
  if (count === 0) return 'green';
  if (count <= warnAt) return 'yellow';
  if (count >= dangerAt) return 'red';
  return 'yellow';
}

interface HeroSummary {
  tone: 'good' | 'warn' | 'bad';
  headline: string;
  detail: string;
}

function deriveHeroSummary(
  otdPct: number | null,
  fpyPct: number | null,
  alertsCount: number,
  expeditionsAtRisk: number
): HeroSummary {
  // Lógica de "leitura-em-10s" — uma frase resumida do estado da fábrica
  const otdOk = otdPct === null || otdPct >= 0.95;
  const fpyOk = fpyPct === null || fpyPct >= 0.85;
  const alertsOk = alertsCount === 0;
  const expOk = expeditionsAtRisk === 0;

  if (otdOk && fpyOk && alertsOk && expOk) {
    return {
      tone: 'good',
      headline: 'A fábrica está no plano.',
      detail: `OTD ${otdPct !== null ? (otdPct * 100).toFixed(0) : '—'}% · FPY ${fpyPct !== null ? (fpyPct * 100).toFixed(0) : '—'}% · Sem alertas · Sem expedições em risco.`,
    };
  }

  const issues: string[] = [];
  if (alertsCount > 0) issues.push(`${alertsCount} alerta${alertsCount !== 1 ? 's' : ''}`);
  if (expeditionsAtRisk > 0)
    issues.push(`${expeditionsAtRisk} expedi${expeditionsAtRisk !== 1 ? 'ções' : 'ção'} em risco`);
  if (!otdOk && otdPct !== null)
    issues.push(`OTD ${(otdPct * 100).toFixed(0)}% (alvo 95%)`);
  if (!fpyOk && fpyPct !== null)
    issues.push(`FPY ${(fpyPct * 100).toFixed(0)}% (alvo 85%)`);

  const critical = !otdOk || expeditionsAtRisk >= 2 || alertsCount >= 3;

  return {
    tone: critical ? 'bad' : 'warn',
    headline: critical
      ? 'A fábrica precisa de atenção.'
      : 'A fábrica está perto do plano.',
    detail: issues.join(' · '),
  };
}

const HERO_TONE_STYLES: Record<HeroSummary['tone'], { bg: string; text: string; icon: string }> = {
  good: {
    bg: 'bg-success/10 border-success/30',
    text: 'text-success',
    icon: 'bg-success/15 text-success',
  },
  warn: {
    bg: 'bg-warning/10 border-warning/30',
    text: 'text-warning',
    icon: 'bg-warning/15 text-warning',
  },
  bad: {
    bg: 'bg-danger/10 border-danger/30',
    text: 'text-danger',
    icon: 'bg-danger/15 text-danger',
  },
};

export default function CEOView() {
  const navigate = useNavigate();

  // ─── Queries (cada uma independente — graceful degradation) ───
  const otdQuery = useQuery({
    queryKey: ['ceo', 'otd'],
    queryFn: () => ceoDashboardApi.otd({ window_days: 7 }),
    staleTime: 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const fpyQuery = useQuery({
    queryKey: ['ceo', 'fpy'],
    queryFn: () => ceoDashboardApi.firstPassYield({ window_days: 7 }),
    staleTime: 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const alertsQuery = useQuery({
    queryKey: ['ceo', 'alerts'],
    queryFn: () => ceoDashboardApi.activeAlerts({ limit: 5 }),
    staleTime: 30_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const expeditionsQuery = useQuery({
    queryKey: ['ceo', 'expeditions'],
    queryFn: () => ceoDashboardApi.expeditionsNextNDays({ horizon_days: 7 }),
    staleTime: 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const wipQuery = useQuery({
    queryKey: ['ceo', 'wip'],
    queryFn: () => factoryApi.getWIP(),
    staleTime: 30_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  const trustQuery = useQuery({
    queryKey: ['ceo', 'trust'],
    queryFn: () => dqaApi.trustIndex({ scope: 'factory' }),
    staleTime: 5 * 60_000,
    retry: 0,
    refetchOnWindowFocus: false,
  });

  // ─── Derivações ───
  const otdPct = (otdQuery.data as any)?.otd_pct ?? null;
  const fpyPct = (fpyQuery.data as any)?.fpy_pct ?? null;

  const alertsItems = useMemo<any[]>(() => {
    const data: any = alertsQuery.data;
    if (!data) return [];
    if (Array.isArray(data)) return data;
    if (Array.isArray(data.items)) return data.items;
    if (Array.isArray(data.alerts)) return data.alerts;
    return [];
  }, [alertsQuery.data]);

  const expeditionsAtRisk = useMemo(() => {
    const data: any = expeditionsQuery.data;
    if (!data?.items) return 0;
    return data.items.filter(
      (it: any) => it.risk === 'over_capacity' || it.risk === 'near_capacity'
    ).length;
  }, [expeditionsQuery.data]);

  const totalBoats = (wipQuery.data?.data as any)?.open_orders ?? null;

  const trustScore = (trustQuery.data as any)?.trust_index ?? null;
  const trustGrade = trustScore !== null ? scoreToGrade(trustScore) : undefined;

  const hero = deriveHeroSummary(otdPct, fpyPct, alertsItems.length, expeditionsAtRisk);
  const heroStyle = HERO_TONE_STYLES[hero.tone];

  const allLoading =
    otdQuery.isLoading &&
    fpyQuery.isLoading &&
    alertsQuery.isLoading &&
    expeditionsQuery.isLoading;
  const allErrored =
    otdQuery.isError &&
    fpyQuery.isError &&
    alertsQuery.isError &&
    expeditionsQuery.isError;

  return (
    <div>
      <PageHeader
        title="Direção"
        subtitle="LEITURA EM 10 SEGUNDOS · TURNO DE HOJE"
        icon={<Building size={20} />}
        actions={
          <>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-transparent text-text-dark-secondary hover:bg-white/5 hover:text-text-dark-primary border border-white/[0.08] text-xs font-medium transition-colors"
            >
              <RefreshCw size={13} />
              Atualizar
            </button>
            <button
              type="button"
              onClick={() => askCopilot('Resumo executivo da fábrica para o CEO em 3 frases.')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-500 text-white hover:bg-accent-400 text-xs font-medium transition-colors"
            >
              <Sparkles size={13} />
              Pedir ao Copilot
            </button>
          </>
        }
      />

      <div className="px-6 py-4 space-y-4">
        {/* ═══ HERO ═══ */}
        {allLoading ? (
          <div className="px-6 py-8 rounded-lg bg-dark-800/60 border border-white/[0.06] text-center text-text-dark-tertiary">
            A ler estado da fábrica…
          </div>
        ) : allErrored ? (
          <EmptyState
            title="Não consegui ler o estado da fábrica"
            hint="Backend indisponível ou endpoints de KPI a falhar. Tenta atualizar daqui a pouco — ou contacta o admin se persistir."
            mascot
            size="md"
          />
        ) : (
          <div
            className={`flex items-start gap-4 p-5 rounded-xl border ${heroStyle.bg}`}
          >
            <div
              className={`shrink-0 w-12 h-12 rounded-lg flex items-center justify-center ${heroStyle.icon}`}
            >
              {hero.tone === 'good' ? (
                <CheckCircle2 size={24} />
              ) : (
                <AlertTriangle size={24} />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <h2 className={`text-lg font-semibold ${heroStyle.text}`}>
                {hero.headline}
              </h2>
              <p className="text-sm text-text-dark-secondary mt-1">{hero.detail}</p>
            </div>
            {alertsItems.length > 0 ? (
              <button
                type="button"
                onClick={() => navigate('/painel')}
                className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-white/[0.06] text-text-dark-primary hover:bg-white/[0.10] text-xs font-medium transition-colors"
              >
                Ver inbox
                <ArrowRight size={13} />
              </button>
            ) : null}
          </div>
        )}

        {/* ═══ 4 KPIs leitura-em-10s ═══ */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            label="Barcos em produção"
            icon={<Users size={14} />}
            value={totalBoats === null ? '—' : totalBoats}
            unit="barcos"
            description="Ordens abertas"
            status={totalBoats === null ? 'neutral' : 'green'}
            trust={trustGrade}
            onClick={() => navigate('/producao')}
          />
          <KPICard
            label="OTD (7 dias)"
            icon={<Euro size={14} />}
            value={otdPct === null ? '—' : (otdPct * 100).toFixed(0)}
            unit="%"
            target="100"
            status={statusForOtd(otdPct)}
            description="Entregas no prazo"
            trust={trustGrade}
            onClick={() => navigate('/relatorios')}
          />
          <KPICard
            label="Qualidade 1ª passagem"
            icon={<CheckCircle2 size={14} />}
            value={fpyPct === null ? '—' : (fpyPct * 100).toFixed(0)}
            unit="%"
            target="95"
            status={statusForFpy(fpyPct)}
            description="Sem retrabalho · 7 dias"
            trust={trustGrade}
            onClick={() => navigate('/qualidade')}
          />
          <KPICard
            label="Em risco"
            icon={<AlertTriangle size={14} />}
            value={expeditionsAtRisk + alertsItems.length}
            unit="sinais"
            status={statusForCount(expeditionsAtRisk + alertsItems.length, 1, 3)}
            description={`${alertsItems.length} alerta${alertsItems.length !== 1 ? 's' : ''} · ${expeditionsAtRisk} expedi${expeditionsAtRisk !== 1 ? 'ções' : 'ção'} em risco`}
            onClick={() => navigate('/painel')}
          />
        </div>

        {/* ═══ Acção primária — sugestões pendentes ═══ */}
        <Panel
          title="Decisões pendentes"
          badge="0"
          action={
            <button
              type="button"
              onClick={() => navigate('/painel')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-accent-500/15 text-accent-400 hover:bg-accent-500/25 text-xs font-semibold transition-colors"
            >
              Ver no Painel
              <ArrowRight size={12} />
            </button>
          }
        >
          <div className="px-2 py-6 text-center text-sm text-text-dark-tertiary">
            <Bell size={20} className="mx-auto mb-2 opacity-50" />
            Quando o CPO ou o Workforce sugerirem mudanças, aparecem aqui.
            <br />
            <span className="text-text-dark-secondary">
              Por agora, sem decisões à espera.
            </span>
          </div>
        </Panel>

        {/* ═══ Status técnico ═══ */}
        {(otdQuery.isError ||
          fpyQuery.isError ||
          alertsQuery.isError ||
          expeditionsQuery.isError) && (
          <div className="px-3 py-2 rounded-md bg-warning/10 border border-warning/30 text-xs text-warning">
            Alguns endpoints estão a falhar (degradação parcial).
            {otdQuery.isError ? ' OTD indisponível.' : ''}
            {fpyQuery.isError ? ' FPY indisponível.' : ''}
            {alertsQuery.isError ? ' Alertas indisponíveis.' : ''}
            {expeditionsQuery.isError ? ' Expedições indisponíveis.' : ''}
          </div>
        )}
      </div>
    </div>
  );
}
