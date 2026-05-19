/**
 * RegrasPage — /regras · Q.17 logic-as-data (reconstrução Q.52.L)
 * ================================================================
 *
 * O operador escreve em PT-PT o que quer; o LLM (Q.17.C `nl_translator`)
 * traduz para uma regra YAML restringida pelo DSL fechado (12 eventos ×
 * 9 actions × 8 operadores × 7 axiomas). A regra nasce SEMPRE como
 * `proposed` — `requires_human_approval` é `Literal[True]`, o LLM nunca
 * faz opt-out. Um humano aprova; só então a regra entra em vigor.
 *
 * Layout NELO.html (page-regras.jsx): 4 KPIs no topo, tabs
 * Activas/Propostas/Histórico, split lista/detalhe, e o wizard de 4
 * passos para propor regras novas.
 *
 * ZERO MOCKS — todos os dados vêm da API:
 *   GET  /v1/governance/yaml-policy/rules         — lista
 *   GET  /v1/governance/yaml-policy/rules/{id}    — detalhe
 *   POST .../rules/propose                        — wizard passo 1
 *   POST .../rules/{id}/{approve,reject,suspend,rollback}  — admin
 *   GET  /v1/governance/rule-firings              — disparos (no painel)
 *
 * A matriz ACTION_WIRING vive em components/regras/ruleHelpers.ts e é
 * espelhada de src/governance/yaml_policy/dispatchers.py.
 */

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BookOpen, Sparkles, Plus, Check, History } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkButton, KPIBig, Segmented } from '../../components/dark';
import { yamlPolicyApi } from '../../lib/api';
import { RuleCard } from '../../components/regras/RuleCard';
import {
  RuleDetailPanel,
  type SafetyViolationRow,
} from '../../components/regras/RuleDetailPanel';
import { NovaRegraWizard } from '../../components/regras/NovaRegraWizard';

type TabId = 'activas' | 'propostas' | 'historico';

/** Q.17.F.3 — parse do 422 estruturado vindo do /approve. */
function parseSafetyViolations(err: Error): SafetyViolationRow[] | null {
  try {
    const parsed = JSON.parse(err.message);
    const detail = parsed?.detail ?? parsed;
    if (detail?.error === 'safety_check_failed' && Array.isArray(detail?.violations)) {
      return detail.violations as SafetyViolationRow[];
    }
  } catch {
    // não é JSON — o caller renderiza o fallback
  }
  return null;
}

