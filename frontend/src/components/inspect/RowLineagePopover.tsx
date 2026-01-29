/**
 * Row Lineage Popover
 * ====================
 * 
 * Shows lineage information for any data row.
 * Displays source_sheet, row_number, row_hash, ingestion_id.
 * 
 * Usage:
 * <RowLineagePopover 
 *   sourceSheet="FasesOrdemFabrico" 
 *   rowNumber={12345}
 *   rowHash="abc123..."
 *   ingestionId="uuid-here"
 * >
 *   <button>View Lineage</button>
 * </RowLineagePopover>
 */

import React, { useState, useRef, useEffect } from 'react';
import { 
  GitBranch, 
  FileSpreadsheet, 
  Hash, 
  Database,
  Clock,
  Copy,
  Check,
  ExternalLink,
} from 'lucide-react';

interface RowLineageProps {
  sourceSheet: string;
  rowNumber: number;
  rowHash: string;
  ingestionId: string;
  ingestionTimestamp?: string;
  dataVersion?: string;
  children: React.ReactNode;
}

export function RowLineagePopover({
  sourceSheet,
  rowNumber,
  rowHash,
  ingestionId,
  ingestionTimestamp,
  dataVersion,
  children,
}: RowLineageProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current && 
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Copy to clipboard
  const copyField = (field: string, value: string) => {
    navigator.clipboard.writeText(value);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  return (
    <div ref={containerRef} className="relative inline-block">
      {/* Trigger */}
      <div 
        className="cursor-pointer"
        onClick={() => setIsOpen(!isOpen)}
      >
        {children}
      </div>

      {/* Popover Panel */}
      {isOpen && (
        <div className="absolute z-50 w-72 top-full mt-2 left-0 bg-gray-900 border border-gray-700 rounded-lg shadow-xl">
          {/* Header */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-700">
            <GitBranch className="w-4 h-4 text-purple-400" />
            <span className="font-medium text-white text-sm">Row Lineage</span>
          </div>

          {/* Content */}
          <div className="p-4 space-y-3">
            {/* Source Sheet */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-gray-400">
                <FileSpreadsheet className="w-4 h-4" />
                <span className="text-xs">Source Sheet</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-sm text-emerald-400 font-mono">
                  {sourceSheet}
                </span>
                <button
                  onClick={() => copyField('sheet', sourceSheet)}
                  className="p-1 hover:bg-gray-800 rounded transition-colors"
                >
                  {copiedField === 'sheet' ? (
                    <Check className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <Copy className="w-3 h-3 text-gray-500" />
                  )}
                </button>
              </div>
            </div>

            {/* Row Number */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-gray-400">
                <span className="text-xs">#</span>
                <span className="text-xs">Row Number</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-sm text-white font-mono">
                  {rowNumber.toLocaleString()}
                </span>
                <button
                  onClick={() => copyField('row', rowNumber.toString())}
                  className="p-1 hover:bg-gray-800 rounded transition-colors"
                >
                  {copiedField === 'row' ? (
                    <Check className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <Copy className="w-3 h-3 text-gray-500" />
                  )}
                </button>
              </div>
            </div>

            {/* Row Hash */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-gray-400">
                <Hash className="w-4 h-4" />
                <span className="text-xs">Row Hash</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-sm text-blue-400 font-mono">
                  {rowHash.slice(0, 12)}...
                </span>
                <button
                  onClick={() => copyField('hash', rowHash)}
                  className="p-1 hover:bg-gray-800 rounded transition-colors"
                >
                  {copiedField === 'hash' ? (
                    <Check className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <Copy className="w-3 h-3 text-gray-500" />
                  )}
                </button>
              </div>
            </div>

            {/* Ingestion ID */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-gray-400">
                <Database className="w-4 h-4" />
                <span className="text-xs">Ingestion ID</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-sm text-purple-400 font-mono">
                  {ingestionId.slice(0, 8)}...
                </span>
                <button
                  onClick={() => copyField('ingestion', ingestionId)}
                  className="p-1 hover:bg-gray-800 rounded transition-colors"
                >
                  {copiedField === 'ingestion' ? (
                    <Check className="w-3 h-3 text-emerald-400" />
                  ) : (
                    <Copy className="w-3 h-3 text-gray-500" />
                  )}
                </button>
              </div>
            </div>

            {/* Ingestion Timestamp */}
            {ingestionTimestamp && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-gray-400">
                  <Clock className="w-4 h-4" />
                  <span className="text-xs">Ingested At</span>
                </div>
                <span className="text-sm text-gray-300">
                  {new Date(ingestionTimestamp).toLocaleString()}
                </span>
              </div>
            )}

            {/* Data Version */}
            {dataVersion && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-gray-400">
                  <GitBranch className="w-4 h-4" />
                  <span className="text-xs">Data Version</span>
                </div>
                <span className="text-sm text-white font-mono">
                  {dataVersion}
                </span>
              </div>
            )}

            {/* Divider */}
            <hr className="border-gray-700" />

            {/* Actions */}
            <div className="flex gap-2">
              <button className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-xs text-gray-300 transition-colors">
                <ExternalLink className="w-3 h-3" />
                View in Source
              </button>
              <button 
                onClick={() => {
                  const fullLineage = {
                    sourceSheet,
                    rowNumber,
                    rowHash,
                    ingestionId,
                    ingestionTimestamp,
                    dataVersion,
                  };
                  navigator.clipboard.writeText(JSON.stringify(fullLineage, null, 2));
                  setCopiedField('all');
                  setTimeout(() => setCopiedField(null), 2000);
                }}
                className="flex items-center justify-center gap-1 px-3 py-2 bg-gray-800 hover:bg-gray-700 rounded text-xs text-gray-300 transition-colors"
              >
                {copiedField === 'all' ? (
                  <>
                    <Check className="w-3 h-3 text-emerald-400" />
                    Copied!
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    Copy All
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default RowLineagePopover;





