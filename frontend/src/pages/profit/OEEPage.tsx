import { Link } from 'react-router-dom';
import { 
  Gauge, 
  Info, 
  ArrowRight, 
  Clock, 
  Activity, 
  CheckCircle2,
  XCircle,
  Database,
  FileSpreadsheet,
} from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard } from '../../components/dark';
import { DarkButton } from '../../components/dark/DarkButton';

/**
 * OEE Page - BLOCKED
 * 
 * OEE (Overall Equipment Effectiveness) requires data that does not exist
 * in the current Excel data source (Folha_IA_extra.xlsx).
 * 
 * Required data for OEE:
 * - Machine downtime/uptime logs (for Availability)
 * - Actual cycle times per operation (for Performance)
 * - Good/bad unit counts per batch (for Quality)
 * 
 * What we have:
 * - Planned hours (HorasPrevistas)
 * - Error records (without direct impact on units)
 * - Phase completion status
 */
export function OEEPage() {
  return (
    <DarkPageLayout
      title="OEE Dashboard"
      subtitle="Overall Equipment Effectiveness"
      icon={<Gauge size={20} />}
    >
      {/* Blocked Notice */}
      <DarkCard className="border-red-500/30 bg-red-500/5 mb-6">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-red-500/20">
            <XCircle className="w-6 h-6 text-red-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-red-400 mb-2">
              OEE Não Disponível
            </h3>
            <p className="text-slate-300 mb-4">
              O cálculo de OEE (Overall Equipment Effectiveness) requer dados que <strong>não existem</strong> na 
              fonte de dados atual (Folha_IA_extra.xlsx). Mostrar um valor de OEE sem estes dados seria 
              enganador e violaria os princípios de transparência do sistema.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              {/* Availability */}
              <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="w-4 h-4 text-emerald-400" />
                  <span className="font-medium text-white">Availability</span>
                </div>
                <p className="text-xs text-slate-400 mb-2">
                  Tempo de funcionamento / Tempo planeado
                </p>
                <div className="flex items-center gap-2">
                  <XCircle className="w-4 h-4 text-red-400" />
                  <span className="text-xs text-red-400">
                    Requer: logs de paragens de máquina
                  </span>
                </div>
              </div>

              {/* Performance */}
              <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-4 h-4 text-purple-400" />
                  <span className="font-medium text-white">Performance</span>
                </div>
                <p className="text-xs text-slate-400 mb-2">
                  Tempo de ciclo real / Tempo de ciclo ideal
                </p>
                <div className="flex items-center gap-2">
                  <XCircle className="w-4 h-4 text-red-400" />
                  <span className="text-xs text-red-400">
                    Requer: tempos de ciclo por operação
                  </span>
                </div>
              </div>

              {/* Quality */}
              <div className="p-4 bg-slate-800/50 rounded-lg border border-slate-700/50">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="w-4 h-4 text-amber-400" />
                  <span className="font-medium text-white">Quality</span>
                </div>
                <p className="text-xs text-slate-400 mb-2">
                  Unidades boas / Total de unidades
                </p>
                <div className="flex items-center gap-2">
                  <XCircle className="w-4 h-4 text-red-400" />
                  <span className="text-xs text-red-400">
                    Requer: contagem de unidades por lote
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </DarkCard>

      {/* What We Have Instead */}
      <DarkCard className="mb-6">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-blue-500/20">
            <Database className="w-6 h-6 text-blue-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-white mb-2">
              Métricas Alternativas Disponíveis
            </h3>
            <p className="text-slate-400 mb-4">
              Com os dados disponíveis no Excel, podemos calcular métricas alternativas que fornecem 
              insights valiosos sobre a produção:
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
                <h4 className="font-medium text-emerald-400 mb-1">Backlog por Fase</h4>
                <p className="text-xs text-slate-400">
                  Horas previstas acumuladas por fase, identificando gargalos teóricos.
                </p>
              </div>
              
              <div className="p-4 bg-purple-500/10 border border-purple-500/20 rounded-lg">
                <h4 className="font-medium text-purple-400 mb-1">Bottleneck Ranking</h4>
                <p className="text-xs text-slate-400">
                  Ranking de fases por dias de backlog teórico (TOC analysis).
                </p>
              </div>
              
              <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                <h4 className="font-medium text-amber-400 mb-1">Análise de Erros</h4>
                <p className="text-xs text-slate-400">
                  Erros registados agrupados por tipo, fase ou molde.
                </p>
              </div>
              
              <div className="p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
                <h4 className="font-medium text-blue-400 mb-1">Risco de Competências</h4>
                <p className="text-xs text-slate-400">
                  Fases com poucos funcionários aptos (skills risk).
                </p>
              </div>
            </div>
          </div>
        </div>
      </DarkCard>

      {/* Data Source Info */}
      <DarkCard className="bg-slate-800/30 mb-6">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-xl bg-slate-700/50">
            <FileSpreadsheet className="w-6 h-6 text-slate-400" />
          </div>
          <div>
            <h3 className="font-semibold text-white mb-2">Fonte de Dados Atual</h3>
            <p className="text-sm text-slate-400 mb-2">
              <code className="bg-slate-700/50 px-2 py-0.5 rounded text-slate-300">Folha_IA_extra.xlsx</code>
            </p>
            <ul className="text-sm text-slate-400 space-y-1">
              <li>• <strong>OrdensFabrico</strong>: 27,911 ordens (82% trust)</li>
              <li>• <strong>FasesOrdemFabrico</strong>: 529,450 fases (40% trust)</li>
              <li>• <strong>OrdemFabricoErros</strong>: 89,836 erros (52% trust)</li>
              <li>• <strong>Funcionarios</strong>: 301 funcionários (65% trust)</li>
            </ul>
          </div>
        </div>
      </DarkCard>

      {/* Actions */}
      <div className="flex items-center gap-4">
        <Link to="/">
          <DarkButton variant="primary">
            <ArrowRight className="w-4 h-4 mr-2" />
            Ver Dashboard com Métricas Reais
          </DarkButton>
        </Link>
        <Link to="/profit/quality">
          <DarkButton variant="secondary">
            Ver Análise de Qualidade
          </DarkButton>
        </Link>
      </div>

      {/* Info Box */}
      <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl">
        <div className="flex items-start gap-3">
          <Info className="w-5 h-5 text-blue-400 mt-0.5 flex-shrink-0" />
          <div>
            <h4 className="text-sm font-medium text-blue-400 mb-1">Princípio de Transparência</h4>
            <p className="text-xs text-slate-400">
              Este sistema segue o princípio "Palantir-level" de transparência: cada valor mostrado deve ser 
              explicável, com fonte de dados clara e índice de confiança. Mostrar OEE sem os dados necessários 
              violaria este princípio e poderia levar a decisões erradas.
            </p>
          </div>
        </div>
      </div>
    </DarkPageLayout>
  );
}
