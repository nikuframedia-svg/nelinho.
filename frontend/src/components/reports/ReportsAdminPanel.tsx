/**
 * ReportsAdminPanel — Onda 18 (R). Reports schedule + email + retention.
 *
 *   - POST /v1/reports/schedule       (cron picker stub)
 *   - POST /v1/reports/email          (email delivery stub)
 *   - POST /v1/reports/retention      (GDPR retention picker stub)
 *
 * Q.67.2.B — migrado de `apiFetch` directo para `reportsApi` (lib/api/platformApi.ts;
 * `setRetention` adicionado neste sub-sprint) + `reportsKeys` (lib/api/keys.ts).
 * Tenant + trace_id injectados via `request()` (Q.61.12).
 */

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Calendar, Mail, Shield, Send } from 'lucide-react';
import { Panel, ZipToneBadge } from '../dark';
import { reportsApi, type ReportTemplateId } from '../../lib/api/platformApi';
import { reportsKeys } from '../../lib/api/keys';

const TEMPLATES: ReadonlyArray<ReportTemplateId> = [
  'producao',
  'cliente',
  'qualidade',
  'payroll',
  'cogs',
  'inventario',
];

// ═══════════════════════════════════════════════════════════════════════════
// SchedulePanel
// ═══════════════════════════════════════════════════════════════════════════

