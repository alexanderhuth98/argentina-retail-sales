const { test, expect } = require('@playwright/test');

test('@smoke published dashboard boots', async ({ page }) => {
  await page.route(/(goatcounter\.com|gc\.zgo\.at)/, (route) => route.abort());
  const response = await page.goto('./');

  expect(response?.ok()).toBe(true);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Pulso del retail argentino');
  await expect(page.locator('#gate-value')).toHaveText('APROBADO');
  await expect(page.locator('#app-status')).toContainText('Datos listos:');
});
