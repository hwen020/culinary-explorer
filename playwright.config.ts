import {defineConfig} from '@playwright/test'
import {mkdtempSync} from 'node:fs'
import {tmpdir} from 'node:os'
import {join} from 'node:path'

const origin = 'http://127.0.0.1:55173'
const backend = 'http://127.0.0.1:58000'
const bundle = mkdtempSync(join(tmpdir(), 'culinary-browser-build-'))

export default defineConfig({
  testDir: './tests/browser',
  workers: 1,
  timeout: 120000,
  expect: {timeout: 15000},
  outputDir: mkdtempSync(join(tmpdir(), 'culinary-browser-results-')),
  use: {baseURL: origin, channel: process.env.CULINARY_BROWSER || undefined,
    trace: 'retain-on-failure', screenshot: 'only-on-failure', acceptDownloads: true, actionTimeout: 15000,
    launchOptions: {args: ['--no-proxy-server', '--disable-background-networking']}},
  webServer: [
    {command: '"' + (process.env.CULINARY_TEST_PYTHON || 'python') + '" -m uvicorn backend.main:app --port 58000',
      url: backend + '/api/health', stdout: 'pipe',
      env: {CULINARY_MODE: 'demo', CULINARY_DATA_DIR: mkdtempSync(join(tmpdir(), 'culinary-browser-')),
        CULINARY_DEMO_DATABASE_URL: '', APP_ORIGIN: origin, OLLAMA_MODEL: ''}},
    {command: 'node node_modules/vite/bin/vite.js build --outDir "' + bundle + '" && node node_modules/vite/bin/vite.js preview --outDir "' + bundle + '" --host 127.0.0.1 --port 55173 --strictPort',
      url: origin + '/api/health', env: {CULINARY_API_TARGET: backend}},
  ],
})
