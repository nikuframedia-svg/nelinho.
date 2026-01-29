/**
 * Command Palette Component
 * 
 * A Spotlight/Alfred-like command palette for quick access to:
 * - Runbooks (with dry-run support)
 * - Navigation
 * - Quick actions
 * 
 * Triggered with Ctrl+K or Cmd+K
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { 
  Search, 
  Play, 
  Eye, 
  AlertTriangle, 
  X, 
  Command,
  FileText,
  Zap,
  BarChart3,
  Settings,
  BookOpen,
  CheckCircle,
  XCircle,
  Loader2,
} from 'lucide-react';
import { runbooksApi } from '../lib/factoryApi';
import type { Runbook, RunbookExecution } from '../lib/factoryApi';

// ============================================================================
// TYPES
// ============================================================================

interface CommandItem {
  id: string;
  type: 'runbook' | 'navigation' | 'action';
  title: string;
  description: string;
  icon: React.ReactNode;
  tags?: string[];
  onSelect?: () => void;
  runbook?: Runbook;
}

// ============================================================================
// COMPONENT
// ============================================================================

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [executionResult, setExecutionResult] = useState<RunbookExecution | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);

  // Fetch runbooks
  const { data: runbooks = [] } = useQuery<Runbook[]>({
    queryKey: ['runbooks'],
    queryFn: () => runbooksApi.getRunbooks(),
    enabled: open,
    staleTime: 60000,
  });

  // Execute runbook mutation
  const executeMutation = useMutation({
    mutationFn: ({ name, mode }: { name: string; mode: 'DRY_RUN' | 'PREVIEW' | 'EXECUTE' }) =>
      runbooksApi.execute(name, mode),
    onSuccess: (data) => {
      setExecutionResult(data);
      setExecutionError(null);
    },
    onError: (error: Error) => {
      setExecutionError(error.message);
      setExecutionResult(null);
    },
  });

  // Build command items
  const commandItems: CommandItem[] = useMemo(() => {
    const items: CommandItem[] = [];

    // Add runbooks
    runbooks.forEach((rb) => {
      items.push({
        id: `runbook-${rb.name}`,
        type: 'runbook',
        title: rb.title,
        description: rb.description,
        icon: <BookOpen className="w-4 h-4" />,
        tags: rb.tags,
        runbook: rb,
      });
    });

    // Add navigation commands
    items.push({
      id: 'nav-dashboard',
      type: 'navigation',
      title: 'Dashboard',
      description: 'Go to main dashboard',
      icon: <BarChart3 className="w-4 h-4" />,
      onSelect: () => { window.location.href = '/'; },
    });

    items.push({
      id: 'nav-sandbox',
      type: 'navigation',
      title: 'Sandbox',
      description: 'Open scenario sandbox',
      icon: <Play className="w-4 h-4" />,
      onSelect: () => { window.location.href = '/sandbox'; },
    });

    items.push({
      id: 'nav-explain',
      type: 'navigation',
      title: 'Metric Catalog',
      description: 'View metric definitions and explanations',
      icon: <FileText className="w-4 h-4" />,
      onSelect: () => { window.location.href = '/explain'; },
    });

    items.push({
      id: 'nav-settings',
      type: 'navigation',
      title: 'Settings',
      description: 'System settings',
      icon: <Settings className="w-4 h-4" />,
      onSelect: () => { window.location.href = '/admin/settings'; },
    });

    // Add quick actions
    items.push({
      id: 'action-refresh',
      type: 'action',
      title: 'Refresh Data',
      description: 'Refresh all cached data',
      icon: <Zap className="w-4 h-4" />,
      onSelect: () => { window.location.reload(); },
    });

    return items;
  }, [runbooks]);

  // Filter items by search
  const filteredItems = useMemo(() => {
    if (!search.trim()) return commandItems;
    
    const searchLower = search.toLowerCase();
    return commandItems.filter(item =>
      item.title.toLowerCase().includes(searchLower) ||
      item.description.toLowerCase().includes(searchLower) ||
      item.tags?.some(tag => tag.toLowerCase().includes(searchLower))
    );
  }, [commandItems, search]);

  // Keyboard handling
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Open with Ctrl+K or Cmd+K
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(prev => !prev);
        setSearch('');
        setSelectedIndex(0);
        setExecutionResult(null);
        setExecutionError(null);
      }

      // Close with Escape
      if (e.key === 'Escape' && open) {
        e.preventDefault();
        if (executionResult || executionError) {
          setExecutionResult(null);
          setExecutionError(null);
        } else {
          setOpen(false);
        }
      }

      // Navigate with arrow keys
      if (open && !executionResult && !executionError) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          setSelectedIndex(prev => Math.min(prev + 1, filteredItems.length - 1));
        }
        if (e.key === 'ArrowUp') {
          e.preventDefault();
          setSelectedIndex(prev => Math.max(prev - 1, 0));
        }
        if (e.key === 'Enter') {
          e.preventDefault();
          const item = filteredItems[selectedIndex];
          if (item?.onSelect) {
            item.onSelect();
            setOpen(false);
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, filteredItems, selectedIndex, executionResult, executionError]);

  // Reset selection when search changes
  useEffect(() => {
    setSelectedIndex(0);
  }, [search]);

  const executeRunbook = useCallback((name: string, mode: 'DRY_RUN' | 'PREVIEW' | 'EXECUTE') => {
    executeMutation.mutate({ name, mode });
  }, [executeMutation]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-start justify-center pt-[10vh] z-50 backdrop-blur-sm">
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-2xl w-full max-w-2xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        {/* Header with search */}
        <div className="flex items-center p-4 border-b border-gray-200 dark:border-gray-700">
          <Command className="w-5 h-5 text-gray-400 mr-2" />
          <Search className="w-5 h-5 text-gray-400 mr-3" />
          <input
            type="text"
            placeholder="Search commands, runbooks, navigation..."
            className="flex-1 bg-transparent outline-none text-lg text-gray-900 dark:text-white placeholder-gray-400"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
          />
          <kbd className="hidden sm:flex items-center gap-1 px-2 py-1 text-xs text-gray-400 bg-gray-100 dark:bg-gray-800 rounded">
            ESC
          </kbd>
          <button 
            onClick={() => setOpen(false)}
            className="ml-2 p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded"
          >
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Execution Result */}
        {(executionResult || executionError) && (
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            {executionError ? (
              <div className="flex items-start gap-3 text-red-600 dark:text-red-400">
                <XCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
                <div>
                  <div className="font-medium">Execution Failed</div>
                  <div className="text-sm mt-1">{executionError}</div>
                </div>
              </div>
            ) : executionResult && (
              <div className="flex items-start gap-3 text-green-600 dark:text-green-400">
                <CheckCircle className="w-5 h-5 mt-0.5 flex-shrink-0" />
                <div className="flex-1">
                  <div className="font-medium">
                    {executionResult.mode === 'DRY_RUN' ? 'Dry Run Complete' : 
                     executionResult.mode === 'PREVIEW' ? 'Preview Complete' : 
                     'Execution Complete'}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    Runbook: {executionResult.runbook_name} | Status: {executionResult.status}
                  </div>
                  {executionResult.results && executionResult.results.length > 0 && (
                    <div className="mt-2 text-sm">
                      <div className="font-medium text-gray-700 dark:text-gray-300">Results:</div>
                      <pre className="mt-1 p-2 bg-gray-100 dark:bg-gray-800 rounded text-xs overflow-auto max-h-32">
                        {JSON.stringify(executionResult.results, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            )}
            <button 
              className="mt-3 text-sm text-blue-600 dark:text-blue-400 hover:underline"
              onClick={() => { setExecutionResult(null); setExecutionError(null); }}
            >
              ← Back to commands
            </button>
          </div>
        )}

        {/* Command List */}
        {!executionResult && !executionError && (
          <div className="max-h-[60vh] overflow-auto">
            {filteredItems.length === 0 ? (
              <div className="p-8 text-center text-gray-500">
                No commands found matching "{search}"
              </div>
            ) : (
              <div className="p-2">
                {/* Group by type */}
                {['runbook', 'navigation', 'action'].map(type => {
                  const typeItems = filteredItems.filter(item => item.type === type);
                  if (typeItems.length === 0) return null;

                  return (
                    <div key={type} className="mb-4">
                      <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        {type === 'runbook' ? 'Runbooks' : 
                         type === 'navigation' ? 'Navigation' : 
                         'Quick Actions'}
                      </div>
                      {typeItems.map((item, _index) => {
                        const globalIndex = filteredItems.indexOf(item);
                        const isSelected = globalIndex === selectedIndex;
                        
                        return (
                          <div
                            key={item.id}
                            className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors
                              ${isSelected 
                                ? 'bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700' 
                                : 'hover:bg-gray-50 dark:hover:bg-gray-800'
                              }`}
                            onClick={() => {
                              if (item.onSelect) {
                                item.onSelect();
                                setOpen(false);
                              }
                            }}
                            onMouseEnter={() => setSelectedIndex(globalIndex)}
                          >
                            <div className="flex items-center gap-3">
                              <div className={`p-2 rounded-lg ${
                                item.type === 'runbook' 
                                  ? 'bg-purple-100 dark:bg-purple-900/50 text-purple-600 dark:text-purple-400' 
                                  : item.type === 'navigation'
                                  ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400'
                                  : 'bg-amber-100 dark:bg-amber-900/50 text-amber-600 dark:text-amber-400'
                              }`}>
                                {item.icon}
                              </div>
                              <div>
                                <div className="font-medium text-gray-900 dark:text-white">
                                  {item.title}
                                </div>
                                <div className="text-sm text-gray-500">
                                  {item.description}
                                </div>
                              </div>
                            </div>

                            {/* Runbook actions */}
                            {item.type === 'runbook' && item.runbook && (
                              <div className="flex gap-2">
                                <button
                                  className="px-3 py-1.5 bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300 rounded-md text-sm font-medium hover:bg-blue-200 dark:hover:bg-blue-800 transition-colors flex items-center gap-1"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    executeRunbook(item.runbook!.name, 'DRY_RUN');
                                  }}
                                  disabled={executeMutation.isPending}
                                >
                                  {executeMutation.isPending ? (
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                  ) : (
                                    <Eye className="w-3 h-3" />
                                  )}
                                  Dry Run
                                </button>
                                <button
                                  className="px-3 py-1.5 bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 rounded-md text-sm font-medium hover:bg-amber-200 dark:hover:bg-amber-800 transition-colors flex items-center gap-1"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    executeRunbook(item.runbook!.name, 'PREVIEW');
                                  }}
                                  disabled={executeMutation.isPending}
                                >
                                  <AlertTriangle className="w-3 h-3" />
                                  Preview
                                </button>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="p-3 border-t border-gray-200 dark:border-gray-700 text-sm text-gray-500 flex justify-between bg-gray-50 dark:bg-gray-800/50">
          <div className="flex gap-4">
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">↑</kbd>
              <kbd className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">↓</kbd>
              navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Enter</kbd>
              select
            </span>
          </div>
          <span className="flex items-center gap-1">
            <kbd className="px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">Esc</kbd>
            close
          </span>
        </div>
      </div>
    </div>
  );
}

export default CommandPalette;


