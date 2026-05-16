/**
 * Dependency Graph Component
 * ===========================
 * 
 * Interactive visualization of the workforce dependency graph.
 * Shows relationships between:
 * - Phases (production stages)
 * - Employees (qualified workers)
 * - Orders (affected work)
 * 
 * Uses a force-directed layout with D3-like positioning.
 */

import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { 
  Network, 
  User, 
  Layers, 
  ZoomIn, 
  ZoomOut, 
  AlertTriangle,
  Play,
  Info,
  Shield,
} from 'lucide-react';
import type { DependencyGraph as DependencyGraphType, GraphNode, GraphEdge, RiskLevel } from './types';

interface DependencyGraphProps {
  graph: DependencyGraphType;
  onNodeClick?: (nodeId: string, nodeType: string) => void;
  onSimulate?: (phaseId: string) => void;
  highlightSpof?: boolean;
  trustIndex?: number;
  isLoading?: boolean;
}

const NODE_COLORS = {
  phase: {
    default: { fill: '#6366f1', stroke: '#818cf8' },
    critical: { fill: '#ef4444', stroke: '#f87171' },
    high: { fill: '#f97316', stroke: '#fb923c' },
    medium: { fill: '#eab308', stroke: '#facc15' },
    ok: { fill: '#22c55e', stroke: '#4ade80' },
  },
  employee: { fill: '#0ea5e9', stroke: '#38bdf8' },
  order: { fill: '#64748b', stroke: '#94a3b8' },
};

const RISK_GLOW: Record<RiskLevel, string> = {
  critical: 'drop-shadow(0 0 8px rgba(239, 68, 68, 0.6))',
  high: 'drop-shadow(0 0 6px rgba(249, 115, 22, 0.5))',
  medium: 'drop-shadow(0 0 4px rgba(234, 179, 8, 0.4))',
  low: 'drop-shadow(0 0 2px rgba(234, 179, 8, 0.2))',
  ok: 'none',
};

// Simple force layout calculation
function calculateLayout(nodes: GraphNode[], _edges: GraphEdge[], width: number, height: number) {
  const nodeMap = new Map<string, { x: number; y: number; vx: number; vy: number }>();
  
  // Initialize positions
  nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / nodes.length;
    const radius = Math.min(width, height) * 0.35;
    nodeMap.set(node.id, {
      x: width / 2 + radius * Math.cos(angle),
      y: height / 2 + radius * Math.sin(angle),
      vx: 0,
      vy: 0,
    });
  });

  // Group nodes by type for better layout
  const phases = nodes.filter(n => n.type === 'phase');
  const employees = nodes.filter(n => n.type === 'employee');
  
  // Position phases in center ring
  phases.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / phases.length - Math.PI / 2;
    const radius = Math.min(width, height) * 0.2;
    const pos = nodeMap.get(node.id)!;
    pos.x = width / 2 + radius * Math.cos(angle);
    pos.y = height / 2 + radius * Math.sin(angle);
  });

  // Position employees in outer ring
  employees.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / employees.length - Math.PI / 2;
    const radius = Math.min(width, height) * 0.4;
    const pos = nodeMap.get(node.id)!;
    pos.x = width / 2 + radius * Math.cos(angle);
    pos.y = height / 2 + radius * Math.sin(angle);
  });

  return nodeMap;
}

