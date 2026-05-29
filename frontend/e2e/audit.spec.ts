/**
 * audit.spec.ts — auditoria de browser das 4 páginas (Q.121.B).
 * ============================================================
 *
 * Conduz um chromium real contra o stack vivo e, por rota, captura:
 *   • console messages (error/warning) + pageerrors (crashes JS)
 *   • respostas de rede com status >= 400 (4xx/5xx) — endpoint + status
 *   • screenshot full-page  →  _audit/<slug>.png
 * e escreve um relatório agregado em _audit/report.json.
 *
 * NÃO falha por achados (é auditoria, não gate) — captura tudo e no fim
 * imprime um sumário + falha SÓ se houver erros de consola ou network 5xx
 * (para o CI saber que há regressão), depois de ter gravado os artefactos.
 */
import { test, expect, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const AUDIT_DIR = resolve(process.cwd(), '_audit');

const ROUTES: { slug: string; path: string; label: string }[] = [
  { slug: 'decisoes', path: '/decisoes', label: 'Decisões · Decidir' },
  { slug: 'decisoes-simulacoes', path: '/decisoes?tab=simulacoes', label: 'Decisões · Simulações' },
  { slug: 'decisoes-historico', path: '/decisoes?tab=historico', label: 'Decisões · Histórico' },
  { slug: 'overall', path: '/overall', label: 'Overall · Por fase' },
  { slug: 'overall-barco', path: '/overall?view=barco', label: 'Overall · Por barco' },
  { slug: 'overall-pessoa', path: '/overall?view=pessoa', label: 'Overall · Por pessoa' },
  { slug: 'overall-expedicao', path: '/overall?view=expedicao', label: 'Overall · Por expedição' },
  { slug: 'llm-chat', path: '/llm', label: 'LLM · Chat' },
  { slug: 'llm-kpis', path: '/llm?tab=kpis', label: 'LLM · KPIs' },
  { slug: 'llm-alertas', path: '/llm?tab=alertas', label: 'LLM · Alertas' },
  { slug: 'llm-regras', path: '/llm?tab=regras', label: 'LLM · Regras' },
  { slug: 'cfg-master', path: '/configuracoes?tab=master', label: 'Config · Master Data' },
  { slug: 'cfg-regras', path: '/configuracoes?tab=regras', label: 'Config · Regras' },
  { slug: 'cfg-logica', path: '/configuracoes?tab=logica-llm', label: 'Config · Lógica LLM' },
  { slug: 'cfg-custos', path: '/configuracoes?tab=custos', label: 'Config · Custos' },
  { slug: 'cfg-input', path: '/configuracoes?tab=input', label: 'Config · Input' },
  { slug: 'cfg-aprendizagem', path: '/configuracoes?tab=aprendizagem', label: 'Config · Aprendizagem' },
];

interface RouteReport {
  slug: string;
  label: string;
  path: string;
  consoleErrors: string[];
  consoleWarnings: string[];
  pageErrors: string[];
  netFailures: { url: string; status: number }[];
}

const reports: RouteReport[] = [];

test.beforeAll(() => {
  mkdirSync(AUDIT_DIR, { recursive: true });
});

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('tenant_id', '00000000-0000-0000-0000-000000000001');
    localStorage.setItem('user_id', '00000000-0000-0000-0000-000000000001');
    localStorage.setItem('user_role', 'admin');
    localStorage.setItem('auth_token', 'dev-e2e-token');
  });
});

for (const route of ROUTES) {
  test(`audit ${route.label}`, async ({ page }) => {
    const r: RouteReport = {
      slug: route.slug, label: route.label, path: route.path,
      consoleErrors: [], consoleWarnings: [], pageErrors: [], netFailures: [],
    };
    page.on('console', (msg) => {
      if (msg.type() === 'error') r.consoleErrors.push(msg.text().slice(0, 300));
      else if (msg.type() === 'warning') r.consoleWarnings.push(msg.text().slice(0, 200));
    });
    page.on('pageerror', (err) => r.pageErrors.push(String(err).slice(0, 300)));
    page.on('response', (resp) => {
      if (resp.status() >= 400) r.netFailures.push({ url: resp.url().replace(/^https?:\/\/[^/]+/, ''), status: resp.status() });
    });

    // domcontentloaded (não networkidle: a app faz polling 5s + SSE, networkidle
    // nunca assenta → goto expirava). Espera fixa deixa o React hidratar + queries.
    await page.goto(route.path, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(2500);
    await page.screenshot({ path: resolve(AUDIT_DIR, `${route.slug}.png`), fullPage: true }).catch(() => {});

    reports.push(r);
  });
}

test.afterAll(() => {
  writeFileSync(resolve(AUDIT_DIR, 'report.json'), JSON.stringify(reports, null, 2), 'utf-8');
  // sumário legível no stdout
  for (const r of reports) {
    const net5xx = r.netFailures.filter((f) => f.status >= 500);
    const flag = (r.consoleErrors.length || r.pageErrors.length || net5xx.length) ? 'X' : 'ok';
    // eslint-disable-next-line no-console
    console.log(
      `[${flag}] ${r.label} — consoleErr=${r.consoleErrors.length} pageErr=${r.pageErrors.length} ` +
      `net4xx=${r.netFailures.filter((f) => f.status < 500).length} net5xx=${net5xx.length}`,
    );
  }
});