export default function RegrasPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<TabId>('activas');
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [violations, setViolations] = useState<SafetyViolationRow[] | null>(null);

  const rulesQuery = useQuery({
    queryKey: ['yamlPolicy', 'rules'],
    queryFn: () => yamlPolicyApi.list({ limit: 200 }),
    refetchOnWindowFocus: false,
  });

  const detailQuery = useQuery({
    queryKey: ['yamlPolicy', 'rule', selectedRuleId],
    queryFn: () => yamlPolicyApi.get(selectedRuleId!),
    enabled: !!selectedRuleId,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['yamlPolicy'] });
  };

  const approveMutation = useMutation({
    mutationFn: (ruleId: string) => yamlPolicyApi.approve(ruleId),
    onSuccess: () => {
      setViolations(null);
      invalidate();
    },
    onError: (err: Error) => {
      const v = parseSafetyViolations(err);
      setViolations(v && v.length > 0 ? v : null);
    },
  });
  const rejectMutation = useMutation({
    mutationFn: ({ ruleId, reason }: { ruleId: string; reason: string }) =>
      yamlPolicyApi.reject(ruleId, reason),
    onSuccess: invalidate,
  });
  const suspendMutation = useMutation({
    mutationFn: (ruleId: string) => yamlPolicyApi.suspend(ruleId),
    onSuccess: invalidate,
  });
  const rollbackMutation = useMutation({
    mutationFn: ({ ruleId, reason }: { ruleId: string; reason: string }) =>
      yamlPolicyApi.rollback(ruleId, reason),
    onSuccess: invalidate,
  });

  const transitionPending =
    approveMutation.isPending ||
    rejectMutation.isPending ||
    suspendMutation.isPending ||
    rollbackMutation.isPending;

  const rules = useMemo(() => rulesQuery.data?.rules ?? [], [rulesQuery.data]);

  const counts = useMemo(() => {
    const active = rules.filter((r) => r.status === 'active').length;
    const proposed = rules.filter((r) => r.status === 'proposed').length;
    const fires = rules.reduce((acc, r) => acc + r.fire_count, 0);
    return { active, proposed, fires };
  }, [rules]);

  const filtered = useMemo(() => {
    if (tab === 'activas') {
      return rules.filter((r) => r.status === 'active' || r.status === 'approved');
    }
    if (tab === 'propostas') {
      return rules.filter((r) => r.status === 'proposed');
    }
    return rules.filter(
      (r) =>
        r.status === 'suspended' || r.status === 'rolled_back' || r.status === 'rejected',
    );
  }, [rules, tab]);

  const selectedRule = detailQuery.data?.rule ?? null;
  const selectedInTab = selectedRule
    ? filtered.some((r) => r.rule_id === selectedRule.rule_id)
    : false;

  return (
    <DarkPageLayout
      breadcrumbs={[{ label: 'Sistema' }, { label: 'Regras' }]}
      title="Regras"
      subtitle="Logic-as-data · o LLM traduz PT-PT → DSL fechado · o humano aprova sempre"
      icon={<BookOpen className="h-6 w-6" />}
      helpId="regras"
      actions={
        <DarkButton
          variant="primary"
          icon={<Plus size={14} />}
          onClick={() => setWizardOpen(true)}
        >
          Nova regra
        </DarkButton>
      }
    >
      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-5">
        <KPIBig
          label="Regras activas"
          value={counts.active}
          status="green"
          context="em vigor na fábrica"
        />
        <KPIBig
          label="Propostas a aprovar"
          value={counts.proposed}
          status="blue"
          accent="blue"
          context="à espera de revisão humana"
        />
        <KPIBig
          label="Disparos acumulados"
          value={counts.fires}
          context="soma de todas as regras"
        />
        <KPIBig
          label="Total de regras"
          value={rules.length}
          context="todos os estados"
        />
      </div>

      {/* Tabs */}
      <div className="mb-4">
        <Segmented<TabId>
          value={tab}
          onChange={setTab}
          ariaLabel="Filtrar regras por estado"
          options={[
            { value: 'activas', label: 'Activas', icon: <Check size={12} /> },
            { value: 'propostas', label: 'Propostas', icon: <Sparkles size={12} /> },
            { value: 'historico', label: 'Histórico', icon: <History size={12} /> },
          ]}
        />
      </div>

      {/* Split: lista + detalhe */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_1.3fr] gap-4">
        {/* Lista */}
        <div>
          <p className="text-[10.5px] uppercase tracking-wide font-semibold text-fg-3 mb-2">
            {filtered.length} {filtered.length === 1 ? 'regra' : 'regras'}
          </p>
          {rulesQuery.isLoading ? (
            <DarkCard className="text-center py-10">
              <p className="text-sm text-fg-3">A carregar regras…</p>
            </DarkCard>
          ) : rulesQuery.isError ? (
            <DarkCard className="text-center py-10 flex flex-col items-center gap-3">
              <BookOpen className="h-8 w-8 text-fg-3" />
              <p className="text-sm text-fg-2">Falha a carregar as regras.</p>
              <DarkButton variant="ghost" onClick={() => rulesQuery.refetch()}>
                Tentar novamente
              </DarkButton>
            </DarkCard>
          ) : filtered.length === 0 ? (
            <div
              className="rounded-lg border border-dashed border-bd-2 bg-bg-1 text-center py-10 px-6"
            >
              <BookOpen className="h-7 w-7 text-fg-3 mx-auto mb-2" />
              <p className="text-sm text-fg-2">
                {tab === 'propostas'
                  ? 'Sem propostas pendentes. Cria uma nova regra acima.'
                  : tab === 'activas'
                    ? 'Sem regras activas. Aprova uma proposta para a pôr em vigor.'
                    : 'Sem regras suspensas, revertidas ou rejeitadas.'}
              </p>
            </div>
          ) : (
            <div className="max-h-[70vh] overflow-y-auto pr-1">
              {filtered.map((r) => (
                <RuleCard
                  key={r.id}
                  rule={r}
                  active={selectedRuleId === r.rule_id}
                  onSelect={() => {
                    setSelectedRuleId(r.rule_id);
                    setViolations(null);
                  }}
                />
              ))}
            </div>
          )}
        </div>

        {/* Detalhe */}
        <div>
          {selectedRuleId && detailQuery.isLoading ? (
            <DarkCard className="text-center py-16">
              <p className="text-sm text-fg-3">A carregar detalhe…</p>
            </DarkCard>
          ) : selectedRuleId && detailQuery.isError ? (
            <DarkCard className="text-center py-16 flex flex-col items-center gap-3">
              <BookOpen className="h-10 w-10 text-fg-3" />
              <p className="text-sm text-fg-2">Falha a carregar o detalhe da regra.</p>
              <DarkButton variant="ghost" onClick={() => detailQuery.refetch()}>
                Tentar novamente
              </DarkButton>
            </DarkCard>
          ) : selectedRule && selectedInTab ? (
            <RuleDetailPanel
              rule={selectedRule}
              onApprove={() => {
                setViolations(null);
                approveMutation.mutate(selectedRule.rule_id);
              }}
              onReject={(reason) =>
                rejectMutation.mutate({ ruleId: selectedRule.rule_id, reason })
              }
              onSuspend={() => suspendMutation.mutate(selectedRule.rule_id)}
              onRollback={(reason) =>
                rollbackMutation.mutate({ ruleId: selectedRule.rule_id, reason })
              }
              pending={transitionPending}
              violations={violations}
            />
          ) : (
            <DarkCard className="text-center py-16">
              <BookOpen className="h-12 w-12 text-fg-3 mx-auto mb-3" />
              <h3 className="text-base font-medium text-fg-1 mb-1">
                Selecciona uma regra na lista
              </h3>
              <p className="text-sm text-fg-2">
                Vês aqui o YAML que o LLM produziu, os axiomas que preserva e as acções
                de aprovação.
              </p>
            </DarkCard>
          )}
        </div>
      </div>

      <NovaRegraWizard
        open={wizardOpen}
        onClose={() => setWizardOpen(false)}
        onProposed={(ruleId) => {
          setTab('propostas');
          setSelectedRuleId(ruleId);
          setViolations(null);
          invalidate();
        }}
      />
    </DarkPageLayout>
  );
}