export function DependencyGraph({
  graph,
  onNodeClick,
  onSimulate,
  highlightSpof = true,
  trustIndex = 55,
  isLoading = false,
}: DependencyGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  const [zoom, setZoom] = useState(1);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [showFilter, setShowFilter] = useState<'all' | 'phases' | 'employees'>('all');

  // Update dimensions on mount
  useEffect(() => {
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setDimensions({ width: rect.width, height: rect.height });
    }
  }, []);

  // Filter nodes
  const filteredNodes = useMemo(() => {
    if (showFilter === 'all') return graph.nodes;
    return graph.nodes.filter(n => n.type === (showFilter === 'phases' ? 'phase' : 'employee'));
  }, [graph.nodes, showFilter]);

  // Calculate layout
  const nodePositions = useMemo(() => {
    return calculateLayout(filteredNodes, graph.edges, dimensions.width, dimensions.height);
  }, [filteredNodes, graph.edges, dimensions]);

  // Get edges that connect visible nodes
  const visibleEdges = useMemo(() => {
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    return graph.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target));
  }, [graph.edges, filteredNodes]);

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node.id === selectedNode ? null : node.id);
    onNodeClick?.(node.id, node.type);
  }, [selectedNode, onNodeClick]);

  const selectedNodeData = selectedNode 
    ? graph.nodes.find(n => n.id === selectedNode) 
    : null;

  const isSPOF = (nodeId: string) => graph.metadata.spofNodes.includes(nodeId);

  if (isLoading) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 animate-pulse">
        <div className="h-8 bg-slate-800 rounded w-1/3 mb-4" />
        <div className="h-96 bg-slate-800 rounded" />
      </div>
    );
  }

  // ZERO MOCKS: a dependency graph needs employee→phase aptitude edges. When
  // `/v1/factory/skills-risk` carries no per-phase employee identity the graph
  // has no edges — show an explicit empty state instead of a meaningless
  // scatter of phase dots.
  if (graph.edges.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="p-3 bg-slate-800 rounded-xl mb-4">
            <Network className="text-slate-500" size={28} />
          </div>
          <h3 className="font-semibold text-white mb-1">Grafo de dependências indisponível</h3>
          <p className="text-sm text-slate-400 max-w-md">
            Sem telemetria de aptidões funcionário–fase. Ingerir o Excel NELO ou
            verificar o endpoint <code className="bg-slate-800 px-1 rounded">/factory/skills-risk</code>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 rounded-lg">
            <Network className="text-indigo-400" size={20} />
          </div>
          <div>
            <h3 className="font-semibold text-white">Mapa de Dependências Críticas</h3>
            <p className="text-xs text-slate-500">
              {graph.metadata.totalPhases} fases • {graph.metadata.totalEmployees} funcionários • {graph.metadata.totalLinks} ligações
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          {/* Filter */}
          <div className="flex items-center gap-1 bg-slate-800 rounded-lg p-1">
            <button
              onClick={() => setShowFilter('all')}
              className={`px-2 py-1 text-xs rounded ${showFilter === 'all' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'}`}
            >
              Todos
            </button>
            <button
              onClick={() => setShowFilter('phases')}
              className={`px-2 py-1 text-xs rounded ${showFilter === 'phases' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'}`}
            >
              Fases
            </button>
            <button
              onClick={() => setShowFilter('employees')}
              className={`px-2 py-1 text-xs rounded ${showFilter === 'employees' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'}`}
            >
              Funcionários
            </button>
          </div>

          {/* Zoom Controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setZoom(z => Math.max(0.5, z - 0.1))}
              className="p-1.5 hover:bg-slate-800 rounded transition-colors"
            >
              <ZoomOut size={16} className="text-slate-400" />
            </button>
            <span className="text-xs text-slate-500 w-10 text-center">{(zoom * 100).toFixed(0)}%</span>
            <button
              onClick={() => setZoom(z => Math.min(2, z + 0.1))}
              className="p-1.5 hover:bg-slate-800 rounded transition-colors"
            >
              <ZoomIn size={16} className="text-slate-400" />
            </button>
          </div>

          {/* Trust Badge */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 rounded-lg">
            <Shield size={14} className={trustIndex >= 60 ? 'text-emerald-400' : 'text-amber-400'} />
            <span className="text-sm text-slate-400">Trust: <span className="text-white">{trustIndex}%</span></span>
          </div>
        </div>
      </div>

      {/* Graph Canvas */}
      <div 
        ref={containerRef}
        className="relative h-96 bg-slate-950 overflow-hidden"
        style={{ cursor: 'grab' }}
      >
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${dimensions.width} ${dimensions.height}`}
          style={{ transform: `scale(${zoom})`, transformOrigin: 'center' }}
        >
          {/* Background Pattern */}
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <circle cx="20" cy="20" r="0.5" fill="#334155" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Edges */}
          <g className="edges">
            {visibleEdges.map((edge) => {
              const sourcePos = nodePositions.get(edge.source);
              const targetPos = nodePositions.get(edge.target);
              if (!sourcePos || !targetPos) return null;

              const isHighlighted = 
                hoveredNode === edge.source || 
                hoveredNode === edge.target ||
                selectedNode === edge.source ||
                selectedNode === edge.target;

              return (
                <line
                  key={edge.id}
                  x1={sourcePos.x}
                  y1={sourcePos.y}
                  x2={targetPos.x}
                  y2={targetPos.y}
                  stroke={isHighlighted ? '#6366f1' : '#334155'}
                  strokeWidth={isHighlighted ? 2 : 1}
                  strokeOpacity={isHighlighted ? 1 : 0.5}
                  className="transition-all duration-200"
                />
              );
            })}
          </g>

          {/* Nodes */}
          <g className="nodes">
            {filteredNodes.map((node) => {
              const pos = nodePositions.get(node.id);
              if (!pos) return null;

              const isPhase = node.type === 'phase';
              const isEmployee = node.type === 'employee';
              const nodeIsSPOF = isSPOF(node.id);
              const isSelected = selectedNode === node.id;
              const isHovered = hoveredNode === node.id;

              // Get color based on node type and risk
              let fill = NODE_COLORS.employee.fill;
              let stroke = NODE_COLORS.employee.stroke;
              
              if (isPhase) {
                const riskLevel = node.riskLevel || 'ok';
                const colors = NODE_COLORS.phase[riskLevel as keyof typeof NODE_COLORS.phase] || NODE_COLORS.phase.default;
                fill = colors.fill;
                stroke = colors.stroke;
              } else if (node.type === 'order') {
                fill = NODE_COLORS.order.fill;
                stroke = NODE_COLORS.order.stroke;
              }

              const radius = isPhase ? 25 : (isEmployee ? 18 : 12);
              const glow = highlightSpof && nodeIsSPOF ? RISK_GLOW['critical'] : (isPhase ? RISK_GLOW[node.riskLevel || 'ok'] : 'none');

              return (
                <g
                  key={node.id}
                  transform={`translate(${pos.x}, ${pos.y})`}
                  onClick={() => handleNodeClick(node)}
                  onMouseEnter={() => setHoveredNode(node.id)}
                  onMouseLeave={() => setHoveredNode(null)}
                  className="cursor-pointer"
                  style={{ filter: glow }}
                >
                  {/* Outer ring for SPOF */}
                  {nodeIsSPOF && highlightSpof && (
                    <circle
                      r={radius + 6}
                      fill="none"
                      stroke="#ef4444"
                      strokeWidth={2}
                      strokeDasharray="4 2"
                      className="animate-pulse"
                    />
                  )}

                  {/* Selection ring */}
                  {isSelected && (
                    <circle
                      r={radius + 4}
                      fill="none"
                      stroke="#6366f1"
                      strokeWidth={2}
                    />
                  )}

                  {/* Main circle */}
                  <circle
                    r={radius}
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={2}
                    className={`transition-all duration-200 ${isHovered ? 'opacity-100' : 'opacity-90'}`}
                    style={{ transform: isHovered || isSelected ? 'scale(1.1)' : 'scale(1)' }}
                  />

                  {/* Icon */}
                  {isPhase && (
                    <Layers size={14} className="text-white" style={{ transform: 'translate(-7, -7)' }} />
                  )}
                  {isEmployee && (
                    <User size={12} className="text-white" style={{ transform: 'translate(-6, -6)' }} />
                  )}

                  {/* Label */}
                  <text
                    y={radius + 12}
                    textAnchor="middle"
                    fill="#94a3b8"
                    fontSize="10"
                    className="pointer-events-none"
                  >
                    {node.label.length > 12 ? node.label.substring(0, 12) + '...' : node.label}
                  </text>

                  {/* SPOF badge */}
                  {nodeIsSPOF && highlightSpof && (
                    <g transform={`translate(${radius - 4}, ${-radius + 4})`}>
                      <circle r={8} fill="#ef4444" />
                      <text
                        textAnchor="middle"
                        dominantBaseline="central"
                        fill="white"
                        fontSize="8"
                        fontWeight="bold"
                      >
                        !
                      </text>
                    </g>
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {/* Hover Tooltip */}
        {hoveredNode && !selectedNode && (
          <div className="absolute bottom-4 right-4 bg-slate-800 border border-slate-600 rounded-lg p-3 shadow-xl max-w-64">
            {(() => {
              const node = graph.nodes.find(n => n.id === hoveredNode);
              if (!node) return null;
              return (
                <>
                  <div className="flex items-center gap-2 mb-2">
                    {node.type === 'phase' && <Layers size={14} className="text-indigo-400" />}
                    {node.type === 'employee' && <User size={14} className="text-cyan-400" />}
                    <span className="font-medium text-white text-sm">{node.label}</span>
                  </div>
                  {isSPOF(node.id) && (
                    <p className="text-xs text-red-400 flex items-center gap-1">
                      <AlertTriangle size={10} />
                      Single Point of Failure
                    </p>
                  )}
                  <p className="text-xs text-slate-400 mt-1">Clique para ver detalhes</p>
                </>
              );
            })()}
          </div>
        )}
      </div>

      {/* Selected Node Details */}
      {selectedNodeData && (
        <div className="px-6 py-4 border-t border-slate-700 bg-slate-800/50">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                {selectedNodeData.type === 'phase' && <Layers size={16} className="text-indigo-400" />}
                {selectedNodeData.type === 'employee' && <User size={16} className="text-cyan-400" />}
                <h4 className="font-semibold text-white">{selectedNodeData.label}</h4>
                {isSPOF(selectedNodeData.id) && (
                  <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded">SPOF</span>
                )}
              </div>
              <p className="text-sm text-slate-400">
                Tipo: {selectedNodeData.type === 'phase' ? 'Fase de Produção' : 'Funcionário'}
                {selectedNodeData.riskLevel && ` • Risco: ${selectedNodeData.riskLevel.toUpperCase()}`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {selectedNodeData.type === 'phase' && (
                <button
                  onClick={() => onSimulate?.(selectedNodeData.id)}
                  className="flex items-center gap-2 px-3 py-1.5 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg text-sm"
                >
                  <Play size={12} />
                  Simular
                </button>
              )}
              <button
                onClick={() => setSelectedNode(null)}
                className="px-3 py-1.5 bg-slate-700 text-white rounded-lg text-sm"
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="px-6 py-3 border-t border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-indigo-500" />
            <span className="text-xs text-slate-400">Fase</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-cyan-500" />
            <span className="text-xs text-slate-400">Funcionário</span>
          </div>
          <div className="flex items-center gap-2 ml-4 pl-4 border-l border-slate-700">
            <div className="w-3 h-3 rounded-full bg-red-500 ring-1 ring-red-400 ring-offset-1 ring-offset-slate-900" />
            <span className="text-xs text-slate-400">SPOF</span>
          </div>
        </div>
        <p className="text-xs text-slate-500">
          <Info size={10} className="inline mr-1" />
          Dados: FuncionariosFasesAptos (902 registos)
        </p>
      </div>
    </div>
  );
}

export default DependencyGraph;

