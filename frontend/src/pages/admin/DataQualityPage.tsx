/**
 * DataQualityPage — Palantir-Level Data Quality Dashboard
 * 
 * "The Foundation of Truth"
 */

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Shield, Database, AlertTriangle, Lock, FileSpreadsheet, BarChart3 } from 'lucide-react';
import {
  TrustHeatmap,
  QuarantineCenter,
  BlockedMetricsWall,
  IngestionTimeline,
  SchemaDriftAlert,
  CoverageAnalysis,
  ModuleErrorBoundary,
} from '@/components/palantir';
import { useTrustHeatmap, useSchemaDrift } from '@/hooks';

type Tab = 'overview' | 'heatmap' | 'quarantine' | 'blocked' | 'ingestions' | 'coverage';

export function DataQualityPage() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const { data: heatmapData } = useTrustHeatmap();
  const { drifts } = useSchemaDrift();

  const tabs = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'heatmap', label: 'Trust Heatmap', icon: Database },
    { id: 'quarantine', label: 'Quarantine', icon: Shield },
    { id: 'blocked', label: 'Métricas Bloqueadas', icon: Lock },
    { id: 'ingestions', label: 'Ingestions', icon: FileSpreadsheet },
    { id: 'coverage', label: 'Coverage', icon: AlertTriangle },
  ];

  return (
    <ModuleErrorBoundary moduleName="DataQuality">
      <div className="p-6 space-y-6">
        {/* Schema Drift Alert (floating) */}
        {drifts.length > 0 && <SchemaDriftAlert position="fixed" />}

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-text-white flex items-center gap-3">
              <Shield className="w-7 h-7 text-brand-400" />
              Data Quality Center
            </h1>
            <p className="text-text-muted mt-1">
              Monitorização e controlo da qualidade dos dados — Palantir Level
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 overflow-x-auto pb-2">
          {tabs.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as Tab)}
                className={`px-4 py-2 rounded-lg text-sm flex items-center gap-2 whitespace-nowrap
                           transition-all ${activeTab === tab.id 
                             ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/25' 
                             : 'bg-surface-700 text-text-muted hover:bg-surface-600'}`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* Quick Stats */}
              <div className="grid grid-cols-4 gap-4">
                <QuickStat 
                  icon={<Database className="w-5 h-5 text-brand-400" />}
                  label="Trust Index Médio"
                  value="72%"
                  trend="+3%"
                  trendUp
                />
                <QuickStat 
                  icon={<Shield className="w-5 h-5 text-amber-400" />}
                  label="Em Quarentena"
                  value="12"
                  trend="-5"
                  trendUp
                />
                <QuickStat 
                  icon={<Lock className="w-5 h-5 text-red-400" />}
                  label="Métricas Bloqueadas"
                  value="7"
                  trend="0"
                />
                <QuickStat 
                  icon={<FileSpreadsheet className="w-5 h-5 text-emerald-400" />}
                  label="Última Ingestion"
                  value="2h"
                  trend="OK"
                  trendUp
                />
              </div>

              {/* Trust Heatmap Preview */}
              <TrustHeatmap data={heatmapData} />

              {/* Side by Side */}
              <div className="grid grid-cols-2 gap-6">
                <BlockedMetricsWall compact maxItems={4} />
                <QuarantineCenter />
              </div>
            </div>
          )}

          {activeTab === 'heatmap' && (
            <TrustHeatmap data={heatmapData} />
          )}

          {activeTab === 'quarantine' && (
            <QuarantineCenter />
          )}

          {activeTab === 'blocked' && (
            <BlockedMetricsWall />
          )}

          {activeTab === 'ingestions' && (
            <IngestionTimeline />
          )}

          {activeTab === 'coverage' && (
            <CoverageAnalysis />
          )}
        </motion.div>
      </div>
    </ModuleErrorBoundary>
  );
}

function QuickStat({ 
  icon, 
  label, 
  value, 
  trend, 
  trendUp 
}: { 
  icon: React.ReactNode; 
  label: string; 
  value: string; 
  trend: string;
  trendUp?: boolean;
}) {
  return (
    <div className="bg-surface-800 rounded-xl p-4 border border-surface-700">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-surface-700 rounded-lg">
          {icon}
        </div>
        <div>
          <p className="text-xs text-text-muted">{label}</p>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-text-white">{value}</span>
            <span className={`text-xs ${trendUp ? 'text-emerald-400' : 'text-text-muted'}`}>
              {trend}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DataQualityPage;

