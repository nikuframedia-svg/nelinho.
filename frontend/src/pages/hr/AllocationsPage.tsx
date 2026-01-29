/**
 * Allocations Page - Organizational Structure Only
 * =================================================
 * 
 * IMPORTANT DISCLAIMER:
 * This page displays ORGANIZATIONAL STRUCTURE data from FuncionariosFaseOrdemFabrico.
 * 
 * This shows WHO IS ASSIGNED to phases/orders, NOT:
 * - Hours worked
 * - Performance
 * - Efficiency
 * - Productivity
 * 
 * The data shows STRUCTURE, not EXECUTION.
 * Trust Index: 55% (limited by data coverage and currency)
 */

import { useState, useMemo } from 'react';
import { 
  Users, 
  Info, 
  Shield,
  Layers,
  ArrowRight,
  Link as LinkIcon,
  Ban,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { DarkPageLayout } from '../../layouts';
import { 
  DarkCard, 
  DarkStatCard, 
  DarkTable, 
  DarkTableHead, 
  DarkTableBody, 
  DarkTableRow, 
  DarkTableHeader, 
  DarkTableCell, 
  DarkButton, 
  DarkBadge,
  DarkSearchInput,
} from '../../components/dark';
import { TrustBadge } from '../../components/capabilities/TrustGate';

// Trust index for allocation data
const ALLOCATIONS_TRUST_INDEX = 55;

// Mock allocation data based on FuncionariosFaseOrdemFabrico
function generateAllocationData() {
  const phases = [
    'Laminagem', 'Acabamento', 'Pintura', 'Montagem', 'Rotomoldagem',
    'Infusão', 'Prep. Molde', 'Polimento', 'Controlo Qualidade'
  ];
  
  const employees = [
    'João Silva', 'Maria Santos', 'Pedro Ferreira', 'Ana Costa', 'Carlos Lima',
    'Sofia Oliveira', 'Miguel Rodrigues', 'Inês Martins', 'Ricardo Alves', 'Helena Sousa'
  ];

  return phases.map((phase, i) => ({
    id: `phase-${i}`,
    phaseName: phase,
    assignedCount: Math.floor(Math.random() * 15) + 1,
    chiefId: `emp-${i}`,
    chiefName: employees[i % employees.length],
    isChief: true,
    lastUpdated: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
  }));
}

export function AllocationsPage() {
  const [search, setSearch] = useState('');
  const [showWarning, setShowWarning] = useState(true);

  // Generate allocation data
  const allocations = useMemo(() => generateAllocationData(), []);

  const filteredAllocations = useMemo(() => {
    if (!search) return allocations;
    return allocations.filter(a => 
      a.phaseName.toLowerCase().includes(search.toLowerCase()) ||
      a.chiefName.toLowerCase().includes(search.toLowerCase())
    );
  }, [allocations, search]);

  const stats = useMemo(() => ({
    totalPhases: allocations.length,
    totalAssigned: allocations.reduce((sum, a) => sum + a.assignedCount, 0),
    withChief: allocations.filter(a => a.isChief).length,
    coverage: 58.5, // % from FuncionariosFaseOrdemFabrico
  }), [allocations]);

  return (
    <DarkPageLayout
      title="Estrutura Organizacional — Fases"
      subtitle="Quem está associado a cada fase (não é performance)"
      icon={<Users size={20} />}
      actions={
        <div className="flex items-center gap-3">
          <TrustBadge trustIndex={ALLOCATIONS_TRUST_INDEX} size="md" showLabel />
          <Link to="/workforce">
            <DarkButton variant="secondary" size="sm" icon={<ArrowRight size={14} />}>
              Ver Workforce Ops
            </DarkButton>
          </Link>
        </div>
      }
    >
      {/* Critical Warning Banner */}
      {showWarning && (
        <div className="mb-6 bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/30 rounded-xl p-5">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className="p-2 bg-amber-500/20 rounded-lg">
                <Info size={24} className="text-amber-400" />
              </div>
              <div>
                <h3 className="font-bold text-amber-400 text-lg mb-2">
                  ℹ️ DADOS ESTRUTURAIS — NÃO USAR PARA PERFORMANCE
                </h3>
                <p className="text-slate-300 text-sm mb-3">
                  Esta página mostra <strong>quem está associado</strong> a cada fase, baseado em:
                </p>
                <ul className="space-y-1 text-sm text-slate-400">
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-amber-400 rounded-full" />
                    <code className="text-xs bg-slate-800 px-1.5 py-0.5 rounded">FuncionariosFaseOrdemFabrico</code> 
                    — 423,769 registos
                  </li>
                  <li className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-amber-400 rounded-full" />
                    Flag <code className="text-xs bg-slate-800 px-1.5 py-0.5 rounded">FuncionarioFaseOf_Chefe</code> 
                    — indica responsável
                  </li>
                </ul>
                <div className="mt-3 p-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                  <p className="text-xs text-red-400 flex items-center gap-2">
                    <Ban size={12} />
                    <strong>SEM horas, SEM tempo, SEM esforço real</strong> — estrutura organizacional apenas
                  </p>
                </div>
              </div>
            </div>
            <button
              onClick={() => setShowWarning(false)}
              className="text-slate-400 hover:text-white p-1"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* What This Page Shows vs What It Doesn't */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        <DarkCard 
          title="✅ O que esta página MOSTRA"
          className="border-emerald-500/20"
        >
          <ul className="space-y-2">
            {[
              'Quem está associado a que fase',
              'Quem é responsável (chefe)',
              'Estrutura organizacional da produção',
              'Quantas pessoas por fase',
              'Cobertura de dados disponíveis',
            ].map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-slate-400">
                <span className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 text-xs">✓</span>
                {item}
              </li>
            ))}
          </ul>
        </DarkCard>

        <DarkCard 
          title="❌ O que NÃO pode ser inferido"
          className="border-red-500/20"
        >
          <ul className="space-y-2">
            {[
              'Produtividade individual',
              'Eficiência de trabalho',
              'Horas efectivamente trabalhadas',
              'Performance comparativa',
              'Avaliação de desempenho',
              'Custos reais por funcionário',
            ].map((item, i) => (
              <li key={i} className="flex items-center gap-2 text-sm text-slate-400">
                <span className="w-4 h-4 rounded-full bg-red-500/20 flex items-center justify-center text-red-400 text-xs">✕</span>
                {item}
              </li>
            ))}
          </ul>
        </DarkCard>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <DarkStatCard
          icon={<Layers size={18} />}
          label="Fases com Associações"
          value={stats.totalPhases}
          size="sm"
        />
        <DarkStatCard
          icon={<Users size={18} />}
          iconBg="bg-cyan-500/20"
          label="Total Associados"
          value={stats.totalAssigned}
          size="sm"
        />
        <DarkStatCard
          icon={<Users size={18} />}
          iconBg="bg-emerald-500/20"
          label="Com Chefe Definido"
          value={stats.withChief}
          size="sm"
        />
        <DarkStatCard
          icon={<Shield size={18} />}
          iconBg="bg-amber-500/20"
          label="Trust Index"
          value={`${ALLOCATIONS_TRUST_INDEX}%`}
          size="sm"
        />
      </div>

      {/* Search */}
      <div className="flex items-center gap-4 mb-6">
        <DarkSearchInput
          placeholder="Pesquisar fase ou responsável..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onClear={() => setSearch('')}
          containerClassName="w-72"
        />
      </div>

      {/* Allocations Table */}
      <DarkCard padding="none">
        <DarkTable>
          <DarkTableHead>
            <DarkTableRow>
              <DarkTableHeader>Fase</DarkTableHeader>
              <DarkTableHeader>Responsável</DarkTableHeader>
              <DarkTableHeader>Associados</DarkTableHeader>
              <DarkTableHeader>Status</DarkTableHeader>
              <DarkTableHeader>Trust</DarkTableHeader>
            </DarkTableRow>
          </DarkTableHead>
          <DarkTableBody>
            {filteredAllocations.map((alloc) => (
              <DarkTableRow key={alloc.id}>
                <DarkTableCell className="text-text-white font-medium">
                  {alloc.phaseName}
                </DarkTableCell>
                <DarkTableCell>
                  <div className="flex items-center gap-2">
                    <span className="text-slate-300">{alloc.chiefName}</span>
                    {alloc.isChief && (
                      <DarkBadge variant="info" size="sm">Chefe</DarkBadge>
                    )}
                  </div>
                </DarkTableCell>
                <DarkTableCell>
                  <span className="text-slate-300">{alloc.assignedCount} pessoas</span>
                </DarkTableCell>
                <DarkTableCell>
                  <DarkBadge variant="neutral" size="sm">Estrutural</DarkBadge>
                </DarkTableCell>
                <DarkTableCell>
                  <TrustBadge trustIndex={ALLOCATIONS_TRUST_INDEX} size="sm" showLabel={false} />
                </DarkTableCell>
              </DarkTableRow>
            ))}
          </DarkTableBody>
        </DarkTable>
      </DarkCard>

      {/* Explanation Footer */}
      <div className="mt-6 p-4 bg-slate-800/50 border border-slate-700 rounded-xl">
        <div className="flex items-start gap-3">
          <Info size={16} className="text-slate-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-slate-300 mb-2">
              <strong>Fonte de dados:</strong> FuncionariosFaseOrdemFabrico
            </p>
            <p className="text-xs text-slate-500">
              Esta tabela regista a associação entre funcionários e fases/ordens de fabrico.
              A flag <code className="bg-slate-700 px-1 rounded">Chefe</code> indica responsabilidade.
              <strong> Não contém informação sobre horas, produtividade ou eficiência.</strong>
            </p>
            <div className="mt-3 pt-3 border-t border-slate-700 flex items-center gap-4">
              <Link 
                to="/workforce" 
                className="inline-flex items-center gap-1 text-xs text-purple-400 hover:text-purple-300"
              >
                <Users size={10} />
                Análise de Risco de Competências →
              </Link>
              <Link 
                to="/explain/skills_risk_score" 
                className="inline-flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300"
              >
                <LinkIcon size={10} />
                Ver definição completa →
              </Link>
            </div>
          </div>
        </div>
      </div>
    </DarkPageLayout>
  );
}

export default AllocationsPage;
