/**
 * entity-sheets.spec.ts — fichas contextuais de entidade no /overall (Q.R).
 * =========================================================================
 *
 * Prova o contrato das fichas (Q.116.A / Q.118.C):
 *   clicar numa entidade no /overall  →  URL `?sheet=<kind>&id=<id>`
 *   →  abre `[role="dialog"]`  →  Esc fecha e limpa o `?sheet` da URL.
 *
 * Corre contra o stack VIVO (frontend :5173 → backend :8001 → Postgres),
 * com dados REAIS — zero mocks. Se uma vista não tiver dados reais para
 * clicar (plano vazio, stub de expedição sem lotes), o teste faz
 * `test.skip()` honesto em vez de inventar dados.
 *
 * Erros: distinguimos erros de FRONTEND (pageerror / console.error da app →
 * falham o teste) de 4xx de rede (precondição de dados do backend, Fase 1 →
 * anotados no relatório, não falham — não são desta lane e não os escondemos).
 *
 * Pontos de clique que existem hoje no /overall:
 *   • encomenda — OpCard (vista Por fase, default)
 *   • fase      — cabeçalho de lane da vista Por fase
 *   • operador  — cabeçalho de lane da vista Por pessoa (?view=pessoa)
 *   • cliente   — lote de cliente único da vista Por expedição (?view=expedicao)
 * `modelo` não tem ponto de clique no /overall (a ficha Modelo abre de dentro
 * de outras sheets) e o entityApi não expõe lista para deep-link com id real
 * (zero mocks) — o contrato é idêntico e fica provado pelos kinds acima + pelo
 * unit test `EntitySheetProvider.test.tsx`. Verificação visual da ficha Modelo
 * fica para a sessão com chrome-devtools-mcp (plano Fase 2).
 */
import { test, expect, type Locator, type Page, type TestInfo } from '@playwright/test';

function seedAuth() {
  localStorage.setItem('tenant_id', '00000000-0000-0000-0000-000000000001');
  localStorage.setItem('user_id', '00000000-0000-0000-0000-000000000001');
  localStorage.setItem('user_role', 'admin');
  localStorage.setItem('auth_token', 'dev-e2e-token');
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedAuth);
});

/** Coletores por-teste (sem estado global → sem contaminação entre testes). */
function watchErrors(page: Page): { jsErrors: string[]; netErrors: string[] } {
  const jsErrors: string[] = [];
  const netErrors: string[] = [];
  page.on('pageerror', (e) => jsErrors.push(String(e).slice(0, 200)));
  page.on('console', (m) => {
    if (m.type() !== 'error') return;
    const t = m.text();
    // 4xx de recurso = estado de dados do backend (precondição Fase 1), não um
    // erro de frontend.
    if (/Failed to load resource|net::ERR|status of 4\d\d/i.test(t)) netErrors.push(t.slice(0, 200));
    else jsErrors.push(t.slice(0, 200));
  });
  return { jsErrors, netErrors };
}

function finish(info: TestInfo, jsErrors: string[], netErrors: string[]): void {
  if (netErrors.length) {
    info.annotations.push({ type: 'backend-4xx (fora desta lane)', description: netErrors.join(' | ') });
  }
  expect(jsErrors, `erros de frontend:\n${jsErrors.join('\n')}`).toHaveLength(0);
}

async function gotoOverall(page: Page, view?: 'barco' | 'pessoa' | 'expedicao'): Promise<void> {
  // domcontentloaded (não networkidle: a app faz polling 5s + SSE).
  await page.goto(view ? `/overall?view=${view}` : '/overall', { waitUntil: 'domcontentloaded' });
  // Dá tempo às queries do plano para renderizarem antes de procurar a entidade.
  await page
    .locator('[data-clickable]')
    .first()
    .waitFor({ state: 'visible', timeout: 15000 })
    .catch(() => {});
}

/** Devolve null (em vez de rebentar) quando não há dados reais para clicar. */
async function firstClickable(page: Page, kind: string): Promise<Locator | null> {
  const loc = page.locator(`[data-clickable][data-kind="${kind}"]`).first();
  const ok = await loc
    .waitFor({ state: 'visible', timeout: 12000 })
    .then(() => true)
    .catch(() => false);
  return ok ? loc : null;
}

/** Clica → valida dialog + `?sheet=<kind>` → Esc → dialog some + URL limpa. */
async function openThenEsc(page: Page, kind: string, opener: Locator): Promise<void> {
  await opener.click();

  await expect(page.getByRole('dialog').first()).toBeVisible();
  await expect
    .poll(() => new URL(page.url()).searchParams.get('sheet'), { timeout: 6000 })
    .toBe(kind);

  await page.keyboard.press('Escape');

  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect
    .poll(() => new URL(page.url()).searchParams.has('sheet'), { timeout: 6000 })
    .toBe(false);
}

test.describe('Fichas de entidade (/overall)', () => {
  test('encomenda — clicar no OpCard abre a ficha e Esc fecha', async ({ page }, info) => {
    const { jsErrors, netErrors } = watchErrors(page);
    await gotoOverall(page);
    const opener = await firstClickable(page, 'encomenda');
    test.skip(!opener, 'Sem operações reais no plano actual — nada para clicar (encomenda).');
    await openThenEsc(page, 'encomenda', opener!);
    finish(info, jsErrors, netErrors);
  });

  test('fase — clicar no cabeçalho da lane (Por fase) abre a ficha e Esc fecha', async ({ page }, info) => {
    const { jsErrors, netErrors } = watchErrors(page);
    await gotoOverall(page);
    const opener = await firstClickable(page, 'fase');
    test.skip(!opener, 'Sem fases reais no plano actual — nada para clicar (fase).');
    await openThenEsc(page, 'fase', opener!);
    finish(info, jsErrors, netErrors);
  });

  test('operador — clicar na lane (Por pessoa) abre a ficha e Esc fecha', async ({ page }, info) => {
    const { jsErrors, netErrors } = watchErrors(page);
    await gotoOverall(page, 'pessoa');
    const opener = await firstClickable(page, 'operador');
    test.skip(!opener, 'Sem operadores reais no plano actual — nada para clicar (operador).');
    await openThenEsc(page, 'operador', opener!);
    finish(info, jsErrors, netErrors);
  });

  test('cliente — clicar num lote (Por expedição) abre a ficha e Esc fecha', async ({ page }, info) => {
    const { jsErrors, netErrors } = watchErrors(page);
    await gotoOverall(page, 'expedicao');
    const opener = await firstClickable(page, 'cliente');
    test.skip(
      !opener,
      'Sem lotes de cliente único na expedição (stub Q.115.L.2 sem dados) — nada para clicar (cliente).',
    );
    await openThenEsc(page, 'cliente', opener!);
    finish(info, jsErrors, netErrors);
  });

  // NOTA: `modelo` não tem ponto de clique no /overall (a ficha Modelo abre de
  // dentro de outras sheets) e o entityApi não expõe lista para deep-link com id
  // real (zero mocks → não inventamos id). O contrato ?sheet/[role=dialog]/Esc é
  // idêntico e fica provado por encomenda/fase/operador acima + pelo unit test
  // EntitySheetProvider.test.tsx. Verificação visual da ficha Modelo → sessão
  // chrome-devtools-mcp (plano Fase 2).
});
