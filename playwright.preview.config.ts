import {defineConfig} from '@playwright/test'
import {tmpdir} from 'node:os'
import {mkdtempSync} from 'node:fs'
import {join} from 'node:path'

const hosted = process.env.CULINARY_PREVIEW_URL
const baseURL = hosted || 'http://127.0.0.1:58111'
if (hosted && new URL(hosted).protocol !== 'https:') throw new Error('Public preview tests require HTTPS')

export default defineConfig({
  testDir: './tests/preview',
  outputDir: mkdtempSync(join(tmpdir(), 'culinary-preview-results-')),
  workers: 1,
  timeout: 150000,
  expect: {timeout: 20000},
  use: {baseURL, channel: process.env.CULINARY_BROWSER || undefined, trace: 'retain-on-failure'},
  webServer: hosted ? undefined : {
    command: '"' + (process.env.CULINARY_TEST_PYTHON || 'python') + '" -m uvicorn backend.preview:app --port 58111',
    url: baseURL + '/api/health',
    env: {CULINARY_DEPLOYMENT: 'preview', CULINARY_MODE: 'demo', APP_ORIGIN: baseURL,
      CULINARY_DEMO_DATABASE_URL: '', CULINARY_LIVE_DATABASE_URL: ''},
  },
})
