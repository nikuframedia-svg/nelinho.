/**
 * decisoes-realdata.spec.ts — E2E com DADOS REAIS + reject-lock (Q.119.5).
 * =========================================================================
 *
 * Diferente do smoke (panel.spec.ts, que só testa a shell): isto corre contra
 * o stack completo COM dados reais semeados (scripts/seed_nelo_demo.py: 3
 * decisões PROPOSED + 12 barcos + 4 moldes) e prova fluxos a fundo.
 *
 * O teste-chave é o REJECT-LOCK: rejeitar e aprovar chamam o MESMO endpoint
 * (`/v1/decisions/{id}/approve`) com `status` diferente. Um teste "o cartão
 * desapareceu" passaria para AMBOS e não apanharia o bug Q.118.S (rejeitar
 * aprovava). Por isso a asserção LÊ O STATUS RESULTANTE via API:
 *   rejeitar → GET /v1/decisions/{id} deve ser REJECTED (e nunca APPROVED).
 *
 * Pré-requisito: stack up (backend :8001 + frontend :5173) + seed fresco.
 * Selectores por prefixo ASCII em regex (robustos ao encoding PT-PT do ficheiro).
 */
import { test, expect, type Page } from '@playwright/test';

const TENANT = '00000000-0000-0000-0000-000000000001';
const USER = '00000000-0000-0000-0000-000000000001';
const API = 'http://127.0.0.1:8001';
const HEADERS = {
  'X-Tenant-Id': TENANT,
  'X-User-Id': USER,
  'X-User-Role': 'admin',
  Authorization: 'Bearer dev-e2e-token',
};

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('tenant_id', '00000000-0000-0000-0000-000000000001');
    localStorage.setItem('user_id', '00000000-0000-0000-0000-000000000001');
    localStorage.setItem('user_role', 'admin');
    localStorage.setItem('auth_token', 'dev-e2e-token');
  });
});

function trackPageErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('pageerror', (err) => errors.push(String(err)));
  return errors;
}

/**
 * Navega para /decisoes e captura a RESPOSTA EXACTA que a página usou para
 * renderizar (page_size=50, 200 — pós-redirect 307 e distinta da chamada do
 * Sidebar com page_size=1). Assim decisions[0] é, garantidamente, o cartão
 * actual que a página mostra. Contrato real: a lista vem em `decisions`
 * (não `items`) — ver Q.119.5.
 */
async function captureProposedList(page: Page): Promise<{ id: string }[]> {
  const listResp = page.waitForResponse(
    (r) =>
      /\/v1\/decisions\/?\?/.test(r.url()) &&
      r.url().includes('page_size=50') &&
      r.request().method() === 'GET' &&
      r.status() === 200,
    { timeout: 20_000 },
  );
  await page.goto('/decisoes');
  const body = await (await listResp).json();
  return (body.decisions ?? []) as { id: string }[];
}

test('Decisões — cartão renderiza com dados reais (não empty-state)', async ({ page }) => {
  const errors = trackPageErrors(page);
  const items = await captureProposedList(page);
  expect(items.length, 'o seed deve ter decisões PROPOSED').toBeGreaterThan(0);

  // O hub e os chips de entidade renderizam (conteúdo real, não vazio).
  await expect(page.getByTestId('decision-hub-actions').first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Rejeitar decis/ }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /Aprovar decis/ }).first()).toBeVisible();
  // NÃO deve estar no empty-state.
  await expect(page.getByText(/Sem decis.*pendentes/)).toHaveCount(0);

  expect(errors, errors.join('\n')).toHaveLength(0);
});

test('REJECT-LOCK — rejeitar marca REJECTED, nunca APPROVED (Q.118.S)', async ({ page }) => {
  const items = await captureProposedList(page);
  expect(items.length, 'precisa de ≥1 decisão PROPOSED').toBeGreaterThan(0);
  const targetId = items[0].id; // a página mostra items[0] como cartão actual

  await expect(page.getByRole('button', { name: /Rejeitar decis/ }).first()).toBeVisible();
  const approveResp = page.waitForResponse(
    (r) => r.url().includes(`/v1/decisions/${targetId}/approve`) && r.request().method() === 'POST',
    { timeout: 15_000 },
  );
  await page.getByRole('button', { name: /Rejeitar decis/ }).first().click();
  expect((await approveResp).ok()).toBeTruthy();

  // ASSERÇÃO CRÍTICA: o status resultante prova rejeitar ≠ aprovar.
  const check = await page.request.get(`${API}/v1/decisions/${targetId}`, { headers: HEADERS });
  expect(check.ok()).toBeTruthy();
  const dec = await check.json();
  expect(dec.status, `decisão ${targetId} devia ficar REJECTED`).toMatch(/REJECT/i);
  expect(dec.status).not.toMatch(/APPROV/i);
});

test('APPROVE — aprovar marca APPROVED', async ({ page }) => {
  const items = await captureProposedList(page);
  expect(items.length, 'precisa de ≥1 decisão PROPOSED restante').toBeGreaterThan(0);
  const targetId = items[0].id;

  await expect(page.getByRole('button', { name: /Aprovar decis/ }).first()).toBeVisible();
  const approveResp = page.waitForResponse(
    (r) => r.url().includes(`/v1/decisions/${targetId}/approve`) && r.request().method() === 'POST',
    { timeout: 15_000 },
  );
  await page.getByRole('button', { name: /Aprovar decis/ }).first().click();
  expect((await approveResp).ok()).toBeTruthy();

  const check = await page.request.get(`${API}/v1/decisions/${targetId}`, { headers: HEADERS });
  expect(check.ok()).toBeTruthy();
  const dec = await check.json();
  expect(dec.status, `decisão ${targetId} devia ficar APPROVED`).toMatch(/APPROV/i);
});
