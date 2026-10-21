const { defineConfig, devices } = require('@playwright/test');

const localBaseURL = 'http://127.0.0.1:41733/';
const configuredBaseURL = process.env.E2E_BASE_URL || localBaseURL;
const baseURL = configuredBaseURL.endsWith('/') ? configuredBaseURL : `${configuredBaseURL}/`;

module.exports = defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: 2,
  reporter: [['line'], ['html', { open: 'never' }]],
  outputDir: 'test-results',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'desktop Chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'mobile Chromium',
      use: { ...devices['Pixel 5'] },
    },
  ],
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: 'python -m http.server 41733 --bind 127.0.0.1 --directory site',
        url: localBaseURL,
        reuseExistingServer: !process.env.CI,
        timeout: 30_000,
      },
});
