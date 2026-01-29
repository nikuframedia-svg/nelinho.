/**
 * Payroll Page - THEORETICAL COSTS ONLY
 * ======================================
 * 
 * IMPORTANT DISCLAIMER:
 * This page displays THEORETICAL cost estimates based on:
 * - FuncionarioValorHora (median €5.54/h, with outliers flagged)
 * - HorasPrevistas_Final (standard hours, not actual worked hours)
 * 
 * This is NOT real payroll data and CANNOT be used for:
 * - Financial reporting
 * - Tax calculations
 * - Actual employee compensation
 * 
 * The data confidence is ~52% due to missing:
 * - Actual hours worked
 * - Overtime
 * - Benefits
 * - Deductions
 * - Bonuses
 */

import { useState, useMemo } from 'react';
import { 
  DollarSign, 
  AlertTriangle, 
  Info, 
  Shield,
  Ban,
  Link as LinkIcon,
  ArrowRight,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkStatCard, DarkButton } from '../../components/dark';
import { TrustBadge } from '../../components/capabilities/TrustGate';

// Trust index for theoretical cost calculations
const THEORETICAL_COST_TRUST_INDEX = 52;

// Mock theoretical cost data based on actual available data
function generateTheoreticalCostData() {
  return {
    totalEmployeesWithValorHora: 247,
    totalEmployees: 301,
    medianHourlyRate: 5.54,
    totalTheoreticalCost: 3450.67, // Estimated weekly
    costCoverage: 82.1, // % of employees with valid ValorHora
    warnings: [
      'ValorHora tem outliers (zeros e valores extremos)',
      'Não inclui horas extraordinárias',
      'Não inclui benefícios sociais',
      'Não inclui encargos patronais',
    ],
    phases: [
      { name: 'Laminagem', theoreticalCost: 890.50, employees: 29, avgHourlyRate: 5.12 },
      { name: 'Acabamento', theoreticalCost: 650.30, employees: 15, avgHourlyRate: 5.42 },
      { name: 'Pintura', theoreticalCost: 420.15, employees: 8, avgHourlyRate: 6.12 },
      { name: 'Montagem', theoreticalCost: 580.20, employees: 12, avgHourlyRate: 5.78 },
      { name: 'Outras', theoreticalCost: 909.52, employees: 183, avgHourlyRate: 5.45 },
    ],
  };
}

