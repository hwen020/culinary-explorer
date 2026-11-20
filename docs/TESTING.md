# Testing

Run the following commands from the workspace after installing dependencies.

```powershell
.\.venv312\Scripts\python.exe -m pytest -q
npm.cmd test
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build --outDir (Join-Path $env:TEMP ('culinary-build-' + [guid]::NewGuid()))
$env:CULINARY_TEST_PYTHON = '.venv312\Scripts\python.exe'
$env:CULINARY_BROWSER = 'msedge'
npm.cmd run e2e
docker compose config --quiet
```

The browser suite uses local ports 55173 and 58000, builds temporary frontend assets, checks API readiness through Vite, and uses a separate demo database. It captures traces and screenshots for failures and prints API statuses and browser errors. If Edge is unavailable, install Playwright Chromium with `npx playwright install chromium` and unset `CULINARY_BROWSER`.

Pytest uses a fresh temporary database and checks account isolation, migration startup, worker retries, Chroma persistence, idempotency, reset, and Google data boundaries. Google and Stripe request paths use fixtures and mocked calls. The suite never creates a charge or sends email. See [implementation status](IMPLEMENTATION_STATUS.md) for the latest results.
