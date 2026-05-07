/**
 * useToolRegistry — Hook for LLM tool registry management
 * Part of TIER 4: CI/DEVOPS & FUTURE
 *
 * ZERO MOCKS: hits the real `/v1/tools` endpoint. Empty/error states
 * explicit. updateTool() PATCHes the backend and only mutates local
 * state after the server confirms. (Path was `/v1/copilot/tools` in the
 * original PR-A2; corrected here — backend mounts the router at
 * `/v1/tools` per `src/copilot/api_endpoints/tools_api.py:29`.)
 */

import { useEffect, useState, useCallback } from 'react';
import type { LLMTool } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function useToolRegistry() {
  const [tools, setTools] = useState<LLMTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchTools = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/v1/tools`);
      if (!response.ok) {
        throw new Error(
          `Tools API returned ${response.status} ${response.statusText}`
        );
      }
      const data = await response.json();
      const list: LLMTool[] = Array.isArray(data?.tools)
        ? data.tools
        : Array.isArray(data)
        ? data
        : [];
      setTools(list);
      setError(null);
    } catch (e) {
      setTools([]);
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  const updateTool = useCallback(async (toolId: string, updates: Partial<LLMTool>): Promise<boolean> => {
    const response = await fetch(`${API_BASE}/v1/tools/${toolId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!response.ok) {
      throw new Error(
        `Tool update failed: ${response.status} ${response.statusText}`
      );
    }
    setTools(prev => prev.map(tool => (tool.id === toolId ? { ...tool, ...updates } : tool)));
    return true;
  }, []);

  useEffect(() => {
    fetchTools();
  }, [fetchTools]);

  return { tools, loading, error, refresh: fetchTools, updateTool };
}

export default useToolRegistry;
