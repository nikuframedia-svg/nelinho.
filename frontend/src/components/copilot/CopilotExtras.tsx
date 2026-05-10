/**
 * CopilotExtras — Onda 13 (M).
 *
 *   - DailyFeedbackForm — 👍/👎 + textarea → POST /api/copilot/feedback/user
 *   - RagIngestUploader — drag-drop ficheiro texto → POST /api/copilot/rag/ingest
 *   - InsightsCardWrapper — re-export do CopilotInsightsCard (existe)
 *   - MascotChip — chip pequeno com avatar Nelinho + status
 */

import { useRef, useState, type DragEvent, type ChangeEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { ThumbsUp, ThumbsDown, Send, Upload, FileText, Sparkles } from 'lucide-react';
import { Panel, ZipToneBadge } from '../dark';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
const BASE = 'http://127.0.0.1:8001';

// ═══════════════════════════════════════════════════════════════════════════
// DailyFeedbackForm
// ═══════════════════════════════════════════════════════════════════════════

export function DailyFeedbackForm() {
  const [thumb, setThumb] = useState<'up' | 'down' | null>(null);
  const [text, setText] = useState('');

  const m = useMutation({
    mutationFn: async () => {
      if (!thumb) throw new Error('Escolhe 👍 ou 👎.');
      const r = await fetch(`${BASE}/api/copilot/feedback/user`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...TENANT },
        body: JSON.stringify({ thumb, text, context: { source: 'daily-feedback-form' } }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    onSuccess: () => {
      setText('');
      setThumb(null);
    },
  });

  return (
    <Panel title="O que achaste hoje?" subtitle="Feedback ad-hoc — alimenta o Copilot">
      <div className="space-y-3">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setThumb('up')}
            className="flex-1 inline-flex items-center justify-center gap-2 rounded-md py-2 transition-colors"
            style={{
              background: thumb === 'up' ? 'var(--green-bg)' : 'var(--bg-2)',
              color: thumb === 'up' ? 'var(--green)' : 'var(--fg-2)',
              border: `1px solid ${thumb === 'up' ? 'var(--green)' : 'var(--bd-1)'}`,
            }}
          >
            <ThumbsUp size={14} />
            Bom
          </button>
          <button
            type="button"
            onClick={() => setThumb('down')}
            className="flex-1 inline-flex items-center justify-center gap-2 rounded-md py-2 transition-colors"
            style={{
              background: thumb === 'down' ? 'var(--red-bg)' : 'var(--bg-2)',
              color: thumb === 'down' ? 'var(--red)' : 'var(--fg-2)',
              border: `1px solid ${thumb === 'down' ? 'var(--red)' : 'var(--bd-1)'}`,
            }}
          >
            <ThumbsDown size={14} />
            Mau
          </button>
        </div>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          placeholder="Diz mais (opcional) — vai para o log de feedback do Copilot."
          className="w-full rounded-md border px-3 py-2 text-xs"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}
        />
        <div className="flex items-center justify-between">
          {m.isError && (
            <span className="text-xs" style={{ color: 'var(--red)' }}>
              {(m.error as Error).message}
            </span>
          )}
          {m.isSuccess && (
            <ZipToneBadge tone="green" size="sm">
              Recebido!
            </ZipToneBadge>
          )}
          <button
            type="button"
            onClick={() => m.mutate()}
            disabled={!thumb || m.isPending}
            className="ml-auto inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium"
            style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
          >
            <Send size={12} />
            {m.isPending ? 'A enviar…' : 'Enviar'}
          </button>
        </div>
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// RagIngestUploader
// ═══════════════════════════════════════════════════════════════════════════

export function RagIngestUploader() {
  const [dragOver, setDragOver] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const m = useMutation({
    mutationFn: async (file: File) => {
      const text = await file.text();
      const url = `${BASE}/api/copilot/rag/ingest?source_type=upload&source_id=${encodeURIComponent(file.name)}`;
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...TENANT },
        body: JSON.stringify({ text, metadata: { filename: file.name, size: file.size } }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
  });

  function onPick(list: FileList | null) {
    if (!list) return;
    const arr: File[] = [];
    for (let i = 0; i < list.length; i++) arr.push(list[i]);
    setFiles(arr);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    onPick(e.dataTransfer.files);
  }

  return (
    <Panel title="RAG ingest" subtitle="Drag-drop texto/markdown → POST /api/copilot/rag/ingest (admin)">
      <div className="space-y-3">
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className="rounded-md border-2 border-dashed py-8 text-center cursor-pointer transition-colors"
          style={{
            borderColor: dragOver ? 'var(--blue)' : 'var(--bd-2)',
            background: dragOver ? 'var(--blue-bg)' : 'var(--bg-2)',
            color: 'var(--fg-2)',
          }}
        >
          <Upload size={20} className="inline-block mb-2" style={{ color: 'var(--fg-3)' }} />
          <div className="text-xs">
            Arrasta ficheiros .txt/.md aqui ou clica para escolher
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".txt,.md,.markdown"
            multiple
            className="hidden"
            onChange={(e: ChangeEvent<HTMLInputElement>) => onPick(e.target.files)}
          />
        </div>
        {files.length > 0 && (
          <div className="space-y-1">
            {files.map((f, i) => (
              <div key={i} className="flex items-center justify-between rounded-md border px-3 py-2 text-xs" style={{ borderColor: 'var(--bd-1)', background: 'var(--bg-2)' }}>
                <span className="flex items-center gap-2 min-w-0">
                  <FileText size={12} style={{ color: 'var(--fg-3)' }} />
                  <span className="truncate" style={{ color: 'var(--fg-1)' }}>{f.name}</span>
                  <span style={{ color: 'var(--fg-3)' }}>({f.size}b)</span>
                </span>
                <button
                  type="button"
                  onClick={() => m.mutate(f)}
                  disabled={m.isPending}
                  className="rounded-md px-2 py-1 text-xs font-medium"
                  style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
                >
                  {m.isPending ? '…' : 'Ingest'}
                </button>
              </div>
            ))}
          </div>
        )}
        {m.isSuccess && (
          <div className="text-xs flex items-center gap-2" style={{ color: 'var(--green)' }}>
            <ZipToneBadge tone="green" size="sm">OK</ZipToneBadge>
            {(m.data as any)?.chunks_created ?? 0} chunks ingeridos
          </div>
        )}
        {m.isError && (
          <div className="text-xs" style={{ color: 'var(--red)' }}>
            Erro: {(m.error as Error).message} — necessita CONFIG_WRITE.
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// MascotChip — avatar Nelinho
// ═══════════════════════════════════════════════════════════════════════════

export function MascotChip() {
  return (
    <div
      className="inline-flex items-center gap-2 rounded-full px-2 py-1 text-xs"
      style={{ background: 'var(--bg-2)', border: '1px solid var(--bd-1)', color: 'var(--fg-2)' }}
    >
      <span
        className="inline-flex items-center justify-center w-6 h-6 rounded-full text-[10px] font-semibold"
        style={{ background: 'var(--blue)', color: 'white' }}
      >
        N
      </span>
      <span style={{ color: 'var(--fg-1)' }}>Nelinho</span>
      <Sparkles size={10} style={{ color: 'var(--blue)' }} />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Composição CopilotExtrasDashboard
// ═══════════════════════════════════════════════════════════════════════════

export function CopilotExtrasDashboard() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MascotChip />
          <span className="text-xs" style={{ color: 'var(--fg-3)' }}>
            Feedback diário · ingest RAG (admin)
          </span>
        </div>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda13 — M. Copilot
        </span>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <DailyFeedbackForm />
        <RagIngestUploader />
      </div>
    </div>
  );
}