export function SchedulePanel() {
  const qc = useQueryClient();
  const [tpl, setTpl] = useState<ReportTemplateId>('producao');
  const [cron, setCron] = useState('0 8 * * MON');

  const m = useMutation({
    mutationFn: () => reportsApi.createSchedule({ template_id: tpl, cron, enabled: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: reportsKeys.schedules() });
    },
  });

  return (
    <Panel title="Schedule auto (cron)" subtitle="POST /v1/reports/schedule">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <select value={tpl} onChange={(e) => setTpl(e.target.value as ReportTemplateId)}
            className="rounded-md border px-2 py-1.5 text-xs"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}>
            {TEMPLATES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <input type="text" value={cron} onChange={(e) => setCron(e.target.value)}
            placeholder="0 8 * * MON"
            className="rounded-md border px-2 py-1.5 text-xs font-mono"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
        </div>
        <div className="flex gap-1 flex-wrap text-[10px]" style={{ color: 'var(--fg-3)' }}>
          {[
            { label: 'Diário 8h', cron: '0 8 * * *' },
            { label: 'Sex 17h', cron: '0 17 * * FRI' },
            { label: 'Início mês', cron: '0 9 1 * *' },
          ].map((p) => (
            <button key={p.label} onClick={() => setCron(p.cron)}
              className="rounded px-2 py-0.5"
              style={{ background: 'var(--bg-3)', color: 'var(--fg-2)' }}>
              {p.label}
            </button>
          ))}
        </div>
        <button
          onClick={() => m.mutate()}
          disabled={m.isPending}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          <Calendar size={12} />
          {m.isPending ? '…' : 'Agendar'}
        </button>
        {m.isSuccess && <ZipToneBadge tone="green" size="sm">Agendado (stub)</ZipToneBadge>}
        {m.isError && (
          <div className="text-xs" style={{ color: 'var(--red)' }}>
            {(m.error as Error).message}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// EmailPanel
// ═══════════════════════════════════════════════════════════════════════════

export function EmailPanel() {
  const qc = useQueryClient();
  const [tpl, setTpl] = useState<ReportTemplateId>('producao');
  const [to, setTo] = useState('luis@nikufra.ai');
  const [cron, setCron] = useState('0 8 * * MON');

  const m = useMutation({
    mutationFn: async () => {
      const recipients = to.split(',').map((s) => s.trim()).filter(Boolean);
      if (recipients.length === 0) throw new Error('Pelo menos um email destinatário.');
      return reportsApi.email({
        template_id: tpl,
        to: recipients,
        schedule_cron: cron || null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: reportsKeys.emails() });
    },
  });

  return (
    <Panel title="Email delivery" subtitle="POST /v1/reports/email (SMTP integration pending)">
      <div className="space-y-3">
        <select value={tpl} onChange={(e) => setTpl(e.target.value as ReportTemplateId)}
          className="w-full rounded-md border px-2 py-1.5 text-xs"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}>
          {TEMPLATES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input type="text" value={to} onChange={(e) => setTo(e.target.value)}
          placeholder="emails (csv): luis@nikufra.ai, ana@..."
          className="w-full rounded-md border px-2 py-1.5 text-xs"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
        <input type="text" value={cron} onChange={(e) => setCron(e.target.value)}
          placeholder="cron opcional"
          className="w-full rounded-md border px-2 py-1.5 text-xs font-mono"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
        <button
          onClick={() => m.mutate()}
          disabled={m.isPending}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          <Send size={12} />
          {m.isPending ? '…' : 'Configurar entrega'}
        </button>
        {m.isSuccess && <ZipToneBadge tone="green" size="sm">Configurado (stub)</ZipToneBadge>}
        {m.isError && (
          <div className="text-xs" style={{ color: 'var(--red)' }}>
            {(m.error as Error).message}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// RetentionPanel
// ═══════════════════════════════════════════════════════════════════════════

export function RetentionPanel() {
  const qc = useQueryClient();
  const [tpl, setTpl] = useState<ReportTemplateId>('producao');
  const [days, setDays] = useState(365);

  const m = useMutation({
    mutationFn: () => reportsApi.setRetention({ template_id: tpl, retention_days: days }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: reportsKeys.retentions() });
    },
  });

  return (
    <Panel title="GDPR retention" subtitle="POST /v1/reports/retention (cleanup job pending)">
      <div className="space-y-3">
        <select value={tpl} onChange={(e) => setTpl(e.target.value as ReportTemplateId)}
          className="w-full rounded-md border px-2 py-1.5 text-xs"
          style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }}>
          {TEMPLATES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <div className="flex gap-2 items-center">
          <input type="number" value={days} min={7} max={3650} onChange={(e) => setDays(Number(e.target.value) || 365)}
            className="w-32 rounded-md border px-2 py-1.5 text-xs tabular-nums"
            style={{ background: 'var(--bg-2)', borderColor: 'var(--bd-1)', color: 'var(--fg-1)' }} />
          <span className="text-xs" style={{ color: 'var(--fg-3)' }}>dias</span>
          <span className="text-xs ml-auto" style={{ color: 'var(--fg-3)' }}>≈ {(days / 365).toFixed(1)} anos</span>
        </div>
        <div className="flex gap-1 text-[10px]">
          {[90, 365, 730, 1825].map((d) => (
            <button key={d} onClick={() => setDays(d)}
              className="rounded px-2 py-0.5"
              style={{ background: 'var(--bg-3)', color: 'var(--fg-2)' }}>
              {d === 90 ? '3m' : d === 365 ? '1a' : d === 730 ? '2a' : '5a'}
            </button>
          ))}
        </div>
        <button
          onClick={() => m.mutate()}
          disabled={m.isPending}
          className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium"
          style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}
        >
          <Shield size={12} />
          {m.isPending ? '…' : 'Definir retenção'}
        </button>
        {m.isSuccess && <ZipToneBadge tone="green" size="sm">Definido (stub)</ZipToneBadge>}
      </div>
    </Panel>
  );
}

export function ReportsAdminDashboard() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <span className="text-xs flex items-center gap-2" style={{ color: 'var(--fg-2)' }}>
          <Mail size={13} />
          Reports — schedule auto / email delivery / GDPR retention
        </span>
        <span className="text-[10px]" style={{ color: 'var(--fg-3)' }}>
          Q.18.ZIP.A.Onda18 — R. Reports
        </span>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <SchedulePanel />
        <EmailPanel />
        <RetentionPanel />
      </div>
      <div className="text-[10px] flex items-center gap-2 px-1" style={{ color: 'var(--fg-3)' }}>
        Os 3 endpoints respondem 200 com status="stubbed" — persistência em
        ReportSchedule/ReportEmail/ReportRetention models requer migration
        dedicada. SMTP integration + cleanup job idem.
      </div>
    </div>
  );
}
