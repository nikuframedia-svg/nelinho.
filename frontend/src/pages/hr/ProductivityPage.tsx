/**
 * Productivity Page - DEPRECATED
 * ================================
 * 
 * This page has been BLOCKED because it displayed metrics that cannot be
 * computed from the available data:
 * 
 * ❌ Individual Productivity - Requires actual hours worked (not available)
 * ❌ Efficiency Metrics - Requires output vs input tracking (not available)
 * ❌ Performance Evaluation - Zero objective data, high legal risk
 * 
 * Users are redirected to the Workforce Operations dashboard which provides
 * legitimate metrics based on FuncionariosFasesAptos data:
 * 
 * ✅ Skills Risk Assessment
 * ✅ Single Point of Failure Detection
 * ✅ Cross-Training Recommendations
 * ✅ Theoretical Capacity Analysis
 */

import { useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { ArrowRight, Ban, Shield, Users } from 'lucide-react';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkButton } from '../../components/dark';

export function ProductivityPage() {
  const navigate = useNavigate();

  // Auto-redirect after 5 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      navigate('/workforce');
    }, 8000);
    return () => clearTimeout(timer);
  }, [navigate]);

  return (
    <DarkPageLayout
      title="Productivity Analysis"
      subtitle="Esta página foi descontinuada"
      icon={<Ban size={20} className="text-red-400" />}
    >
      {/* Main Warning Card */}
      <DarkCard className="border-red-500/30 bg-gradient-to-br from-red-500/10 to-red-900/10 mb-6">
        <div className="flex items-start gap-4">
          <div className="p-3 bg-red-500/20 rounded-xl">
            <Ban size={32} className="text-red-400" />
          </div>
          <div className="flex-1">
            <h2 className="text-xl font-bold text-red-400 mb-2">
              🚫 Página BLOQUEADA — Dados Insuficientes
            </h2>
            <p className="text-slate-300 mb-4">
              Esta página foi desactivada porque mostrava métricas de produtividade 
              individual que <strong>não podem ser calculadas</strong> com os dados disponíveis.
            </p>
            <div className="text-sm text-slate-400 mb-4">
              Serás redirecionado automaticamente em 8 segundos...
            </div>
          </div>
        </div>
      </DarkCard>

      {/* Why This Page is Blocked */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <DarkCard 
          title="❌ Métricas que NÃO existem"
          className="border-red-500/20"
        >
          <div className="space-y-4">
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="font-medium text-red-400 text-sm mb-1">Produtividade Individual</p>
              <p className="text-xs text-slate-400">
                Faltam: horas reais trabalhadas, output por pessoa, tempo efectivo
              </p>
            </div>
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="font-medium text-red-400 text-sm mb-1">Eficiência por Funcionário</p>
              <p className="text-xs text-slate-400">
                Faltam: tempo disponível vs usado, paragens, benchmarks
              </p>
            </div>
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <p className="font-medium text-red-400 text-sm mb-1">Avaliação de Desempenho</p>
              <p className="text-xs text-slate-400">
                Zero dados objectivos + Alto risco legal e ético
              </p>
            </div>
          </div>
        </DarkCard>

        <DarkCard 
          title="✅ Métricas que EXISTEM (alternativa)"
          className="border-emerald-500/20"
        >
          <div className="space-y-4">
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
              <p className="font-medium text-emerald-400 text-sm mb-1">Risco de Competências</p>
              <p className="text-xs text-slate-400">
                Baseado em FuncionariosFasesAptos (902 registos)
              </p>
            </div>
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
              <p className="font-medium text-emerald-400 text-sm mb-1">Single Points of Failure</p>
              <p className="text-xs text-slate-400">
                Fases com apenas 1 funcionário apto activo
              </p>
            </div>
            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg">
              <p className="font-medium text-emerald-400 text-sm mb-1">Capacidade Teórica</p>
              <p className="text-xs text-slate-400">
                Funcionários × Horas/dia (com disclaimers)
              </p>
            </div>
          </div>
        </DarkCard>
      </div>

      {/* Call to Action */}
      <DarkCard className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 border-purple-500/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-purple-500/20 rounded-xl">
              <Users size={28} className="text-purple-400" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-white mb-1">
                Ir para Workforce Operations
              </h3>
              <p className="text-sm text-slate-400">
                Dashboard de decisões com métricas legítimas e explicabilidade completa
              </p>
            </div>
          </div>
          <Link to="/workforce">
            <DarkButton 
              icon={<ArrowRight size={18} />}
              className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
            >
              Abrir Workforce Dashboard
            </DarkButton>
          </Link>
        </div>
      </DarkCard>

      {/* Trust Explanation */}
      <div className="mt-6 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl">
        <div className="flex items-start gap-3">
          <Shield size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-amber-400 font-medium mb-1">
              Filosofia Anti-Hallucination
            </p>
            <p className="text-xs text-amber-300/70">
              Este software foi desenhado para nunca mostrar métricas que não podem ser 
              calculadas de forma fiável. Cada valor tem um Trust Index, fonte de dados 
              explícita, e limitações documentadas. "Unknown ≠ 0".
            </p>
          </div>
        </div>
      </div>
    </DarkPageLayout>
  );
}

export default ProductivityPage;