export function PayrollPage() {
  const [showBlockedWarning, setShowBlockedWarning] = useState(true);

  // Generate theoretical data
  const theoreticalData = useMemo(() => generateTheoreticalCostData(), []);

  return (
    <DarkPageLayout
      title="Custo Teórico de Trabalho"
      subtitle="Estimativas baseadas em ValorHora × HorasPrevistas"
      icon={<DollarSign size={20} />}
      actions={
        <div className="flex items-center gap-3">
          <TrustBadge trustIndex={THEORETICAL_COST_TRUST_INDEX} size="md" showLabel />
          <Link to="/workforce">
            <DarkButton variant="secondary" size="sm" icon={<ArrowRight size={14} />}>
              Ver Workforce Ops
            </DarkButton>
          </Link>
        </div>
      }
    >
      {/* Critical Warning Banner */}
      {showBlockedWarning && (
        <div className="mb-6 bg-gradient-to-r from-red-500/10 to-orange-500/10 border border-red-500/30 rounded-xl p-5">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="p-2 bg-red-500/20 rounded-lg">
                <Ban size={24} className="text-red-400" />
              </div>
              <div>
                <h3 className="font-bold text-red-400 text-lg mb-2">
                  ⚠️ DADOS TEÓRICOS — NÃO USAR PARA CONTABILIDADE
                </h3>
                <p className="text-slate-300 text-sm mb-3">
                  Esta página mostra <strong>estimativas de custo teórico</strong> calculadas a partir de:
                </p>
                <ul className="space-y-1 text-sm text-slate-400">
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-red-400 rounded-full" />
                    <code className="text-xs bg-slate-800 px-1.5 py-0.5 rounded">FuncionarioValorHora</code> 
                    — mediana €5.54/h (82% cobertura)
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-red-400 rounded-full" />
                    <code className="text-xs bg-slate-800 px-1.5 py-0.5 rounded">HorasPrevistas_Final</code> 
                    — horas standard (43.4% cobertura)
                  </li>
                </ul>
                <div className="mt-3 flex items-center gap-2 text-xs text-amber-400">
                  <AlertTriangle size={12} />
                  <span>Fórmula: SUM(horas_previstas × valor_hora_mediano)</span>
                </div>
              </div>
            </div>
            <button
              onClick={() => setShowBlockedWarning(false)}
              className="text-slate-400 hover:text-white p-1"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* What This Is NOT */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <DarkCard 
          title="❌ O que NÃO está incluído"
          className="border-red-500/20"
        >
          <ul className="space-y-2">
            {[
              'Horas reais trabalhadas',
              'Horas extraordinárias',
              'Subsídios (férias, Natal, alimentação)',
              'Encargos patronais (SS, seguros)',
              'Deduções (IRS, SS trabalhador)',
              'Benefícios sociais',
              'Bónus e prémios',
            ].map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-slate-400">
                <span className="w-4 h-4 rounded-full bg-red-500/20 flex items-center justify-center text-red-400 text-xs">✕</span>
                {item}
              </li>
            ))}
          </ul>
        </DarkCard>

        <DarkCard 
          title="✅ O que ESTÁ incluído"
          className="border-emerald-500/20"
        >
          <ul className="space-y-2">
            {[
              'FuncionarioValorHora (82% cobertura)',
              'HorasPrevistas_Final (43.4% cobertura)',
              'Mediana para evitar outliers',
              'Trust Index calculado',
              'Explicação de limitações',
              'Ligação à formação/simulação',
            ].map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-slate-400">
                <span className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 text-xs">✓</span>
                {item}
              </li>
            ))}
          </ul>
        </DarkCard>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkStatCard
          icon={<DollarSign size={18} />}
          label="Custo Teórico Total"
          value={`€${theoreticalData.totalTheoreticalCost.toLocaleString()}`}
          size="sm"
        />
        <DarkStatCard
          icon={<DollarSign size={18} />}
          iconBg="bg-cyan-500/20"
          label="Valor/Hora Mediano"
          value={`€${theoreticalData.medianHourlyRate.toFixed(2)}`}
          size="sm"
        />
        <DarkStatCard
          icon={<Shield size={18} />}
          iconBg="bg-amber-500/20"
          label="Cobertura ValorHora"
          value={`${theoreticalData.costCoverage.toFixed(0)}%`}
          size="sm"
        />
        <DarkStatCard
          icon={<AlertTriangle size={18} />}
          iconBg="bg-red-500/20"
          label="Trust Index"
          value={`${THEORETICAL_COST_TRUST_INDEX}%`}
          size="sm"
        />
      </div>

      {/* Cost by Phase */}
      <DarkCard 
        title="Custo Teórico por Fase"
        subtitle="Baseado em FuncionariosFasesAptos × ValorHora mediano"
      >
        <div className="space-y-3">
          {theoreticalData.phases.map((phase, i) => (
            <div
              key={i}
              className="flex items-center justify-between p-4 bg-slate-800/50 rounded-lg border border-slate-700/50"
            >
              <div className="flex items-center gap-4">
                <span className="text-sm text-slate-500 w-6">{i + 1}.</span>
                <div>
                  <p className="font-medium text-white">{phase.name}</p>
                  <p className="text-xs text-slate-400">
                    {phase.employees} funcionários • €{phase.avgHourlyRate.toFixed(2)}/h média
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-lg font-bold text-white">€{phase.theoreticalCost.toFixed(2)}</p>
                <p className="text-xs text-slate-500">custo teórico semanal</p>
              </div>
            </div>
          ))}
        </div>
      </DarkCard>

      {/* Warnings Footer */}
      <div className="mt-6 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl">
        <div className="flex items-start gap-3">
          <AlertTriangle size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-amber-400 font-medium mb-2">
              ⚠️ Limitações Críticas — Trust {THEORETICAL_COST_TRUST_INDEX}%
            </p>
            <ul className="grid grid-cols-2 gap-2">
              {theoreticalData.warnings.map((warning, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-amber-300/70">
                  <Info size={10} className="flex-shrink-0 mt-0.5" />
                  {warning}
                </li>
              ))}
            </ul>
            <div className="mt-3 pt-3 border-t border-amber-500/20">
              <Link 
                to="/explain/cost_theoretical" 
                className="inline-flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300"
              >
                <LinkIcon size={10} />
                Ver definição completa e fontes de dados →
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Call to Action */}
      <div className="mt-6 p-6 bg-gradient-to-r from-purple-500/10 to-indigo-500/10 border border-purple-500/20 rounded-xl">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-purple-500/20 rounded-xl">
              <Shield size={24} className="text-purple-400" />
            </div>
            <div>
              <h3 className="font-bold text-white mb-1">
                Usar Workforce Operations
              </h3>
              <p className="text-sm text-slate-400">
                Para análise de risco, simulação de formação e decisões operacionais legítimas
              </p>
            </div>
          </div>
          <Link to="/workforce">
            <DarkButton 
              icon={<ArrowRight size={16} />}
              className="bg-gradient-to-r from-purple-500 to-indigo-500"
            >
              Abrir Workforce Ops
            </DarkButton>
          </Link>
        </div>
      </div>
    </DarkPageLayout>
  );
}

export default PayrollPage;
