/**
 * ModuleErrorBoundary — Resilient error handling per module
 * Part of TIER 3: ENTERPRISE EXCELLENCE
 * 
 * "The Resilience Layer"
 */

import React from 'react';
import { motion } from 'framer-motion';
import { AlertOctagon, RefreshCw, Home, Bug } from 'lucide-react';

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: React.ErrorInfo | null;
}

interface ModuleErrorBoundaryProps {
  children: React.ReactNode;
  moduleName: string;
  fallback?: React.ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

// Log error to monitoring service (placeholder)
function logErrorToService(error: Error, errorInfo: React.ErrorInfo, moduleName: string) {
  // In production, this would send to Sentry, DataDog, etc.
  console.error(`[${moduleName}] Error:`, error);
  console.error('Component Stack:', errorInfo.componentStack);
}

export class ModuleErrorBoundary extends React.Component<ModuleErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { 
    hasError: false, 
    error: null, 
    errorInfo: null 
  };

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ errorInfo });
    logErrorToService(error, errorInfo, this.props.moduleName);
    this.props.onError?.(error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="min-h-[400px] flex items-center justify-center p-8"
        >
          <div className="max-w-md text-center">
            {/* Animated Error Icon */}
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', damping: 10 }}
              className="w-24 h-24 mx-auto mb-6 rounded-full bg-red-500/10 
                        flex items-center justify-center"
            >
              <AlertOctagon className="w-12 h-12 text-red-400" />
            </motion.div>

            <h2 className="text-xl font-semibold text-text-white mb-2">
              Algo correu mal no módulo {this.props.moduleName}
            </h2>
            <p className="text-text-muted mb-6">
              Ocorreu um erro inesperado. A equipa técnica foi notificada.
            </p>

            {/* Error Details (collapsible) */}
            <details className="text-left bg-surface-900 rounded-lg p-4 mb-6 border border-surface-700">
              <summary className="text-text-secondary cursor-pointer text-sm flex items-center gap-2">
                <Bug className="w-4 h-4" />
                Ver detalhes técnicos
              </summary>
              <pre className="mt-3 text-xs text-red-400 overflow-auto max-h-40 p-2 bg-surface-800 rounded">
                {this.state.error?.message}
                {this.state.errorInfo?.componentStack}
              </pre>
            </details>

            <div className="flex gap-3 justify-center">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => window.location.reload()}
                className="px-6 py-2.5 bg-brand-500 text-white rounded-lg 
                          hover:bg-brand-600 transition-colors flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Recarregar Página
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={this.handleRetry}
                className="px-6 py-2.5 bg-surface-700 text-text-secondary rounded-lg 
                          hover:bg-surface-600 transition-colors"
              >
                Tentar Novamente
              </motion.button>
            </div>

            <div className="mt-6">
              <a 
                href="/"
                className="text-sm text-text-muted hover:text-text-secondary 
                          transition-colors flex items-center gap-1 justify-center"
              >
                <Home className="w-4 h-4" />
                Voltar ao Dashboard
              </a>
            </div>
          </div>
        </motion.div>
      );
    }

    return this.props.children;
  }
}

/**
 * HOC to wrap components with error boundary
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  moduleName: string,
  options?: Omit<ModuleErrorBoundaryProps, 'children' | 'moduleName'>
) {
  return function WrappedComponent(props: P) {
    return (
      <ModuleErrorBoundary moduleName={moduleName} {...options}>
        <Component {...props} />
      </ModuleErrorBoundary>
    );
  };
}

export default ModuleErrorBoundary;

