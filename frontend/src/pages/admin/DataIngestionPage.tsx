/**
 * Data Ingestion Page
 * 
 * Upload Excel files and monitor data ingestion pipeline.
 * Part of the Palantir-level data management system.
 */

import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  FileSpreadsheet,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Database,
  Loader2,
  RefreshCw,
  Clock,
  BarChart3,
  Shield,
  History,
  Play,
  ChevronRight,
  AlertOctagon,
  Sparkles,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { DarkPageLayout } from '@/layouts/DarkPageLayout';
import { DarkCard } from '@/components/dark/DarkCard';
import { ingestionApi } from '@/lib/factoryApi';
import type { IngestionResult, IngestionRun, ActiveRun } from '@/lib/factoryApi';

// ============================================================================
// TYPES
// ============================================================================

type UploadState = 'idle' | 'uploading' | 'processing' | 'success' | 'error';

interface UploadProgress {
  stage: string;
  progress: number;
  message: string;
}

// ============================================================================
// COMPONENTS
// ============================================================================

function StatCard({
  icon,
  value,
  label,
  color = 'brand',
}: {
  icon: React.ReactNode;
  value: string | number;
  label: string;
  color?: 'brand' | 'emerald' | 'amber' | 'red';
}) {
  const colorClasses = {
    brand: 'text-brand-400',
    emerald: 'text-emerald-400',
    amber: 'text-amber-400',
    red: 'text-red-400',
  };

  return (
    <div className="bg-surface-800 rounded-xl p-6 text-center border border-surface-700">
      <div className={`w-8 h-8 mx-auto mb-2 ${colorClasses[color]}`}>
        {icon}
      </div>
      <p className="text-3xl font-bold text-text-white">{value}</p>
      <p className="text-text-muted text-sm">{label}</p>
    </div>
  );
}

