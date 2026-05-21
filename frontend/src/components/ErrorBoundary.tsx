import React, { Component } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './ui/Button';

/**
 * ErrorBoundary global — captura erros de render em qualquer subtree.
 *
 * Sprint Q.68.5.D — Adicionado:
 *   - `label` opcional: identificador do contexto (page/component) que
 *     entra nos logs e no fallback default. Substitui o anti-padrão
 *     de embrulhar tudo em `data ?? []` para mascarar erros.
 *   - `fallback` opcional: nó a renderizar em vez do default. Permite
 *     que páginas individuais usem o EmptyState/DarkCard local.
 *
 * Defaults antigos preservados: sem props extra continua a mostrar o
 * cartão branco com o botão "Recarregar Página" (compat App.tsx top-level).
 */
interface Props {
  children: ReactNode;
  /** Etiqueta do contexto — entra no `console.error` e no fallback. */
  label?: string;
  /** Nó alternativo a renderizar quando há erro. */
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    const label = this.props.label ?? 'ErrorBoundary';
    console.error(`[${label}] caught:`, error, errorInfo);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      // 1) Custom fallback tem precedência.
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // 2) Default: cartão claro com botão de reload (compat top-level).
      const label = this.props.label;
      const title = label ? `Erro em ${label}` : 'Algo correu mal';
      return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-8">
          <div className="max-w-md w-full bg-white rounded-2xl p-6 border border-slate-200 shadow-lg">
            <div className="flex items-center gap-3 mb-4">
              <AlertTriangle className="text-red-500" size={24} />
              <h2 className="text-xl font-bold text-slate-900">{title}</h2>
            </div>
            <p className="text-slate-600 mb-4">
              {this.state.error?.message || 'Ocorreu um erro inesperado.'}
            </p>
            <Button
              onClick={this.handleReload}
              className="w-full flex items-center justify-center gap-2"
            >
              <RefreshCw size={16} />
              Recarregar Página
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
