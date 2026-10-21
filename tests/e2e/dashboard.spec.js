const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

function dashboardPath(testInfo) {
  return testInfo.project.name === 'mobile Chromium' ? 'mobile.html' : './';
}

async function blockOptionalAnalytics(page) {
  await page.route(/(goatcounter\.com|gc\.zgo\.at)/, (route) => route.abort());
}

async function openDashboard(page, testInfo) {
  await blockOptionalAnalytics(page);
  await page.goto(dashboardPath(testInfo));
  await expect(page.locator('#app-status')).toContainText('Datos listos:');
}

async function selectWholesale(page) {
  await page.locator('label.format-option:has(input[value="wholesale"])').click();
  await expect(page.getByRole('radio', { name: 'Autoservicios mayoristas' })).toBeChecked();
}

test('boots with published data and keeps retail formats isolated', async ({ page }, testInfo) => {
  await openDashboard(page, testInfo);

  await expect(page).toHaveTitle(/Pulso del retail argentino/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Pulso del retail argentino');
  await expect(page.locator('#gate-value')).toHaveText('APROBADO');
  const supermarketSales = await page.locator('#nominal-sales').textContent();

  await selectWholesale(page);

  await expect(page.locator('#app-status')).toContainText('Autoservicios mayoristas');
  await expect(page.locator('#nominal-sales')).not.toHaveText(supermarketSales);
  await expect(page.getByRole('radio', { name: 'Supermercados' })).not.toBeChecked();
});

test('year filter updates the effective period', async ({ page }, testInfo) => {
  await openDashboard(page, testInfo);

  await page.locator('#year-filter').selectOption('2025');

  await expect(page.locator('#year-filter')).toHaveValue('2025');
  await expect(page.locator('#overview-date')).toContainText('2025');
  await expect(page.locator('#app-status')).toContainText('2025');
});

test('tabs expose ARIA state and support arrow-key navigation', async ({ page }, testInfo) => {
  await openDashboard(page, testInfo);
  const overview = page.getByRole('tab', { name: 'Panorama' });
  const payments = page.getByRole('tab', { name: 'Medios de pago' });
  const categories = page.getByRole('tab', { name: 'Categorías' });

  await overview.focus();
  await overview.press('ArrowRight');
  await expect(payments).toBeFocused();
  await expect(payments).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#payments')).toBeVisible();

  await payments.press('ArrowRight');
  await expect(categories).toBeFocused();
  await expect(categories).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#categories')).toBeVisible();
  await expect(overview).toHaveAttribute('tabindex', '-1');
});

test('category selection updates its KPI without changing the global format', async ({ page }, testInfo) => {
  await openDashboard(page, testInfo);
  await page.getByRole('tab', { name: 'Categorías' }).click();
  const sales = page.locator('#category-sales');
  const grocerySales = await sales.textContent();

  await page.locator('#category-filter').selectOption('beverages');

  await expect(page.locator('#category-filter')).toHaveValue('beverages');
  await expect(sales).not.toHaveText(grocerySales);
  await expect(page.getByRole('radio', { name: 'Supermercados' })).toBeChecked();
});

test('missing wholesale channel detail falls back without imputing zero', async ({ page }, testInfo) => {
  await openDashboard(page, testInfo);
  await selectWholesale(page);
  await page.locator('#year-filter').selectOption('2026');
  await page.getByRole('tab', { name: 'Canales y calidad' }).click();

  await expect(page.locator('#online-share')).not.toHaveText('0,00%');
  await expect(page.locator('#online-note')).toContainText('2022');
  await expect(page.locator('#channel-date')).toContainText('2022');
  await expect(page.locator('#channel-coverage')).toContainText('nunca como cero');
  await expect(page.locator('#channels-chart .empty-chart')).toContainText('agosto de 2022');
});

test('reset filters restores the initial format, year, category and tab', async ({ page }, testInfo) => {
  await openDashboard(page, testInfo);
  const year = page.locator('#year-filter');
  const initialYear = await year.inputValue();
  await selectWholesale(page);
  await year.selectOption('2025');
  await page.getByRole('tab', { name: 'Categorías' }).click();
  await page.locator('#category-filter').selectOption('beverages');

  await page.getByRole('button', { name: 'Restablecer filtros' }).click();

  await expect(page.getByRole('radio', { name: 'Supermercados' })).toBeChecked();
  await expect(year).toHaveValue(initialYear);
  await expect(page.locator('#category-filter')).toHaveValue('grocery');
  await expect(page.getByRole('tab', { name: 'Panorama' })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await expect(page.locator('#overview')).toBeVisible();
});

test('reset chart view restores Plotly autorange', async ({ page }, testInfo) => {
  await openDashboard(page, testInfo);
  const plot = page.locator('.plot-surface.js-plotly-plot').first();
  await expect(plot).toBeVisible();
  await plot.evaluate((node) =>
    window.Plotly.relayout(node, { 'xaxis.range': ['2025-01-01', '2025-02-01'] }),
  );

  await page.getByRole('button', { name: 'Restablecer vista' }).click();

  await expect(page.locator('#app-status')).toHaveText('Vista de los gráficos restablecida.');
  await expect.poll(() => plot.evaluate((node) => node._fullLayout.xaxis.autorange)).toBe(true);
});

test('Plotly asset failure leaves KPIs and filters usable', async ({ page }, testInfo) => {
  await blockOptionalAnalytics(page);
  await page.route('**/plotly-basic-2.35.2.min.js', (route) => route.abort());
  await page.goto(dashboardPath(testInfo));

  await expect(page.locator('#app-status')).toContainText('visualizaciones no pudieron cargarse');
  await expect(page.locator('#real-index')).not.toHaveText('—');
  await expect(page.locator('#overview-index-chart .chart-fallback')).toBeVisible();
  await page.locator('#year-filter').selectOption('2025');
  await expect(page.locator('#overview-date')).toContainText('2025');
});

test('layout remains within the viewport', async ({ page }, testInfo) => {
  await openDashboard(page, testInfo);

  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
      ),
    )
    .toBe(true);
  await expect(page.locator('.shell')).toBeVisible();
});

test('404 artifact is usable and the local server returns missing status', async ({ page, request }) => {
  const missing = await request.get('definitely-missing-page');
  expect(missing.status()).toBe(404);

  await blockOptionalAnalytics(page);
  await page.goto('404.html');
  await expect(page).toHaveTitle(/Página no encontrada/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Página no encontrada.');
  await expect(page.getByRole('link', { name: 'Volver al dashboard' })).toBeVisible();
});

test('dashboard shell has no serious WCAG A or AA violations', async ({ page }, testInfo) => {
  await openDashboard(page, testInfo);

  const results = await new AxeBuilder({ page })
    .include('.shell')
    .exclude('.plot-surface')
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();

  const serious = results.violations.filter(({ impact }) =>
    ['serious', 'critical'].includes(impact),
  );
  expect(serious).toEqual([]);
});