function IngestionHistoryItem({
  ingestion,
  isActive,
  onActivate,
}: {
  ingestion: IngestionRun;
  isActive: boolean;
  onActivate: () => void;
}) {
  const statusColors = {
    succeeded: 'emerald',
    failed: 'red',
    processing: 'amber',
    received: 'blue',
  };

  const status = ingestion.status.toLowerCase();
  const color = statusColors[status as keyof typeof statusColors] || 'gray';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`p-4 rounded-xl border transition-all ${
        isActive
          ? 'bg-emerald-500/10 border-emerald-500/30'
          : 'bg-surface-900/50 border-surface-700 hover:border-surface-600'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div
            className={`w-3 h-3 rounded-full bg-${color}-500 ${
              isActive ? 'animate-pulse' : ''
            }`}
          />
          <div>
            <p className="text-text-white font-medium text-sm">
              {ingestion.source_filename || 'Unknown file'}
            </p>
            <p className="text-text-muted text-xs">
              {new Date(ingestion.created_at).toLocaleString('pt-PT')}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-text-muted text-xs">
            {ingestion.total_rows?.toLocaleString() || 0} rows
          </span>
          {isActive ? (
            <span className="text-xs px-2 py-1 rounded-full bg-emerald-500/20 text-emerald-400">
              Ativo
            </span>
          ) : (
            <button
              onClick={onActivate}
              className="text-xs px-3 py-1.5 rounded-lg bg-brand-500/20 text-brand-400 hover:bg-brand-500/30 transition-colors flex items-center gap-1"
            >
              <Play className="w-3 h-3" />
              Ativar
            </button>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// ============================================================================
// MAIN PAGE COMPONENT
// ============================================================================

export function DataIngestionPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [result, setResult] = useState<IngestionResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ingestions, setIngestions] = useState<IngestionRun[]>([]);
  const [activeRun, setActiveRun] = useState<ActiveRun | null>(null);
  const [loadingHistory, setLoadingHistory] = useState(true);

  // Load ingestion history
  const loadHistory = useCallback(async () => {
    try {
      setLoadingHistory(true);
      const [ingestionsRes, activeRes] = await Promise.all([
        ingestionApi.getIngestions(),
        ingestionApi.getActiveRun(),
      ]);
      setIngestions(ingestionsRes.ingestions || []);
      setActiveRun(activeRes);
    } catch (err) {
      console.error('Error loading history:', err);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Handle file selection
  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        setFile(selectedFile);
        setResult(null);
        setError(null);
        setUploadState('idle');
      }
    },
    []
  );

  // Handle file upload
  const handleUpload = useCallback(async () => {
    if (!file) return;

    setUploadState('uploading');
    setError(null);
    setResult(null);

    try {
      // Simulate progress stages
      setUploadState('processing');

      const data = await ingestionApi.ingestFile(file, true, 'Nelinho');

      setResult(data);
      setUploadState(data.success ? 'success' : 'error');

      // Refresh history
      await loadHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setUploadState('error');
    }
  }, [file, loadHistory]);

  // Handle activation
  const handleActivate = useCallback(
    async (ingestionId: string) => {
      try {
        await ingestionApi.activateIngestion(ingestionId, 'Nelinho');
        await loadHistory();
      } catch (err) {
        console.error('Error activating:', err);
      }
    },
    [loadHistory]
  );

  // Reset state
  const handleReset = useCallback(() => {
    setFile(null);
    setResult(null);
    setError(null);
    setUploadState('idle');
  }, []);

  return (
    <DarkPageLayout
      title="Data Ingestion"
      subtitle="Upload e processamento de dados Excel para a camada CURATED"
    >
      <div className="max-w-6xl mx-auto space-y-8">
        {/* Active Ingestion Banner */}
        {activeRun?.has_active && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-emerald-500/10 border border-emerald-500/30 rounded-2xl p-4 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
              <div>
                <p className="text-emerald-400 font-medium">
                  Ingestão Ativa
                </p>
                <p className="text-text-muted text-sm">
                  ID: {activeRun.active_ingestion_id?.substring(0, 8)}...
                  {' • '}
                  Ativado por: {activeRun.activated_by || 'sistema'}
                </p>
              </div>
            </div>
            <Sparkles className="w-5 h-5 text-emerald-400" />
          </motion.div>
        )}

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Upload Section */}
          <div className="lg:col-span-2 space-y-6">
            {/* Upload Zone */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="relative"
            >
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                disabled={uploadState === 'uploading' || uploadState === 'processing'}
              />
              <div
                className={`
                border-2 border-dashed rounded-2xl p-12 text-center transition-all
                ${
                  file
                    ? 'border-brand-500 bg-brand-500/10'
                    : 'border-surface-600 hover:border-surface-500 bg-surface-800/50'
                }
                ${uploadState !== 'idle' ? 'pointer-events-none' : ''}
              `}
              >
                <div className="flex flex-col items-center gap-4">
                  {file ? (
                    <>
                      <FileSpreadsheet className="w-16 h-16 text-brand-400" />
                      <div>
                        <p className="text-xl font-semibold text-text-white">
                          {file.name}
                        </p>
                        <p className="text-text-muted">
                          {(file.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    </>
                  ) : (
                    <>
                      <Upload className="w-16 h-16 text-text-muted" />
                      <div>
                        <p className="text-xl font-semibold text-text-white">
                          Arraste o ficheiro Excel ou clique para selecionar
                        </p>
                        <p className="text-text-muted">
                          Suporta .xlsx e .xls (Folha_IA_extra.xlsx)
                        </p>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </motion.div>

            {/* Upload Button - Always visible when file is selected */}
            {file && uploadState === 'idle' && (
              <div className="mt-6">
                <button
                  onClick={handleUpload}
                  className="w-full py-4 rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 text-white font-bold text-lg
                           hover:from-brand-600 hover:to-brand-700 transition-all shadow-lg shadow-brand-500/25
                           flex items-center justify-center gap-3 transform hover:scale-[1.02]"
                >
                  <Zap className="w-6 h-6" />
                  🚀 Iniciar Ingestão Pipeline
                </button>
                <p className="text-center text-text-muted text-sm mt-2">
                  Clique para processar {file.name}
                </p>
              </div>
            )}

            {/* Loading State */}
            {(uploadState === 'uploading' || uploadState === 'processing') && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="bg-surface-800 rounded-2xl p-8 text-center border border-surface-700"
              >
                <div className="relative w-24 h-24 mx-auto mb-6">
                  <Loader2 className="w-24 h-24 text-brand-400 animate-spin" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Database className="w-8 h-8 text-brand-400" />
                  </div>
                </div>
                <p className="text-text-white text-lg font-medium">
                  {uploadState === 'uploading'
                    ? 'A carregar ficheiro...'
                    : 'A processar dados...'}
                </p>
                <p className="text-text-muted mt-2">
                  Isto pode demorar alguns minutos para ficheiros grandes (~1.1M rows)
                </p>
                <div className="mt-6 space-y-2 text-left max-w-sm mx-auto">
                  <div className="flex items-center gap-2 text-text-muted text-sm">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    Hash SHA256 calculado
                  </div>
                  <div className="flex items-center gap-2 text-text-muted text-sm">
                    <Loader2 className="w-4 h-4 text-brand-400 animate-spin" />
                    A parsear sheets Excel...
                  </div>
                  <div className="flex items-center gap-2 text-text-muted text-sm opacity-50">
                    <div className="w-4 h-4 rounded-full border border-surface-600" />
                    Quality gates
                  </div>
                  <div className="flex items-center gap-2 text-text-muted text-sm opacity-50">
                    <div className="w-4 h-4 rounded-full border border-surface-600" />
                    Transformação para CURATED
                  </div>
                </div>
              </motion.div>
            )}

            {/* Error State */}
            {error && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-red-500/10 border border-red-500/30 rounded-2xl p-6"
              >
                <div className="flex items-start gap-4">
                  <XCircle className="w-6 h-6 text-red-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="text-red-400 font-semibold">
                      Erro na ingestão
                    </h3>
                    <p className="text-text-secondary mt-1">{error}</p>
                    <button
                      onClick={handleReset}
                      className="mt-4 px-4 py-2 rounded-lg bg-red-500/20 text-red-400 
                               hover:bg-red-500/30 transition-colors text-sm"
                    >
                      Tentar novamente
                    </button>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Success Result */}
            {result && uploadState === 'success' && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >
                {/* Status Banner */}
                <div
                  className={`
                  rounded-2xl p-6 flex items-center gap-4 border
                  ${
                    result.success
                      ? 'bg-emerald-500/10 border-emerald-500/30'
                      : 'bg-red-500/10 border-red-500/30'
                  }
                `}
                >
                  {result.success ? (
                    <CheckCircle2 className="w-10 h-10 text-emerald-400" />
                  ) : (
                    <XCircle className="w-10 h-10 text-red-400" />
                  )}
                  <div>
                    <h3
                      className={`text-xl font-semibold ${
                        result.success ? 'text-emerald-400' : 'text-red-400'
                      }`}
                    >
                      {result.success
                        ? '✨ Ingestão Concluída com Sucesso!'
                        : 'Ingestão Falhou'}
                    </h3>
                    <p className="text-text-muted">
                      Status: {result.status} | Quality Gate:{' '}
                      {result.quality_gate_status}
                    </p>
                  </div>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-4 gap-4">
                  <StatCard
                    icon={<BarChart3 className="w-full h-full" />}
                    value={result.total_rows_raw?.toLocaleString() || '0'}
                    label="Rows RAW"
                    color="brand"
                  />
                  <StatCard
                    icon={<Database className="w-full h-full" />}
                    value={result.total_rows_curated?.toLocaleString() || '0'}
                    label="Rows CURATED"
                    color="emerald"
                  />
                  <StatCard
                    icon={<Shield className="w-full h-full" />}
                    value={result.quality_gate_status || 'N/A'}
                    label="Quality Gate"
                    color={
                      result.quality_gate_status === 'passed'
                        ? 'emerald'
                        : 'amber'
                    }
                  />
                  <StatCard
                    icon={<Clock className="w-full h-full" />}
                    value={
                      result.duration_seconds
                        ? `${result.duration_seconds.toFixed(1)}s`
                        : 'N/A'
                    }
                    label="Duração"
                    color="brand"
                  />
                </div>

                {/* Warnings */}
                {result.warnings && result.warnings.length > 0 && (
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle className="w-5 h-5 text-amber-400" />
                      <h4 className="text-amber-400 font-medium">
                        Warnings ({result.warnings.length})
                      </h4>
                    </div>
                    <ul className="space-y-1 max-h-40 overflow-y-auto">
                      {result.warnings.map((w, i) => (
                        <li key={i} className="text-text-secondary text-sm">
                          • {w}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Errors */}
                {result.errors && result.errors.length > 0 && (
                  <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <XCircle className="w-5 h-5 text-red-400" />
                      <h4 className="text-red-400 font-medium">
                        Errors ({result.errors.length})
                      </h4>
                    </div>
                    <ul className="space-y-1 max-h-40 overflow-y-auto">
                      {result.errors.map((e, i) => (
                        <li key={i} className="text-red-300 text-sm">
                          • {e}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Schema Drift Alert */}
                {result.has_schema_drift && (
                  <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
                    <div className="flex items-center gap-2">
                      <AlertOctagon className="w-5 h-5 text-blue-400" />
                      <h4 className="text-blue-400 font-medium">
                        Schema Drift Detectado
                      </h4>
                    </div>
                    <p className="text-text-secondary text-sm mt-1">
                      O schema foi atualizado. Esta é a primeira ingestão ou o
                      schema mudou desde a última ingestão.
                    </p>
                  </div>
                )}

                {/* Reset Button */}
                <button
                  onClick={handleReset}
                  className="w-full py-3 rounded-xl bg-surface-700 text-text-secondary
                           hover:bg-surface-600 transition-colors flex items-center justify-center gap-2"
                >
                  <RefreshCw className="w-5 h-5" />
                  Nova Ingestão
                </button>
              </motion.div>
            )}
          </div>

          {/* History Sidebar */}
          <div className="space-y-6">
            <DarkCard title="Histórico de Ingestões" subtitle="Últimas ingestões">
              <div className="space-y-3">
                {loadingHistory ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 text-brand-400 animate-spin" />
                  </div>
                ) : ingestions.length === 0 ? (
                  <div className="text-center py-8">
                    <History className="w-12 h-12 text-text-muted mx-auto mb-2" />
                    <p className="text-text-muted">Nenhuma ingestão ainda</p>
                    <p className="text-text-secondary text-sm">
                      Faça upload de um ficheiro Excel para começar
                    </p>
                  </div>
                ) : (
                  ingestions.slice(0, 10).map((ing) => (
                    <IngestionHistoryItem
                      key={ing.id}
                      ingestion={ing}
                      isActive={ing.id === activeRun?.active_ingestion_id}
                      onActivate={() => handleActivate(ing.id)}
                    />
                  ))
                )}
              </div>
            </DarkCard>

            {/* Info Card */}
            <DarkCard title="Pipeline Info" subtitle="Como funciona">
              <div className="space-y-4 text-sm">
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-brand-500/20 text-brand-400 flex items-center justify-center text-xs font-bold">
                    1
                  </div>
                  <div>
                    <p className="text-text-white font-medium">Upload</p>
                    <p className="text-text-muted">
                      Ficheiro Excel parseado e hash calculado
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-brand-500/20 text-brand-400 flex items-center justify-center text-xs font-bold">
                    2
                  </div>
                  <div>
                    <p className="text-text-white font-medium">Quality Gates</p>
                    <p className="text-text-muted">
                      Validação de schema, integridade referencial
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-brand-500/20 text-brand-400 flex items-center justify-center text-xs font-bold">
                    3
                  </div>
                  <div>
                    <p className="text-text-white font-medium">
                      RAW → CURATED
                    </p>
                    <p className="text-text-muted">
                      Normalização e transformação dos dados
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <div className="w-6 h-6 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center text-xs font-bold">
                    ✓
                  </div>
                  <div>
                    <p className="text-text-white font-medium">Ativação</p>
                    <p className="text-text-muted">
                      Dados disponíveis para queries semânticas
                    </p>
                  </div>
                </div>
              </div>
            </DarkCard>
          </div>
        </div>
      </div>
    </DarkPageLayout>
  );
}

export default DataIngestionPage;

