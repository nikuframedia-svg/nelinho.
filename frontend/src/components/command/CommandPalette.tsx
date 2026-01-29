/**
 * Command Palette (⌘+K / Ctrl+K)
 * 
 * Universal search and command interface.
 * Allows quick navigation, metric search, and action execution.
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  LayoutDashboard,
  Inbox,
  Factory,
  Calendar,
  GitBranch,
  Database,
  Settings,
  Lightbulb,
  Play,
  TrendingDown,
  AlertTriangle,
  Users,
  Gauge,
  Package,
  ArrowRight,
  Command,
  X,
  Zap,
} from 'lucide-react';

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface CommandItem {
  id: string;
  label: string;
  description?: string;
  icon: React.ReactNode;
  category: 'navigation' | 'action' | 'metric' | 'recent';
  shortcut?: string;
  action: () => void;
  keywords?: string[];
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
}

// ═══════════════════════════════════════════════════════════════════════════════
// FUZZY SEARCH
// ═══════════════════════════════════════════════════════════════════════════════

function fuzzyMatch(query: string, text: string): boolean {
  const queryLower = query.toLowerCase();
  const textLower = text.toLowerCase();
  
  // Check if query is substring
  if (textLower.includes(queryLower)) return true;
  
  // Fuzzy matching
  let queryIndex = 0;
  for (let i = 0; i < textLower.length && queryIndex < queryLower.length; i++) {
    if (textLower[i] === queryLower[queryIndex]) {
      queryIndex++;
    }
  }
  return queryIndex === queryLower.length;
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function CommandPalette({ isOpen, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  // Navigation helper
  const navigateTo = useCallback((path: string) => {
    navigate(path);
    onClose();
  }, [navigate, onClose]);

  // Dispatch copilot event
  const openCopilot = useCallback((promptQuery?: string) => {
    if (promptQuery) {
      window.dispatchEvent(new CustomEvent('copilot:open', { detail: { query: promptQuery } }));
    }
    onClose();
  }, [onClose]);

  // Define all commands
  const allCommands: CommandItem[] = useMemo(() => [
    // NAVIGATION
    {
      id: 'nav-dashboard',
      label: 'Dashboard',
      description: 'Visão geral da produção',
      icon: <LayoutDashboard size={18} />,
      category: 'navigation',
      shortcut: 'G D',
      action: () => navigateTo('/'),
      keywords: ['home', 'início', 'overview'],
    },
    {
      id: 'nav-inbox',
      label: 'Inbox',
      description: 'Fila de excepções',
      icon: <Inbox size={18} />,
      category: 'navigation',
      shortcut: 'G I',
      action: () => navigateTo('/inbox'),
      keywords: ['exceptions', 'alerts', 'problemas'],
    },
    {
      id: 'nav-factory',
      label: 'Factory',
      description: 'Dados mestres',
      icon: <Factory size={18} />,
      category: 'navigation',
      shortcut: 'G F',
      action: () => navigateTo('/core/products'),
      keywords: ['products', 'machines', 'produtos'],
    },
    {
      id: 'nav-planning',
      label: 'Planning',
      description: 'Scheduling e capacidade',
      icon: <Calendar size={18} />,
      category: 'navigation',
      shortcut: 'G P',
      action: () => navigateTo('/plan/scheduling'),
      keywords: ['schedule', 'capacity', 'planeamento'],
    },
    {
      id: 'nav-twin',
      label: 'Twin Sandbox',
      description: 'Simulação de cenários',
      icon: <GitBranch size={18} />,
      category: 'navigation',
      shortcut: 'G T',
      action: () => navigateTo('/twin'),
      keywords: ['simulate', 'scenarios', 'what-if'],
    },
    {
      id: 'nav-dqa',
      label: 'Data Quality Center',
      description: 'Trust index, quarentena e métricas bloqueadas',
      icon: <Database size={18} />,
      category: 'navigation',
      shortcut: 'G Q',
      action: () => navigateTo('/admin/data-quality'),
      keywords: ['quality', 'trust', 'data', 'quarantine', 'blocked'],
    },
    {
      id: 'nav-tools',
      label: 'Tool Registry',
      description: 'Gerir ferramentas do Copilot LLM',
      icon: <Zap size={18} />,
      category: 'navigation',
      shortcut: 'G T',
      action: () => navigateTo('/admin/tool-registry'),
      keywords: ['tools', 'llm', 'copilot', 'registry'],
    },
    {
      id: 'nav-settings',
      label: 'Settings',
      description: 'Configurações',
      icon: <Settings size={18} />,
      category: 'navigation',
      action: () => navigateTo('/settings'),
      keywords: ['config', 'preferences'],
    },

    // METRICS
    {
      id: 'metric-wip',
      label: 'WIP Teórico',
      description: 'Work in Progress - Ordens abertas',
      icon: <Package size={18} />,
      category: 'metric',
      action: () => navigateTo('/explain/wip_theoretical'),
      keywords: ['work', 'progress', 'orders'],
    },
    {
      id: 'metric-backlog',
      label: 'Backlog',
      description: 'Horas pendentes por fase',
      icon: <TrendingDown size={18} />,
      category: 'metric',
      action: () => navigateTo('/explain/backlog_theoretical_hours'),
      keywords: ['pending', 'hours', 'phases'],
    },
    {
      id: 'metric-bottleneck',
      label: 'Bottlenecks',
      description: 'Gargalos identificados',
      icon: <AlertTriangle size={18} />,
      category: 'metric',
      action: () => navigateTo('/inbox'),
      keywords: ['gargalo', 'constraint', 'limit'],
    },
    {
      id: 'metric-quality',
      label: 'Quality Errors',
      description: 'Erros de qualidade registados',
      icon: <AlertTriangle size={18} />,
      category: 'metric',
      action: () => navigateTo('/profit/quality'),
      keywords: ['errors', 'defeitos', 'erros'],
    },
    {
      id: 'metric-skills',
      label: 'Skills Risk',
      description: 'Risco de competências',
      icon: <Users size={18} />,
      category: 'metric',
      action: () => navigateTo('/inbox'),
      keywords: ['training', 'competencies'],
    },
    {
      id: 'metric-oee',
      label: 'OEE (Blocked)',
      description: 'Requer dados de paragens',
      icon: <Gauge size={18} />,
      category: 'metric',
      action: () => navigateTo('/profit/oee'),
      keywords: ['efficiency', 'availability', 'performance'],
    },

    // ACTIONS
    {
      id: 'action-simulate',
      label: 'Simular cenário',
      description: 'Criar novo cenário what-if',
      icon: <Play size={18} />,
      category: 'action',
      shortcut: 'N',
      action: () => navigateTo('/twin'),
      keywords: ['scenario', 'what-if', 'test'],
    },
    {
      id: 'action-explain',
      label: 'Explicar métrica',
      description: 'Abrir explicação de uma métrica',
      icon: <Lightbulb size={18} />,
      category: 'action',
      shortcut: 'E',
      action: () => navigateTo('/explain'),
      keywords: ['explain', 'understand', 'why'],
    },
    {
      id: 'action-ask-nelinho',
      label: 'Perguntar ao Nelinho',
      description: 'Abrir chat com o assistente',
      icon: <Command size={18} />,
      category: 'action',
      action: () => openCopilot(),
      keywords: ['copilot', 'ai', 'assistant', 'help'],
    },
    {
      id: 'action-bottleneck-analysis',
      label: 'Analisar bottleneck',
      description: 'Pedir análise de gargalos ao Nelinho',
      icon: <TrendingDown size={18} />,
      category: 'action',
      action: () => openCopilot('Analisa os bottlenecks actuais e sugere acções'),
      keywords: ['analyze', 'constraint'],
    },
  ], [navigateTo, openCopilot]);

  // Filter commands based on query
  const filteredCommands = useMemo(() => {
    if (!query.trim()) {
      return allCommands;
    }
    
    return allCommands.filter(cmd => {
      const searchText = [
        cmd.label,
        cmd.description || '',
        ...(cmd.keywords || []),
      ].join(' ');
      
      return fuzzyMatch(query, searchText);
    });
  }, [query, allCommands]);

  // Group commands by category
  const groupedCommands = useMemo(() => {
    const groups: Record<string, CommandItem[]> = {
      recent: [],
      action: [],
      navigation: [],
      metric: [],
    };
    
    filteredCommands.forEach(cmd => {
      if (groups[cmd.category]) {
        groups[cmd.category].push(cmd);
      }
    });
    
    return groups;
  }, [filteredCommands]);

  // Flatten for keyboard navigation
  const flatCommands = useMemo(() => {
    return [
      ...groupedCommands.recent,
      ...groupedCommands.action,
      ...groupedCommands.navigation,
      ...groupedCommands.metric,
    ];
  }, [groupedCommands]);

  // Handle keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex(i => Math.min(i + 1, flatCommands.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex(i => Math.max(i - 1, 0));
          break;
        case 'Enter':
          e.preventDefault();
          if (flatCommands[selectedIndex]) {
            flatCommands[selectedIndex].action();
          }
          break;
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, selectedIndex, flatCommands, onClose]);

  // Scroll selected item into view
  useEffect(() => {
    const selectedEl = listRef.current?.querySelector(`[data-index="${selectedIndex}"]`);
    selectedEl?.scrollIntoView({ block: 'nearest' });
  }, [selectedIndex]);

  if (!isOpen) return null;

  const categoryLabels: Record<string, string> = {
    recent: '🕐 Recentes',
    action: '⚡ Acções',
    navigation: '📍 Navegação',
    metric: '📊 Métricas',
  };

  let currentIndex = 0;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[200]"
        onClick={onClose}
      />

      {/* Palette */}
      <div className="fixed top-[20%] left-1/2 -translate-x-1/2 w-full max-w-2xl z-[201] animate-in fade-in zoom-in-95 duration-150">
        <div className="bg-bg-card border border-border-subtle rounded-2xl shadow-2xl overflow-hidden">
          {/* Search Input */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-border-subtle">
            <Search size={20} className="text-text-tertiary" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              placeholder="Pesquisar ou executar comando..."
              className="flex-1 bg-transparent text-text-white placeholder:text-text-tertiary outline-none text-base"
            />
            <kbd className="hidden sm:flex items-center gap-1 px-2 py-1 bg-bg-secondary rounded text-xs text-text-tertiary">
              <Command size={12} />K
            </kbd>
            <button
              onClick={onClose}
              className="p-1 hover:bg-bg-secondary rounded transition-colors"
            >
              <X size={18} className="text-text-tertiary" />
            </button>
          </div>

          {/* Results */}
          <div ref={listRef} className="max-h-[400px] overflow-y-auto py-2">
            {flatCommands.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <p className="text-text-tertiary">Nenhum resultado para "{query}"</p>
              </div>
            ) : (
              Object.entries(groupedCommands).map(([category, commands]) => {
                if (commands.length === 0) return null;
                
                return (
                  <div key={category} className="mb-2">
                    <div className="px-4 py-1.5 text-xs font-medium text-text-tertiary uppercase tracking-wider">
                      {categoryLabels[category]}
                    </div>
                    {commands.map((cmd) => {
                      const index = currentIndex++;
                      const isSelected = index === selectedIndex;
                      
                      return (
                        <button
                          key={cmd.id}
                          data-index={index}
                          onClick={() => cmd.action()}
                          onMouseEnter={() => setSelectedIndex(index)}
                          className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                            isSelected
                              ? 'bg-accent/20 text-accent'
                              : 'text-text-secondary hover:bg-bg-secondary'
                          }`}
                        >
                          <span className={isSelected ? 'text-accent' : 'text-text-tertiary'}>
                            {cmd.icon}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className={`font-medium truncate ${isSelected ? 'text-accent' : 'text-text-white'}`}>
                              {cmd.label}
                            </p>
                            {cmd.description && (
                              <p className="text-xs text-text-tertiary truncate">
                                {cmd.description}
                              </p>
                            )}
                          </div>
                          {cmd.shortcut && (
                            <kbd className="px-1.5 py-0.5 bg-bg-secondary rounded text-xs text-text-tertiary">
                              {cmd.shortcut}
                            </kbd>
                          )}
                          <ArrowRight size={14} className={isSelected ? 'text-accent' : 'text-text-tertiary opacity-0 group-hover:opacity-100'} />
                        </button>
                      );
                    })}
                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-2 border-t border-border-subtle bg-bg-secondary/50">
            <div className="flex items-center gap-4 text-xs text-text-tertiary">
              <span className="flex items-center gap-1">
                <kbd className="px-1 bg-bg-secondary rounded">↑↓</kbd> navegar
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1 bg-bg-secondary rounded">↵</kbd> seleccionar
              </span>
              <span className="flex items-center gap-1">
                <kbd className="px-1 bg-bg-secondary rounded">esc</kbd> fechar
              </span>
            </div>
            <span className="text-xs text-text-tertiary">
              {flatCommands.length} resultados
            </span>
          </div>
        </div>
      </div>
    </>
  );
}

export default CommandPalette;

