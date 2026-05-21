/**
 * ReportExportButton — Onda 11 (K). Botão exportar relatório.
 *
 * Chama POST /v1/reports/generate com {template_id, format} e faz download
 * do ficheiro retornado. Templates suportados:
 *   • producao  ✓ live
 *   • cliente   ✓ live
 *   • qualidade ✓ live
 *   • payroll, cogs, inventario  ⚠ stubbed (status="not_implemented")
 *
 * Format: csv (default) ou json. PDF não suportado backend ainda — usar
 * CSV para já (browser-side print → PDF é workaround).
 */

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Download, ChevronDown, FileSpreadsheet } from 'lucide-react';
import { getApiBase } from '../../lib/api';

const TENANT = { 'X-Tenant-Id': '00000000-0000-0000-0000-000000000001' };
// Q.21.A — porta única via api.ts (concorda com VITE_API_URL).
const BASE = getApiBase();

const TEMPLATES = [
  { id: 'producao', label: 'Produção', wired: true },
  { id: 'cliente', label: 'Cliente', wired: true },
  { id: 'qualidade', label: 'Qualidade', wired: true },
  { id: 'payroll', label: 'Payroll', wired: false },
  { id: 'cogs', label: 'COGS', wired: false },
  { id: 'inventario', label: 'Inventário', wired: false },
] as const;
type TemplateId = (typeof TEMPLATES)[number]['id'];

interface Props {
  defaultTemplate?: TemplateId;
  className?: string;
}

export function ReportExportButton({ defaultTemplate = 'producao', className = '' }: Props) {
  const [open, setOpen] = useState(false);
  const [template, setTemplate] = useState<TemplateId>(defaultTemplate);

  const m = useMutation({
    mutationFn: async (tpl: TemplateId) => {
      const r = await fetch(`${BASE}/v1/reports/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...TENANT },
        body: JSON.stringify({ template_id: tpl, format: 'csv' }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return r.json();
    },
    onSuccess: (data: { status?: string; template_id?: string; message?: string; content?: string; filename?: string }) => {
      if (data?.status === 'not_implemented') {
        alert(`Template "${data.template_id}" ainda não implementado: ${data.message ?? ''}`);
        return;
      }
      const blob = new Blob([data.content ?? ''], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = data.filename ?? `${template}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setOpen(false);
    },
  });

  return (
    <div className={`relative inline-block ${className}`}>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => m.mutate(template)}
          disabled={m.isPending}
          className="inline-flex items-center gap-1.5 text-xs font-medium"
          style={{
            padding: '6px 12px',
            height: 32,
            background: 'var(--bg-2)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-md)',
            color: 'var(--fg-1)',
          }}
        >
          {m.isPending ? (
            <>A gerar…</>
          ) : (
            <>
              <Download size={13} />
              Exportar {TEMPLATES.find((t) => t.id === template)?.label}
            </>
          )}
        </button>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center justify-center"
          style={{
            padding: '6px 8px',
            height: 32,
            background: 'var(--bg-2)',
            border: '1px solid var(--bd-1)',
            borderRadius: 'var(--r-md)',
            color: 'var(--fg-2)',
          }}
          aria-label="Escolher template"
        >
          <ChevronDown size={12} />
        </button>
      </div>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 z-30 w-56 rounded-md border shadow-lg"
          style={{ background: 'var(--bg-1)', borderColor: 'var(--bd-1)' }}
        >
          <div className="px-3 py-2 text-[10px] uppercase tracking-wider border-b" style={{ color: 'var(--fg-3)', borderColor: 'var(--bd-1)' }}>
            Template
          </div>
          {TEMPLATES.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => {
                setTemplate(t.id);
                setOpen(false);
                m.mutate(t.id);
              }}
              className="w-full flex items-center justify-between px-3 py-2 text-xs hover:opacity-80 transition-opacity"
              style={{
                color: t.wired ? 'var(--fg-1)' : 'var(--fg-3)',
                background: template === t.id ? 'var(--bg-2)' : 'transparent',
              }}
            >
              <span className="flex items-center gap-2">
                <FileSpreadsheet size={12} />
                {t.label}
              </span>
              {!t.wired && (
                <span className="text-[10px]" style={{ color: 'var(--yellow)' }}>
                  stub
                </span>
              )}
            </button>
          ))}
          <div className="px-3 py-2 text-[10px] border-t" style={{ color: 'var(--fg-3)', borderColor: 'var(--bd-1)' }}>
            Formato CSV. PDF: Ctrl+P na page.
          </div>
        </div>
      )}
    </div>
  );
}
