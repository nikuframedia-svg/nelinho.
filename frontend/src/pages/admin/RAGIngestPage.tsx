import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Upload, FileText, Loader2, CheckCircle2, AlertTriangle, X } from 'lucide-react';
import { copilotApi } from '../../lib/api';
import { DarkPageLayout } from '../../layouts';
import { DarkCard, DarkButton, DarkInput, DarkSelect, DarkTextarea } from '../../components/dark';

export function RAGIngestPage() {
  const [sourceType, setSourceType] = useState('document');
  const [sourceId, setSourceId] = useState('');
  const [text, setText] = useState('');
  const [metadata, setMetadata] = useState('{}');
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  
  // Ingest mutation
  const ingestMutation = useMutation({
    mutationFn: async (data: {
      source_type: string;
      source_id: string;
      text: string;
      metadata?: Record<string, any>;
    }) => {
      return copilotApi.ingestRAG(data.source_type, data.source_id, data.text, data.metadata);
    },
    onSuccess: () => {
      // Reset form on success
      setSourceId('');
      setText('');
      setMetadata('{}');
      setFileName(null);
    },
  });

  const handleFileSelect = (file: File) => {
    if (file.type.startsWith('text/') || file.name.endsWith('.txt') || file.name.endsWith('.md')) {
      setFileName(file.name);
      const reader = new FileReader();
      reader.onload = (e) => {
        const content = e.target?.result as string;
        setText(content);
      };
      reader.readAsText(file);
    } else {
      alert('Only text files (.txt, .md) are supported.');
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    let parsedMetadata: Record<string, any> = {};
    try {
      parsedMetadata = JSON.parse(metadata);
    } catch (error) {
      alert('Invalid metadata. Must be valid JSON.');
      return;
    }
    
    if (!sourceId.trim()) {
      alert('Source ID is required.');
      return;
    }
    
    if (!text.trim()) {
      alert('Text content is required.');
      return;
    }
    
    ingestMutation.mutate({
      source_type: sourceType,
      source_id: sourceId,
      text: text.trim(),
      metadata: parsedMetadata,
    });
  };

  const handleClear = () => {
    setSourceId('');
    setText('');
    setMetadata('{}');
    setFileName(null);
    ingestMutation.reset();
  };

  const sourceTypeOptions = [
    { value: 'document', label: 'Document' },
    { value: 'knowledge_base', label: 'Knowledge Base' },
    { value: 'manual', label: 'Manual' },
    { value: 'faq', label: 'FAQ' },
    { value: 'other', label: 'Other' },
  ];

  return (
    <DarkPageLayout
      title="RAG Ingest"
      subtitle="Upload documents to the COPILOT RAG system"
      icon={<Upload size={20} />}
    >
      <DarkCard>
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Source Type */}
          <DarkSelect
            label="Source Type"
            options={sourceTypeOptions}
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
          />

          {/* Source ID */}
          <DarkInput
            label="Source ID"
            value={sourceId}
            onChange={(e) => setSourceId(e.target.value)}
            placeholder="e.g., doc-001, kb-manual-operations, faq-production"
            hint="Unique identifier for this document."
            required
          />

          {/* File Upload / Text Input */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              Content <span className="text-danger">*</span>
            </label>
            
            {/* Drag and Drop Area */}
            <div
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                dragActive
                  ? 'border-accent bg-accent/10'
                  : 'border-border-subtle bg-bg-elevated hover:border-border-hover'
              }`}
            >
              <Upload size={32} className="text-text-tertiary mx-auto mb-2" />
              <p className="text-sm text-text-secondary mb-2">
                Drag a file here or{' '}
                <label className="text-accent hover:text-accent-light cursor-pointer underline">
                  select a file
                  <input
                    type="file"
                    accept=".txt,.md,text/*"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleFileSelect(e.target.files[0]);
                      }
                    }}
                  />
                </label>
              </p>
              <p className="text-xs text-text-tertiary">
                Supported formats: .txt, .md
              </p>
              {fileName && (
                <div className="mt-4 flex items-center justify-center gap-2 text-sm text-text-white">
                  <FileText size={16} className="text-accent" />
                  <span>{fileName}</span>
                  <button
                    type="button"
                    onClick={() => {
                      setFileName(null);
                      setText('');
                    }}
                    className="text-danger hover:text-danger-light transition-colors"
                  >
                    <X size={16} />
                  </button>
                </div>
              )}
            </div>

            {/* Text Area */}
            <DarkTextarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Or type the text directly here..."
              rows={12}
              containerClassName="mt-4"
              className="font-mono text-sm"
              hint={`${text.length} characters`}
            />
          </div>

          {/* Metadata */}
          <DarkTextarea
            label="Metadata (JSON)"
            value={metadata}
            onChange={(e) => setMetadata(e.target.value)}
            placeholder='{"author": "John Doe", "category": "operations", "version": "1.0"}'
            rows={6}
            className="font-mono text-sm"
            hint="Additional metadata in JSON format (optional)."
          />

          {/* Success/Error Messages */}
          {ingestMutation.isSuccess && (
            <div className="flex items-center gap-2 p-4 bg-success/10 border border-success/30 rounded-lg text-success">
              <CheckCircle2 size={20} />
              <span>Document ingested successfully!</span>
            </div>
          )}

          {ingestMutation.isError && (
            <div className="flex items-center gap-2 p-4 bg-danger/10 border border-danger/30 rounded-lg text-danger-light">
              <AlertTriangle size={20} />
              <span>
                {(ingestMutation.error as any)?.message || 'Error ingesting document.'}
              </span>
            </div>
          )}

          {/* Submit Button */}
          <div className="flex justify-end gap-3 pt-4 border-t border-border-subtle">
            <DarkButton
              type="button"
              variant="secondary"
              onClick={handleClear}
            >
              Clear
            </DarkButton>
            <DarkButton
              type="submit"
              disabled={ingestMutation.isPending || !text.trim() || !sourceId.trim()}
              icon={ingestMutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            >
              {ingestMutation.isPending ? 'Ingesting...' : 'Ingest Document'}
            </DarkButton>
          </div>
        </form>
      </DarkCard>
    </DarkPageLayout>
  );
}
